import datetime
import logging
import os
import time
from dataclasses import dataclass

import boto3
import httpx

FANTASY_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF"}

BASE_URL = "https://api.sleeper.app/v1"
PLAYERS_PATH = "/players/nfl/nope"
USERS_PATH = "/league/{league_id}/users"

logger = logging.getLogger(__name__)

def configure_logging() -> None:
    """Configure logging for both Lambda and local execution."""

    root = logging.getLogger()

    if root.handlers:
        # Set the logging for lambda
        root.setLevel(logging.INFO)
        for handler in root.handlers:
            handler.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
            )
    else:
        # Set the logging for local execution
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[logging.StreamHandler()],
        )

class ConfigError(Exception):
    """Raised when required configuration is missing or invalid"""

@dataclass(frozen=True)
class Config:
    players_table: str
    users_table: str
    league_ids: tuple[str, ...]

def load_config() -> Config:
    names = ("LEAGUE_IDS", "PLAYERS_TABLE", "USERS_TABLE")
    values = {name: os.environ.get(name, "").strip() for name in names}

    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ConfigError(f"Missing required environment variables {', '.join(missing)}")

    league_ids = tuple(
        part.strip() for part in values["LEAGUE_IDS"].split(",") if part.strip()
    )
    if not league_ids or not all (lid.isdigit() for lid in league_ids):
        raise ConfigError(
            f"LEAGUE_IDS must be a comma-separated list of numeric IDs, got {values['LEAGUE_IDS']!r}"
        )

    return Config(
        league_ids=league_ids,
        players_table=values["PLAYERS_TABLE"],
        users_table=values["USERS_TABLE"]
    )

def fetch_json(client: httpx.Client, path: str, expected_type: type):

    # Query the url for a response and store it
    response = client.get(path)
    response.raise_for_status()

    # Parse returned data and determine the amount of time this took
    start = time.perf_counter()
    data = response.json()
    parse_seconds = time.perf_counter() - start

    logger.info(
        "Fetched %s: status=%s bytes=%s download=%.2fs, parse=%.2fs",
        path,
        response.status_code,
        len(response.content),
        response.elapsed.total_seconds(),
        parse_seconds,
    )

    # Check the response is of the expected data type
    if not isinstance(data, expected_type):
        raise TypeError(
            f"Expected {expected_type.__name__} from {path}, got {type(data).__name__}"
        )

    return data

def player_items(raw: dict, refreshed_at: str) -> list:
    # Only return the fields required from the /players response
    players_trimmed = []
    for player_id, player_data in raw.items():
        position = player_data.get("position")
        if position in FANTASY_POSITIONS:
            player = {
                "player_id": player_id,
                "first_name": player_data.get("first_name"),
                "last_name": player_data.get("last_name"),
                "position": position,
                "team": player_data.get("team"),
                "injury_status": player_data.get("injury_status"),
                "refreshed_at": refreshed_at,
            }
            players_trimmed.append(player)
    return players_trimmed


def user_items(raw: list, league_id: str, refreshed_at: str) -> list:
    # Only return the fields required from the /users response
    users_trimmed = []
    for user_data in raw:
        metadata = user_data.get("metadata") or {}
        team_name = metadata.get("team_name")
        user = {
            "league_id": league_id,
            "user_id": user_data.get("user_id"),
            "display_name": user_data.get("display_name"),
            "team_name": team_name,
            "refreshed_at": refreshed_at,
        }
        users_trimmed.append(user)

    return users_trimmed


def handler(event, context):
    return {"status": "ok"}
