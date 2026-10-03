import datetime
import logging
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import Table

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


class BatchRunError(Exception):
    """Raised at the end of a run when any dataset failed to refresh"""


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
        raise ConfigError(
            f"Missing required environment variables {', '.join(missing)}"
        )

    league_ids = tuple(
        part.strip() for part in values["LEAGUE_IDS"].split(",") if part.strip()
    )
    if not league_ids or not all(lid.isdigit() for lid in league_ids):
        raise ConfigError(
            f"LEAGUE_IDS must be a comma-separated list of numeric IDs, got {values['LEAGUE_IDS']!r}"
        )

    return Config(
        league_ids=league_ids,
        players_table=values["PLAYERS_TABLE"],
        users_table=values["USERS_TABLE"],
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


def write_items(table: Table, items: list[dict]) -> int:
    """Write items to a DynamoDB table in batches and return how many were written."""
    count = 0
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)
            count += 1

    # Only reached once __exit__ has flushed the final partial batch successfully
    return count


def handler(event, context):
    configure_logging()
    config = load_config()

    dynamodb = boto3.resource("dynamodb")
    players_table = dynamodb.Table(config.players_table)
    users_table = dynamodb.Table(config.users_table)

    # Determine time for refreshed_at
    refreshed_at = datetime.datetime.now(datetime.UTC).isoformat()

    # Get and trim the players data
    with httpx.Client(base_url=BASE_URL, timeout=httpx.Timeout(20, connect=5)) as client:
        player_raw = fetch_json(client, PLAYERS_PATH, dict)
        players_trimmed_data = player_items(player_raw, refreshed_at)

        if len(players_trimmed_data) < 3000:
            error_msg = f"Not enough players to write to Dynamodb. Got {len(players_trimmed_data)}, expected > 3000"
            raise ValueError(error_msg)

        written = write_items(players_table, players_trimmed_data)
        logging.info("Wrote %d players %s", written, config.players_table)

        # Get and trim the users data
        for league_id in config.league_ids:
            path = USERS_PATH.format(league_id=league_id)
            users_raw = fetch_json(client, path, list)
            users_trimmed_data = user_items(users_raw, league_id, refreshed_at)
            write_items(users_table, users_trimmed_data)
            logger.info("Wrote %d users for league %s to %s", written, league_id, config.users_table)
