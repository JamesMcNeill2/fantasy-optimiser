import datetime
import logging
import time
from typing import TYPE_CHECKING

import boto3
import httpx
from shared.config import load_config
from shared.logs import configure_logging
from shared.sleeper import BASE_URL, fetch_json

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import Table

FANTASY_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF"}

PLAYERS_PATH = "/players/nfl"
USERS_PATH = "/league/{league_id}/users"

logger = logging.getLogger(__name__)


class BatchRunError(Exception):
    """Raised at the end of a run when any dataset failed to refresh"""


def player_items(raw: dict, refreshed_at: str) -> list[dict]:
    """
    Return trimmed player records for supported fantasy positions.

    Args:
        raw: Raw player payload from the Sleeper API.
        refreshed_at: Timestamp indicating when the data was refreshed.

    Returns:
        list[dict]: Player records trimmed to the fields required for storage.
    """

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
    """
    Return trimmed user records associated with the given league.

    Args:
        raw: Raw user payload for a league from the Sleeper API.
        league_id: League identifier to assign to each returned user record.
        refreshed_at: Timestamp indicating when the data was refreshed.

    Returns:
        list[dict]: User records trimmed to the fields required for storage.
    """

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
    """
    Write items to a DynamoDB table and return the number written.

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
    """
    Refresh player and league-user data, then return write counts.

    Args:
        event: Lambda event payload.
        context: Lambda context object.

    Returns:
        dict: A summary of the number of player and user records written.

    Raises:
        ValueError: If the fetched players payload is below the minimum
            expected size, or if a required record transform fails.
        httpx.HTTPError: If a request to the Fantasy API fails while fetching
            the player or league-user data.
        Exception: If a DynamoDB write or other unexpected processing step fails
            before it can be handled by the internal retry-and-log logic.
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
