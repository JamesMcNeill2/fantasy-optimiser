"""Tests for the batch handler (services/batch/app/main.py).

No network and no AWS: Sleeper and its CDN are one MockTransport fake, and
DynamoDB and S3 are small fake classes swapped in for boto3. The transforms and
copy_avatars have their own tests; these check how handler() puts them
together: the config check, the order of the Sleeper calls, one refreshed_at
per run, each part failing on its own, and the summary logged before
BatchRunError is raised.
"""

import copy
import datetime
import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from botocore.exceptions import ClientError
from shared.config import ConfigError
from shared.sleeper import BASE_URL

from app import main
from app.main import BatchRunError

# --- Fake data -----------------------------------------------------------------
# Obviously fake IDs: this file is committed, and the failure labels and the
# summary line both contain league IDs.

LEAGUE_A = "900000000000000001"
LEAGUE_B = "900000000000000002"
USER_1 = "800000000000000001"
USER_2 = "800000000000000002"
USER_3 = "800000000000000003"
USER_4 = "800000000000000004"

PLAYERS_TABLE = "players-test"
USERS_TABLE = "users-test"
BUCKET = "avatars-test"

# The handler's size check: fewer players than this fails the players part.
MIN_PLAYERS = 3000

CDN = "https://sleepercdn.com/uploads/"
JPEG = b"\xff\xd8\xff fake jpeg"

# Brad is in both leagues with the same avatar, so it's copied once. cccc.jpg
# is only in league A and bbbb.jpg only in league B, so a test can tell whose
# avatars were collected.
USERS = {
    LEAGUE_A: [
        {
            "user_id": USER_1,
            "display_name": "brad",
            "metadata": {"team_name": "Bravo Ballers", "avatar": CDN + "aaaa.jpg"},
        },
        {"user_id": USER_2, "display_name": "ann", "metadata": None},
        {
            "user_id": USER_4,
            "display_name": "dee",
            "metadata": {"avatar": CDN + "cccc.jpg"},
        },
    ],
    LEAGUE_B: [
        {
            "user_id": USER_1,
            "display_name": "brad",
            "metadata": {"team_name": "Bravo B-Team", "avatar": CDN + "aaaa.jpg"},
        },
        {
            "user_id": USER_3,
            "display_name": "cat",
            "metadata": {"avatar": CDN + "bbbb.jpg"},
        },
    ],
}

ALL_COPIED = {"copied": 3, "existing": 0, "failed": 0}


def players_payload(count: int = MIN_PLAYERS) -> dict[str, dict]:
    """A /players/nfl response: `count` fantasy players plus one lineman.

    player_items drops the lineman, so the size check sees exactly `count`.
    """
    players = {
        str(10000 + n): {
            "first_name": "Test",
            "last_name": f"Player{n}",
            "number": n % 100,
            "position": "WR",
            "team": "KC",
            "injury_status": None,
        }
        for n in range(count)
    }
    players["99999"] = {"first_name": "Oscar", "last_name": "Line", "position": "OL"}
    return players


PLAYERS = players_payload()


# --- Helpers -------------------------------------------------------------------


def respond(payload: object) -> httpx.Response:
    """A response with a streamed body (pre-loaded bodies break .elapsed)."""
    return httpx.Response(200, stream=httpx.ByteStream(json.dumps(payload).encode()))


def run() -> dict:
    return main.handler({}, None)


def summary_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        r.getMessage()
        for r in caplog.records
        if r.getMessage().startswith("Run summary")
    ]


def errors_in(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.levelno == logging.ERROR]


def write_error() -> ClientError:
    return ClientError({"Error": {"Code": "InternalServerError"}}, "BatchWriteItem")


# --- Fakes ---------------------------------------------------------------------


