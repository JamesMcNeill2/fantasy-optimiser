import datetime
import logging
import os
import time
from collections.abc import Iterable
from typing import TYPE_CHECKING

import boto3
import httpx
from botocore.exceptions import ClientError
from shared.avatars import AVATAR_URL_PREFIX, AVATARS_FOLDER, avatar_file
from shared.config import load_config
from shared.logs import configure_logging
from shared.sleeper import BASE_URL, fetch_json

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import Table
    from mypy_boto3_s3.client import S3Client

FANTASY_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF"}

PLAYERS_PATH = "/players/nfl"
USERS_PATH = "/league/{league_id}/users"

AVATAR_MAX_BYTES = 1_000_000
AVATAR_CACHE_CONTROL = "public, max-age=31536000, immutable"

# The first bytes of each image format the batch stores. Sleeper's CDN sends
# the wrong Content-Type (image/png for JPEG files), so the type comes from
# the file itself, not the response header.
IMAGE_SIGNATURES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
}

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
                "shirt_number": player_data.get("number"),
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
            "avatar": metadata.get("avatar"),
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


def avatar_exits(s3: S3Client, bucket: str, key: str) -> bool:
    """
    Check whether an avatar is already stored.

    Args:
        s3: S3 client.
        bucket: Bucket holding the avatars.
        key: The avatar's object key.

    Returns:
        bool: True if the object exists, False if S3 reports it missing.

    Raises:
        ClientError: For any error other than not found, such as access denied.
    """
    try:
        s3.head_object(Bucket=bucket, Key=key)
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") == "404":
            return False
        raise
    return True


def image_type(body: bytes) -> str | None:
    """
    Identify a JPEG or PNG image from its first bytes.

    Args:
        body: The downloaded file.

    Returns:
        str | None: "image/jpeg" or "image/png", or None for anything else.
    """
    for signature, content_type in IMAGE_SIGNATURES.items():
        if body.startswith(signature):
            return content_type
    return None


def copy_avatars(
    s3: S3Client, client: httpx.Client, bucket: str, urls: Iterable[object]
) -> dict[str, int]:
    """
    Copy Sleeper avatar uploads into the bucket, skipping ones already stored.

    A new avatar always has a new file name, so a stored file never needs
    replacing. Each file is stored with the type of image it actually contains.
    Each failure is logged as a warning and counted; it doesn't stop the rest.

    Args:
        s3: S3 client.
        client: HTTP client used to download from Sleeper's CDN.
        bucket: Bucket to copy the avatars into.
        urls: Stored avatar values; anything that isn't a Sleeper upload URL
            is ignored.

    Returns:
        dict[str, int]: Counts of avatars copied, already stored and failed.
    """

    names = sorted({name for url in urls if (name := avatar_file(url))})
    counts = {"copied": 0, "existing": 0, "failed": 0}
    for name in names:
        key = f"{AVATARS_FOLDER}/{name}"
        try:
            if avatar_exits(s3, bucket, key):
                counts["existing"] += 1
                continue
            response = client.get(AVATAR_URL_PREFIX + name)
            response.raise_for_status()
            content = response.content
            if len(content) > AVATAR_MAX_BYTES:
                raise ValueError(f"{len(content)} bytes is over the limit")
            content_type = image_type(content)
            if content_type is None:
                raise ValueError("Not a JPEG or PNG image")
            s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
                CacheControl=AVATAR_CACHE_CONTROL,
            )
            counts["copied"] += 1
        except Exception:
            counts["failed"] += 1
            logger.warning("Avatar copy failed for %s", name, exc_info=True)

    return counts


def handler(event, context):
    """
    Refresh player and league-user data, then return write counts.

    Args:
        event: Lambda event payload.
        context: Lambda context object.

    Returns:
        dict: A summary of the player and user records written and the avatar copy counts.

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

    summary = {"players": None, "users": {}, "avatars": None}
    failures = []
    avatar_urls: list[str | None] = []

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
                avatar_urls.extend(item["avatar"] for item in users_trimmed_data)
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

        avatars_start = time.perf_counter()
        try:
            bucket = os.environ.get("AVATARS_BUCKET", "").strip()
            if not bucket:
                raise ValueError("AVATARS_BUCKET is not set")
            counts = copy_avatars(boto3.client("s3"), client, bucket, avatar_urls)
            summary["avatars"] = counts
            logger.info(
                "Avatars: %d copied, %d already sorted, %d failed in %.2fs",
                counts["copied"],
                counts["existing"],
                counts["failed"],
                time.perf_counter() - avatars_start,
            )
        except Exception:
            failures.append("avatars")
            logger.exception(
                "Avatar copy failed after %.2fs", time.perf_counter() - avatars_start
            )

    logger.info("Run summary: %s", summary)
    if failures:
        raise BatchRunError(f"Batch run failed for: {', '.join(failures)}")

    return summary
