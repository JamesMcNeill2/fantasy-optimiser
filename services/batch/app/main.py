import datetime
import logging
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import boto3
import httpx

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import Table

FANTASY_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF"}

BASE_URL = "https://api.sleeper.app/v1"
PLAYERS_PATH = "/players/nfl"
USERS_PATH = "/league/{league_id}/users"

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configure logging for both Lambda and local execution.

    Args:
        None.

    Returns:
        None.
    """

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
    """Load and validate required settings from environment variables.

    Args:
        None.

    Returns:
        Config: Validated application configuration loaded from the environment.
    """

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


def fetch_json[T](client: httpx.Client, path: str, expected_type: type[T]) -> T:
    """Fetch JSON from the API and verify that it has the expected type.

    Args:
        client: HTTP client to use for the request.
        path: Relative API path to request.
        expected_type: Python type expected for the decoded JSON payload.

    Returns:
        object: The decoded JSON payload from the API.
    """

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


def player_items(raw: dict, refreshed_at: str) -> list[dict]:
    """Return trimmed player records for supported fantasy positions.

    Args:
        raw: Raw player payload from the Sleeper API.
        refreshed_at: Timestamp indicating when the data was refreshed.

    Returns:
        list[dict]: Player records trimmed to the fields required for storage.
    """

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


def user_items(raw: list, league_id: str, refreshed_at: str) -> list[dict]:
    """Return trimmed user records associated with the given league.

    Args:
        raw: Raw user payload for a league from the Sleeper API.
        league_id: League identifier to assign to each returned user record.
        refreshed_at: Timestamp indicating when the data was refreshed.

    Returns:
        list[dict]: User records trimmed to the fields required for storage.
    """

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
    """Write items to a DynamoDB table and return the number written.

    Args:
        table: DynamoDB table resource to write into.
        items: Records to write to the table.

    Returns:
        int: The number of items successfully written to the table.
    """

    count = 0
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)
            count += 1

    # Only reached once __exit__ has flushed the final partial batch successfully
    return count


def handler(event, context):
    """Refresh player and league-user data, then return write counts.

    Args:
        event: Lambda event payload.
        context: Lambda context object.

    Returns:
        dict: A summary of the number of player and user records written.
    """

    configure_logging()
    config = load_config()

    dynamodb = boto3.resource("dynamodb")
    players_table = dynamodb.Table(config.players_table)
    users_table = dynamodb.Table(config.users_table)

    # Determine time for refreshed_at
    refreshed_at = datetime.datetime.now(datetime.UTC).isoformat()

    summary = {"players": None, "users": {}}
    failures = []

    with httpx.Client(
        base_url=BASE_URL, timeout=httpx.Timeout(20, connect=5)
    ) as client:
        players_start = time.perf_counter()
        try:
            # Get and trim the players data
            player_raw = fetch_json(client, PLAYERS_PATH, dict)
            players_trimmed_data = player_items(player_raw, refreshed_at)
            if len(players_trimmed_data) < 3000:
                raise ValueError(
                    f"Not enough players to write to DynamoDB. "
                    f"Got: {len(players_trimmed_data)}, expected at least 3000"
                )

            # Write players to DynamoDB
            players_written = write_items(players_table, players_trimmed_data)
            summary["players"] = players_written
            logger.info(
                "Wrote %d players to %s in %.2fs",
                players_written,
                config.players_table,
                time.perf_counter() - players_start,
            )
        except Exception:
            failures.append("players")
            logger.exception(
                "Players refresh failed after %.2fs",
                time.perf_counter() - players_start,
            )

        for league_id in config.league_ids:
            users_start = time.perf_counter()
            try:
                # Get and trim the users data
                path = USERS_PATH.format(league_id=league_id)
                users_raw = fetch_json(client, path, list)
                users_trimmed_data = user_items(users_raw, league_id, refreshed_at)

                # Write users to DynamoDB
                users_written = write_items(users_table, users_trimmed_data)
                summary["users"][league_id] = users_written
                logger.info(
                    "Wrote %d users for league %s to %s in %.2fs",
                    users_written,
                    league_id,
                    config.users_table,
                    time.perf_counter() - users_start,
                )
            except Exception:
                failures.append(f"users:{league_id}")
                logger.exception(
                    "Users refresh failed for league %s after %.2fs",
                    league_id,
                    time.perf_counter() - users_start,
                )

    logger.info("Run summary: %s", summary)
    if failures:
        raise BatchRunError(f"Batch run failed for: {', '.join(failures)}")

    return summary