class FakeSleeper:
    """Answers Sleeper's API and its CDN, as the handler uses one client for both.

    Tests change the attributes before the run: `players` and `users` are the
    payloads, `images` the CDN's files, and `failing` holds URL substrings
    that get a 500.
    """

    def __init__(self) -> None:
        self.players: object = copy.deepcopy(PLAYERS)
        self.users: dict[str, list[dict[str, Any]]] = copy.deepcopy(USERS)
        self.images = {"aaaa.jpg": JPEG, "bbbb.jpg": JPEG, "cccc.jpg": JPEG}
        self.failing: set[str] = set()
        self.requests: list[str] = []
        self.client_options: list[dict[str, Any]] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.requests.append(url)
        if any(part in url for part in self.failing):
            return httpx.Response(500)
        if url.startswith(CDN):
            body = self.images.get(url.removeprefix(CDN))
            return httpx.Response(200, content=body) if body else httpx.Response(404)
        if url == f"{BASE_URL}/players/nfl":
            return respond(self.players)
        for league_id, users in self.users.items():
            if url == f"{BASE_URL}/league/{league_id}/users":
                return respond(users)
        return httpx.Response(404)


class FakeTable:
    """A DynamoDB table with only batch_writer; each put_item is recorded.

    The real writer sends 25 items at a time; this one records each at once.
    Set `error` to make every put_item raise.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.items: list[dict] = []
        self.error: Exception | None = None

    @contextmanager
    def batch_writer(self) -> Iterator[FakeTable]:
        yield self

    def put_item(self, *, Item: dict) -> None:
        if self.error is not None:
            raise self.error
        self.items.append(Item)


class FakeDynamoDB:
    """A DynamoDB resource that hands out the fake tables by name.

    An unexpected name raises KeyError, so the tests prove the handler uses
    the configured table names.
    """

    def __init__(self, *tables: FakeTable) -> None:
        self.tables = {table.name: table for table in tables}

    def Table(self, name: str) -> FakeTable:
        return self.tables[name]


class FakeS3:
    """S3 with the two calls copy_avatars makes: head_object and put_object."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.puts: list[dict[str, Any]] = []

    def head_object(self, **kwargs: Any) -> dict[str, Any]:
        if kwargs["Key"] not in self.objects:
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")
        return {}

    def put_object(self, **kwargs: Any) -> dict[str, Any]:
        self.puts.append(kwargs)
        self.objects[kwargs["Key"]] = kwargs["Body"]
        return {}


@pytest.fixture
def batch(monkeypatch, caplog):
    """Swap the handler's config, Sleeper client and AWS clients for fakes."""
    monkeypatch.setenv("PLAYERS_TABLE", PLAYERS_TABLE)
    monkeypatch.setenv("USERS_TABLE", USERS_TABLE)
    monkeypatch.setenv("LEAGUE_IDS", f"{LEAGUE_A},{LEAGUE_B}")
    monkeypatch.setenv("AVATARS_BUCKET", BUCKET)

    sleeper = FakeSleeper()
    players, users = FakeTable(PLAYERS_TABLE), FakeTable(USERS_TABLE)
    dynamodb = FakeDynamoDB(players, users)
    s3 = FakeS3()
    real_client = httpx.Client

    def sleeper_client(**options: Any) -> httpx.Client:
        sleeper.client_options.append(options)
        return real_client(transport=httpx.MockTransport(sleeper.handle), **options)

    def resource(service_name: str, **kwargs: Any) -> FakeDynamoDB:
        assert service_name == "dynamodb"
        return dynamodb

    def client(service_name: str, **kwargs: Any) -> FakeS3:
        assert service_name == "s3"
        return s3

    monkeypatch.setattr(main.httpx, "Client", sleeper_client)
    monkeypatch.setattr(main.boto3, "resource", resource)
    monkeypatch.setattr(main.boto3, "client", client)
    # configure_logging would restyle pytest's own log handlers.
    monkeypatch.setattr(main, "configure_logging", lambda: None)
    caplog.set_level(logging.INFO)

    return SimpleNamespace(sleeper=sleeper, players=players, users=users, s3=s3)


# --- A normal run ---------------------------------------------------------------


def test_handler_refreshes_players_users_and_avatars(batch, caplog):
    summary = run()

    # Exactly MIN_PLAYERS players passes the size check.
    assert summary == {
        "players": MIN_PLAYERS,
        "users": {LEAGUE_A: 3, LEAGUE_B: 2},
        "avatars": ALL_COPIED,
    }
    assert len(batch.players.items) == MIN_PLAYERS
    assert "99999" not in {item["player_id"] for item in batch.players.items}
    assert [(i["league_id"], i["user_id"]) for i in batch.users.items] == [
        (LEAGUE_A, USER_1),
        (LEAGUE_A, USER_2),
        (LEAGUE_A, USER_4),
        (LEAGUE_B, USER_1),
        (LEAGUE_B, USER_3),
    ]
    assert [(put["Bucket"], put["Key"]) for put in batch.s3.puts] == [
        (BUCKET, "avatars/aaaa.jpg"),
        (BUCKET, "avatars/bbbb.jpg"),
        (BUCKET, "avatars/cccc.jpg"),
    ]
    assert summary_lines(caplog) == [f"Run summary: {summary}"]
    assert not errors_in(caplog)


def test_handler_calls_sleeper_once_each_with_one_client(batch):
    run()

    assert batch.sleeper.requests == [
        f"{BASE_URL}/players/nfl",
        f"{BASE_URL}/league/{LEAGUE_A}/users",
        f"{BASE_URL}/league/{LEAGUE_B}/users",
        CDN + "aaaa.jpg",
        CDN + "bbbb.jpg",
        CDN + "cccc.jpg",
    ]
    assert len(batch.sleeper.client_options) == 1
    assert batch.sleeper.client_options[0]["base_url"] == BASE_URL


def test_handler_fetches_leagues_in_the_configured_order(batch, monkeypatch):
    monkeypatch.setenv("LEAGUE_IDS", f"{LEAGUE_B},{LEAGUE_A}")

    summary = run()

    assert batch.sleeper.requests[1:3] == [
        f"{BASE_URL}/league/{LEAGUE_B}/users",
        f"{BASE_URL}/league/{LEAGUE_A}/users",
    ]
    assert list(summary["users"]) == [LEAGUE_B, LEAGUE_A]


def test_handler_stamps_every_item_with_one_utc_time(batch):
    before = datetime.datetime.now(datetime.UTC)
    run()
    after = datetime.datetime.now(datetime.UTC)

    stamps = {item["refreshed_at"] for item in batch.players.items + batch.users.items}
    assert len(stamps) == 1
    stamp = datetime.datetime.fromisoformat(stamps.pop())
    assert stamp.utcoffset() == datetime.timedelta(0)
    assert before <= stamp <= after


def test_handler_counts_avatar_problems_without_failing_the_run(batch):
    # One already stored, one missing from the CDN: counted, not raised.
    batch.s3.objects["avatars/aaaa.jpg"] = JPEG
    del batch.sleeper.images["bbbb.jpg"]

    summary = run()

    assert summary["avatars"] == {"copied": 1, "existing": 1, "failed": 1}
    assert [put["Key"] for put in batch.s3.puts] == ["avatars/cccc.jpg"]


# --- Config --------------------------------------------------------------------


@pytest.mark.parametrize("name", ["LEAGUE_IDS", "PLAYERS_TABLE", "USERS_TABLE"])
def test_handler_missing_config_fails_before_any_call(batch, monkeypatch, caplog, name):
    monkeypatch.delenv(name)

    with pytest.raises(ConfigError, match=name):
        run()

    assert batch.sleeper.client_options == []
    assert batch.sleeper.requests == []
    assert batch.players.items == []
    assert batch.users.items == []
    assert summary_lines(caplog) == []


@pytest.mark.parametrize("value", [None, "   "], ids=["unset", "blank"])
def test_handler_without_an_avatars_bucket_writes_the_data_then_fails(
    batch, monkeypatch, caplog, value
):
    if value is None:
        monkeypatch.delenv("AVATARS_BUCKET")
    else:
        monkeypatch.setenv("AVATARS_BUCKET", value)

    with pytest.raises(BatchRunError, match=r"^Batch run failed for: avatars$"):
        run()

    assert len(batch.players.items) == MIN_PLAYERS
    assert len(batch.users.items) == 5
    assert not any(url.startswith(CDN) for url in batch.sleeper.requests)
    assert batch.s3.puts == []
    expected = {
        "players": MIN_PLAYERS,
        "users": {LEAGUE_A: 3, LEAGUE_B: 2},
        "avatars": None,
    }
    assert summary_lines(caplog) == [f"Run summary: {expected}"]


# --- Failures stay in their own part ----------------------------------------------


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"failing": {"/players/nfl"}}, id="status-500"),
        pytest.param({"players": [PLAYERS]}, id="not-a-dict"),
        pytest.param({"players": players_payload(MIN_PLAYERS - 1)}, id="too-few"),
    ],
)
def test_handler_players_failure_leaves_users_and_avatars_alone(batch, caplog, changes):
    for name, value in changes.items():
        setattr(batch.sleeper, name, value)

    with pytest.raises(BatchRunError, match=r"^Batch run failed for: players$"):
        run()

    assert batch.players.items == []
    assert len(batch.users.items) == 5
    assert len(batch.s3.puts) == 3
    # No second try: each /players call counts against Sleeper's daily limit.
    assert batch.sleeper.requests.count(f"{BASE_URL}/players/nfl") == 1
    expected = {
        "players": None,
        "users": {LEAGUE_A: 3, LEAGUE_B: 2},
        "avatars": ALL_COPIED,
    }
    assert summary_lines(caplog) == [f"Run summary: {expected}"]
    assert [r.getMessage().split(" after ")[0] for r in errors_in(caplog)] == [
        "Players refresh failed"
    ]


def test_handler_players_write_failure_leaves_users_and_avatars_alone(batch):
    batch.players.error = write_error()

    with pytest.raises(BatchRunError, match=r"^Batch run failed for: players$"):
        run()

    assert len(batch.users.items) == 5
    assert len(batch.s3.puts) == 3


def test_handler_one_league_failing_leaves_the_other_alone(batch, caplog):
    # League A is fetched first, so this also proves the loop carries on.
    batch.sleeper.failing = {f"/league/{LEAGUE_A}/users"}

    with pytest.raises(
        BatchRunError, match=rf"^Batch run failed for: users:{LEAGUE_A}$"
    ):
        run()

    assert len(batch.players.items) == MIN_PLAYERS
    assert {item["league_id"] for item in batch.users.items} == {LEAGUE_B}
    # Only league B's avatars: cccc.jpg belongs to league A alone.
    assert [put["Key"] for put in batch.s3.puts] == [
        "avatars/aaaa.jpg",
        "avatars/bbbb.jpg",
    ]
    expected = {
        "players": MIN_PLAYERS,
        "users": {LEAGUE_B: 2},
        "avatars": {"copied": 2, "existing": 0, "failed": 0},
    }
    assert summary_lines(caplog) == [f"Run summary: {expected}"]


def test_handler_users_write_failure_collects_no_avatars(batch, caplog):
    # A league's avatars are only collected once its users are written.
    batch.users.error = write_error()

    with pytest.raises(
        BatchRunError,
        match=rf"^Batch run failed for: users:{LEAGUE_A}, users:{LEAGUE_B}$",
    ):
        run()

    assert len(batch.players.items) == MIN_PLAYERS
    assert not any(url.startswith(CDN) for url in batch.sleeper.requests)
    assert batch.s3.puts == []
    expected = {
        "players": MIN_PLAYERS,
        "users": {},
        "avatars": {"copied": 0, "existing": 0, "failed": 0},
    }
    assert summary_lines(caplog) == [f"Run summary: {expected}"]


def test_handler_names_every_failed_part_in_order(batch, monkeypatch, caplog):
    batch.sleeper.failing = {"/players/nfl", "/users"}
    monkeypatch.delenv("AVATARS_BUCKET")

    with pytest.raises(BatchRunError) as exc_info:
        run()

    assert str(exc_info.value) == (
        f"Batch run failed for: players, users:{LEAGUE_A}, users:{LEAGUE_B}, avatars"
    )
    errors = errors_in(caplog)
    assert len(errors) == 4
    assert all(record.exc_info for record in errors)  # each with its traceback
    expected = {"players": None, "users": {}, "avatars": None}
    assert summary_lines(caplog) == [f"Run summary: {expected}"]
