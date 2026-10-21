"""Tests for the api Lambda (services/api/app/main.py).

No network and no AWS: Sleeper is a MockTransport fake and DynamoDB is a pair of
small fake classes. Run with `uv run python -m pytest` from services/api,
without --env-file, so a missed dependency override fails instead of using real
IDs.
"""

import copy
import json
import logging
import re
import time
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from shared.config import Config
from shared.sleeper import BASE_URL

from app import main
from app.main import (
    NflWeek,
    Tables,
    WeekGame,
    avatar_path,
    clean_int,
    clean_str,
    describe_game,
    get_actual_points,
    get_nfl_week,
    get_players,
    get_projection,
    get_projections,
    get_roster_positions,
    get_week_games,
)

# --- Fake data -----------------------------------------------------------------
# Obviously fake IDs: this file is committed, and distinctive values make the
# "no IDs in the response" checks meaningful.

LEAGUE_A = "900000000000000001"
LEAGUE_B = "900000000000000002"
USER_1 = "800000000000000001"
USER_2 = "800000000000000002"
USER_4 = "800000000000000004"
USER_5 = "800000000000000005"
USER_6 = "800000000000000006"
USER_7 = "800000000000000007"
SECRET_IDS = (LEAGUE_A, LEAGUE_B, USER_1, USER_2, USER_4, USER_5, USER_6, USER_7)

# Fake avatar uploads, in the shape the batch stores (Sleeper's full URL).
AVATAR_A = "https://sleepercdn.com/uploads/0a1b2c.jpg"
AVATAR_B = "https://sleepercdn.com/uploads/3d4e5f.jpeg"

PLAYERS_TABLE = "players-test"
FAKE_CONFIG = Config(
    players_table=PLAYERS_TABLE,
    users_table="users-test",
    league_ids=(LEAGUE_A, LEAGUE_B),
)

WEEK = NflWeek("2026", 5, "regular")
PLAYER_ID = "3634"

# week differs from display_week, so a test fails if the wrong one is used.
STATE = {
    "week": 4,
    "display_week": 5,
    "season": "2026",
    "season_type": "regular",
    "leg": 5,
}

# PHI has a week-4 game but none in week 5, so PHI players are on a bye.
SCHEDULE = [
    {"week": 5, "home": "KC", "away": "LV", "status": "in_game", "game_id": "1"},
    {"week": 5, "home": "BUF", "away": "NE", "status": "complete", "game_id": "2"},
    {"week": 5, "home": "NYG", "away": "DAL", "status": "pre_game", "game_id": "3"},
    {"week": 5, "home": "MIA", "away": "NYJ", "status": "canceled", "game_id": "4"},
    {"week": 4, "home": "PHI", "away": "DAL", "status": "complete", "game_id": "5"},
]

# Six starting slots, matching the six entries in league A roster 1's starters.
# The flex is WRRB_FLEX as in the real leagues; BN entries come last.
LAYOUT_A = ["QB", "RB", "RB", "WR", "WR", "WRRB_FLEX", "BN", "BN", "BN", "BN"]
SLOTS_A = ["QB", "RB", "RB", "WR", "WR", "WRRB_FLEX"]
LAYOUT_B = ["TE", "BN"]

LEAGUES = {
    LEAGUE_A: {
        "league_id": LEAGUE_A,
        "name": " Test League A ",
        "roster_positions": LAYOUT_A,
    },
    LEAGUE_B: {"league_id": LEAGUE_B, "name": "", "roster_positions": LAYOUT_B},
}

MAIN_ROSTER_PLAYERS = [
    "1001",
    "1002",
    "1003",
    "1004",
    "1005",
    "1006",
    "1007",
    "1008",
    "1009",
]

ROSTERS = {
    LEAGUE_A: [
        {
            "roster_id": 1,
            "owner_id": USER_1,
            "league_id": LEAGUE_A,
            "players": MAIN_ROSTER_PLAYERS,
            # "0" is an empty slot: later starters must keep their indices.
            "starters": ["1001", "0", "1002", "1003", "1004", "1009"],
            "reserve": ["1006"],
        },
        {"roster_id": 2, "owner_id": USER_2, "league_id": LEAGUE_A},
        {
            "roster_id": 3,
            "owner_id": None,
            "league_id": LEAGUE_A,
            "players": None,
            "starters": None,
            "reserve": None,
        },
        {"roster_id": 4, "owner_id": USER_4, "league_id": LEAGUE_A},
        {"roster_id": 5, "owner_id": USER_5, "league_id": LEAGUE_A},
        {"roster_id": 6, "owner_id": USER_6, "league_id": LEAGUE_A},
    ],
    LEAGUE_B: [
        {
            "roster_id": 1,
            "owner_id": USER_1,
            "league_id": LEAGUE_B,
            "players": ["2001"],
            "starters": ["2001"],
            "reserve": None,
        },
    ],
}

# Actual points so far this week, keyed as Sleeper does. Roster 1 isn't first,
# so taking the first entry fails; 1007's whole-number 0 must come back as 0.0;
# roster 3 has no entry at all.
MATCHUPS = {
    LEAGUE_A: [
        {"roster_id": 2, "matchup_id": 1, "points": 0.0, "players_points": {}},
        {
            "roster_id": 1,
            "matchup_id": 1,
            "points": 9.5,
            "players_points": {
                "1001": 9.5,
                "1002": 0.0,
                "1003": 0.0,
                "1004": 0.0,
                "1005": 4.0,
                "1006": 11.2,
                "1007": 0,
                "1008": 0.0,
                "1009": 0.0,
            },
        },
        {"roster_id": 4, "matchup_id": 2, "points": 0.0, "players_points": {}},
    ],
    LEAGUE_B: [
        {
            "roster_id": 1,
            "matchup_id": 1,
            "points": 0.0,
            "players_points": {"2001": 0.0},
        },
    ],
}

USER_ROWS = [
    {
        "league_id": LEAGUE_A,
        "user_id": USER_1,
        "display_name": "brad",
        "team_name": " Bravo Ballers ",
        "avatar": AVATAR_A,
    },
    # An avatar that isn't a Sleeper upload is never passed on.
    {
        "league_id": LEAGUE_A,
        "user_id": USER_2,
        "display_name": "ann",
        "team_name": "alpha squad",
        "avatar": "https://example.com/uploads/0a1b2c.jpg",
    },
    # No avatar attribute: a row stored before the batch added avatars.
    {
        "league_id": LEAGUE_A,
        "user_id": USER_4,
        "display_name": "Dana",
        "team_name": "   ",
    },
    {
        "league_id": LEAGUE_A,
        "user_id": USER_5,
        "display_name": "   ",
        "team_name": None,
        "avatar": None,
    },
    # Left the league: a row but no roster, so never listed.
    {
        "league_id": LEAGUE_A,
        "user_id": USER_7,
        "display_name": "gus",
        "team_name": "Ghost Team",
        "avatar": None,
    },
    # Same user in the other league, with a different team name and avatar.
    {
        "league_id": LEAGUE_B,
        "user_id": USER_1,
        "display_name": "brad",
        "team_name": "Bravo B-Team",
        "avatar": AVATAR_B,
    },
]


def player_row(player_id, first, last, position, team, injury_status=None, **extra):
    """A players-table row; extra holds optional attributes such as shirt_number."""
    return {
        "player_id": player_id,
        "first_name": first,
        "last_name": last,
        "position": position,
        "team": team,
        "injury_status": injury_status,
        "refreshed_at": "2026-10-11T03:00:00+00:00",
        **extra,
    }


# 1003 has no row (signed after the batch run). Shirt numbers are Decimals, as
# DynamoDB returns them. 1004 wears 0, which must survive as 0, not None; 1007's
# row predates shirt numbers (no attribute); 1008's is stored as null.
PLAYER_ROWS = {
    "1001": player_row("1001", "Quinn", "Back", "QB", "KC", shirt_number=Decimal(15)),
    "1002": player_row("1002", "Ray", "Byeweek", "RB", "PHI", shirt_number=Decimal(22)),
    "1004": player_row(
        "1004", " Wade ", " Receiver ", "WR", "NYG", "", shirt_number=Decimal(0)
    ),
    "1005": player_row("1005", "Ted", "Endly", "TE", "LV", shirt_number=Decimal(87)),
    "1006": player_row(
        "1006", "Ira", "Reserve", "RB", "NE", "IR", shirt_number=Decimal(31)
    ),
    "1007": player_row("1007", "Otto", "Out", "WR", "BUF", "Out"),
    "1008": player_row("1008", "Kurt", "Freeagent", "K", None, shirt_number=None),
    "1009": player_row("1009", "Cal", "Celled", "WR", "MIA", shirt_number=Decimal(11)),
    "2001": player_row("2001", "Bea", "Other", "TE", "DAL", shirt_number=Decimal(85)),
}

# Missing IDs get Sleeper's null (bye, Out, IR).
PROJECTIONS = {
    "1001": {"stats": {"pts_ppr": 21.4, "pts_std": 18.0}},
    "1003": {"stats": {"pts_ppr": 5.5}},
    "1004": {"stats": {"pts_ppr": 12}},
    "1005": {"stats": {"pts_ppr": 8.25}},
    "1009": {"stats": {"pts_ppr": 3.1}},
}


# --- Helpers -------------------------------------------------------------------


def respond(payload, status=200):
    """A response with a streamed body (pre-loaded bodies break .elapsed)."""
    return httpx.Response(status, stream=httpx.ByteStream(json.dumps(payload).encode()))


def make_client(status, payload):
    """A fake Sleeper client that returns the same response for every request."""
    body = json.dumps(payload).encode()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(status, stream=httpx.ByteStream(body))
    )
    return httpx.Client(transport=transport, base_url="https://sleeper.test")


def make_handler_client(handler):
    """A fake Sleeper client whose responses come from handler(request)."""
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport, base_url="https://sleeper.test")


def assert_502(exc_info):
    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "Sleeper request failed"


def warnings_in(caplog):
    return [r for r in caplog.records if r.levelno == logging.WARNING]


def errors_in(caplog):
    return [r for r in caplog.records if r.levelno == logging.ERROR]


def assert_no_ids(response):
    """No league or user ID, and no ID field names, anywhere in the response."""
    for secret in SECRET_IDS:
        assert secret not in response.text
    for field in ("league_id", "user_id", "owner_id"):
        assert field not in response.text


def requested_ids(call):
    return [key["player_id"] for key in call[PLAYERS_TABLE]["Keys"]]


# --- Fakes ---------------------------------------------------------------------


class FakeSleeper:
    """Routes each request by URL to canned Sleeper data.

    Tests change the attributes before making requests: `failing` holds URL
    substrings that get a 500, `delays` holds seconds to wait per player ID.
    """

    def __init__(self):
        self.state = copy.deepcopy(STATE)
        self.schedule = copy.deepcopy(SCHEDULE)
        self.leagues = copy.deepcopy(LEAGUES)
        self.rosters = copy.deepcopy(ROSTERS)
        self.matchups = copy.deepcopy(MATCHUPS)
        self.projections: dict[str, dict[str, dict[str, float]] | None] = copy.deepcopy(
            PROJECTIONS
        )
        self.failing: set[str] = set()
        self.delays: dict[str, float] = {}
        self.requests: list[str] = []
        self.completed: list[str] = []  # projection IDs, in the order answered

    def client(self):
        transport = httpx.MockTransport(self.handle)
        return httpx.Client(transport=transport, base_url=BASE_URL)

    def handle(self, request):
        url = str(request.url)
        self.requests.append(url)
        if any(part in url for part in self.failing):
            return httpx.Response(500)

        path = request.url.path
        if path.endswith("/state/nfl"):
            return respond(self.state)
        if path.startswith("/schedule/nfl/"):
            return respond(self.schedule)
        if path.startswith("/projections/nfl/player/"):
            player_id = path.rsplit("/", 1)[1]
            time.sleep(self.delays.get(player_id, 0))
            self.completed.append(player_id)
            return respond(self.projections.get(player_id))
        if match := re.search(r"/league/(\d+)/matchups/\d+$", path):
            league_id = match.group(1)
            if league_id in self.matchups:
                return respond(self.matchups[league_id])
        elif match := re.search(r"/league/(\d+)/rosters$", path):
            league_id = match.group(1)
            if league_id in self.rosters:
                return respond(self.rosters[league_id])
        elif match := re.search(r"/league/(\d+)$", path):
            league_id = match.group(1)
            if league_id in self.leagues:
                return respond(self.leagues[league_id])
        return httpx.Response(404)


class FakeDynamoDB:
    """A DynamoDB resource with only batch_get_item, answering from `players`.

    `hold_back` maps a player ID to how many calls it comes back in
    UnprocessedKeys before it's returned. Set `error` to make every call fail.
    """

    def __init__(self, players, hold_back=None):
        self.players = players
        self.hold_back = dict(hold_back or {})
        self.error: Exception | None = None
        self.calls: list[dict] = []

    def batch_get_item(self, **kwargs):
        if self.error is not None:
            raise self.error
        request_items = copy.deepcopy(kwargs["RequestItems"])
        self.calls.append(request_items)
        responses, unprocessed = {}, {}
        for table_name, spec in request_items.items():
            found, held = [], []
            for key in spec["Keys"]:
                player_id = key["player_id"]
                if self.hold_back.get(player_id, 0) > 0:
                    self.hold_back[player_id] -= 1
                    held.append(key)
                elif player_id in self.players:
                    found.append(copy.deepcopy(self.players[player_id]))
            responses[table_name] = found
            if held:
                unprocessed[table_name] = {**spec, "Keys": held}
        return {"Responses": responses, "UnprocessedKeys": unprocessed}


class FakeUsersTable:
    """A users table with only query, returning the requested league's rows."""

    name = "users-test"

    def __init__(self, rows):
        self.rows = rows
        self.queries: list[dict] = []

    def query(self, **kwargs):
        self.queries.append(kwargs)
        condition = kwargs["KeyConditionExpression"].get_expression()
        attribute, league_id = condition["values"]
        assert (attribute.name, condition["operator"]) == ("league_id", "=")
        return {"Items": [r for r in self.rows if r["league_id"] == league_id]}


@pytest.fixture
def sleeper():
    return FakeSleeper()


@pytest.fixture
def dynamodb():
    return FakeDynamoDB(PLAYER_ROWS)


@pytest.fixture
def users_table():
    return FakeUsersTable(USER_ROWS)


@pytest.fixture
def api(sleeper, dynamodb, users_table):
    """A TestClient with every dependency swapped for a fake."""

    def sleeper_client():
        with sleeper.client() as client:
            yield client

    tables = Tables(players=SimpleNamespace(name=PLAYERS_TABLE), users=users_table)  # type: ignore
    main.app.dependency_overrides.update(
        {
            main.get_config: lambda: FAKE_CONFIG,
            main.get_dynamodb: lambda: dynamodb,
            main.get_tables: lambda: tables,
            main.get_sleeper_client: sleeper_client,
        }
    )
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


@pytest.fixture
def sleeps(monkeypatch):
    """Record get_players' retry delays instead of sleeping."""
    delays = []
    monkeypatch.setattr(main.time, "sleep", delays.append)
    return delays


# --- clean_str -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("KC", "KC", id="kept"),
        pytest.param("  KC  ", "KC", id="stripped"),
        pytest.param("", None, id="empty"),
        pytest.param("   ", None, id="whitespace-only"),
        pytest.param(None, None, id="none"),
        pytest.param(7, None, id="int"),
        pytest.param(True, None, id="bool"),
        pytest.param(["KC"], None, id="list"),
    ],
)
def test_clean_str(value, expected):
    assert clean_str(value) == expected


# --- clean_int -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param(Decimal(15), 15, id="decimal"),
        pytest.param(Decimal(0), 0, id="decimal-zero"),
        pytest.param(Decimal("7.0"), 7, id="decimal-whole-with-point"),
        pytest.param(7, 7, id="int"),
        pytest.param(Decimal("7.5"), None, id="decimal-fraction"),
        pytest.param(Decimal("NaN"), None, id="decimal-nan"),
        pytest.param(Decimal("Infinity"), None, id="decimal-infinity"),
        pytest.param(7.0, None, id="float"),
        pytest.param("15", None, id="string"),
        pytest.param(True, None, id="bool"),
        pytest.param(None, None, id="none"),
    ],
)
def test_clean_int(value, expected):
    result = clean_int(value)

    assert result == expected
    if expected is not None:
        assert type(result) is int  # Decimal(15) == 15, so == alone can't prove int()


# --- avatar_path ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param(AVATAR_A, "/avatars/0a1b2c.jpg", id="jpg"),
        pytest.param(AVATAR_B, "/avatars/3d4e5f.jpeg", id="jpeg"),
        pytest.param("https://example.com/uploads/0a1b2c.jpg", None, id="other-host"),
        pytest.param(
            "https://sleepercdn.com/uploads/../0a1b2c.jpg", None, id="traversal"
        ),
        pytest.param("", None, id="empty"),
        pytest.param(None, None, id="none"),
    ],
)
def test_avatar_path(value, expected):
    assert avatar_path(value) == expected


# --- describe_game -------------------------------------------------------------

GAMES = {
    "KC": WeekGame(opponent="LV", status="in_game"),
    "LV": WeekGame(opponent="KC", status="in_game"),
    "NE": WeekGame(opponent="BUF", status="canceled"),
}


@pytest.mark.parametrize(
    ("team", "games", "expected"),
    [
        pytest.param("KC", GAMES, ("LV", "in_game"), id="home"),
        pytest.param("LV", GAMES, ("KC", "in_game"), id="away"),
        pytest.param("NE", GAMES, ("BUF", "canceled"), id="canceled-passed-on"),
        pytest.param("DAL", GAMES, (None, "bye"), id="bye"),
        pytest.param(None, GAMES, (None, None), id="no-team"),
        pytest.param("KC", {}, (None, None), id="no-games-not-a-bye"),
        pytest.param(None, {}, (None, None), id="neither"),
    ],
)
def test_describe_game(team, games, expected):
    assert describe_game(team, games) == expected


# --- get_nfl_week --------------------------------------------------------------


@pytest.mark.parametrize(
    "state",
    [
        pytest.param(STATE, id="display_week-not-week"),
        pytest.param(
            {"season": " 2026 ", "season_type": " regular ", "display_week": 5},
            id="whitespace-stripped",
        ),
    ],
)
def test_get_nfl_week(state):
    with make_client(200, state) as client:
        assert get_nfl_week(client) == NflWeek("2026", 5, "regular")


@pytest.mark.parametrize(
    "state",
    [
        pytest.param({**STATE, "display_week": True}, id="week-bool"),
        pytest.param({**STATE, "display_week": "5"}, id="week-string"),
        pytest.param({**STATE, "display_week": 5.0}, id="week-float"),
        pytest.param({**STATE, "display_week": None}, id="week-null"),
        pytest.param({**STATE, "season": ""}, id="season-empty"),
        pytest.param({**STATE, "season": 2026}, id="season-int"),
        pytest.param({**STATE, "season_type": "   "}, id="season_type-blank"),
        pytest.param({"season": "2026", "season_type": "regular"}, id="no-week"),
        pytest.param([STATE], id="not-a-dict"),
    ],
)
def test_get_nfl_week_bad_state_raises_502(state):
    with (
        make_client(200, state) as client,
        pytest.raises(HTTPException) as exc_info,
    ):
        get_nfl_week(client)

    assert_502(exc_info)


# --- get_week_games ------------------------------------------------------------


def test_get_week_games_builds_url_from_nfl_week(sleeper):
    with sleeper.client() as client:
        get_week_games(client, NflWeek("2026", 2, "post"))

    assert sleeper.requests == ["https://api.sleeper.com/schedule/nfl/post/2026"]


def test_get_week_games_maps_both_teams_for_this_week_only(caplog):
    schedule = [
        {"week": 5, "home": "KC", "away": "LV", "status": "in_game"},
        {"week": 5, "home": " NYG ", "away": "DAL", "status": " pre_game "},
        {"week": 4, "home": "PHI", "away": "DAL", "status": "complete"},
    ]
    with make_client(200, schedule) as client:
        games = get_week_games(client, WEEK)

    assert games == {
        "KC": WeekGame("LV", "in_game"),
        "LV": WeekGame("KC", "in_game"),
        "NYG": WeekGame("DAL", "pre_game"),
        "DAL": WeekGame("NYG", "pre_game"),
    }
    assert not warnings_in(caplog)


def test_get_week_games_skips_malformed_games_with_one_warning(caplog):
    # Only the week-5 item without an away team counts as skipped: non-dicts
    # and other weeks are ignored silently.
    schedule = [
        None,
        "x",
        {"week": 5, "home": "KC", "away": None, "status": "pre_game"},
        {"week": 5, "home": "KC", "away": "LV", "status": "pre_game"},
        {"week": 4, "home": "", "away": "", "status": ""},
    ]
    with make_client(200, schedule) as client:
        games = get_week_games(client, WEEK)

    assert games == {
        "KC": WeekGame("LV", "pre_game"),
        "LV": WeekGame("KC", "pre_game"),
    }
    warnings = warnings_in(caplog)
    assert len(warnings) == 1
    assert "Skipped 1" in warnings[0].getMessage()


def test_get_week_games_with_no_games_warns_naming_the_week(caplog):
    with make_client(200, SCHEDULE) as client:
        games = get_week_games(client, NflWeek("2026", 7, "regular"))

    assert games == {}
    warnings = warnings_in(caplog)
    assert len(warnings) == 1
    assert "week=7" in warnings[0].getMessage()


def test_get_week_games_non_list_raises_502():
    with (
        make_client(200, {"games": SCHEDULE}) as client,
        pytest.raises(HTTPException) as exc_info,
    ):
        get_week_games(client, WEEK)

    assert_502(exc_info)


# --- get_projection ------------------------------------------------------------


def test_get_projection_builds_url_from_nfl_week():
    # A post-season week, so a hard-coded "regular" would fail the test.
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, stream=httpx.ByteStream(b"null"))

    with make_handler_client(handler) as client:
        get_projection(client, NflWeek("2026", 2, "post"), PLAYER_ID)

    expected = (
        "https://api.sleeper.com/projections/nfl/player/3634"
        "?season_type=post&season=2026&week=2"
    )
    assert seen == [expected]


def test_get_projection_null_returns_none_without_warning(caplog):
    # Sleeper's null (bye, Out, IR, unknown ID) is normal, not a data problem.
    with make_client(200, None) as client:
        assert get_projection(client, WEEK, PLAYER_ID) is None

    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({}, id="no-stats-key"),
        pytest.param({"stats": None}, id="stats-null"),
        pytest.param({"stats": []}, id="stats-not-dict"),
        pytest.param({"stats": {}}, id="no-pts_ppr-key"),
        pytest.param({"stats": {"pts_ppr": None}}, id="pts_ppr-null"),
        pytest.param({"stats": {"pts_ppr": "7.6"}}, id="pts_ppr-string"),
        pytest.param({"stats": {"pts_ppr": True}}, id="pts_ppr-bool"),
        pytest.param({"stats": {"pts_std": 4.6}}, id="other-scoring-only"),
    ],
)
def test_get_projection_without_usable_points_returns_none_and_warns(payload, caplog):
    with make_client(200, payload) as client:
        assert get_projection(client, WEEK, PLAYER_ID) is None

    warnings = warnings_in(caplog)
    assert len(warnings) == 1
    # The optimiser treats this None as 0, so the warning must name the player.
    assert PLAYER_ID in warnings[0].getMessage()


@pytest.mark.parametrize(
    ("points", "expected"),
    [
        pytest.param(7.6, 7.6, id="float"),
        pytest.param(7, 7.0, id="int-converted"),
        pytest.param(0, 0.0, id="zero-is-a-projection"),
        pytest.param(-1.5, -1.5, id="negative"),
    ],
)
def test_get_projection_returns_ppr_points_as_float(points, expected, caplog):
    # The other scoring formats are present, so this proves pts_ppr is used.
    payload = {"stats": {"pts_std": 4.6, "pts_half_ppr": 6.1, "pts_ppr": points}}
    with make_client(200, payload) as client:
        result = get_projection(client, WEEK, PLAYER_ID)

    assert type(result) is float  # 7 == 7.0, so == alone can't prove float()
    assert result == expected
    assert not warnings_in(caplog)


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param([1, 2], id="list"),
        pytest.param([], id="empty-list"),
        pytest.param("x", id="string"),
        pytest.param("", id="empty-string"),
        pytest.param(7, id="int"),
        pytest.param(0, id="zero"),
        pytest.param(True, id="bool"),
    ],
)
def test_get_projection_non_dict_raises_502(payload, caplog):
    # The falsy cases ([], "", 0) catch an `if not proj_data` refactor,
    # which would quietly return None for them.
    with (
        make_client(200, payload) as client,
        pytest.raises(HTTPException) as exc_info,
    ):
        get_projection(client, WEEK, PLAYER_ID)

    assert_502(exc_info)
    assert any(r.levelno == logging.ERROR for r in caplog.records)


def test_get_projection_http_error_raises_502():
    with (
        make_client(500, None) as client,
        pytest.raises(HTTPException) as exc_info,
    ):
        get_projection(client, WEEK, PLAYER_ID)

    assert_502(exc_info)


def test_get_projection_invalid_json_raises_502():
    def handler(request):
        return httpx.Response(200, stream=httpx.ByteStream(b"not json"))

    with (
        make_handler_client(handler) as client,
        pytest.raises(HTTPException) as exc_info,
    ):
        get_projection(client, WEEK, PLAYER_ID)

    assert_502(exc_info)


def test_get_projection_timeout_raises_502():
    def handler(request):
        raise httpx.ReadTimeout("timed out", request=request)

    with (
        make_handler_client(handler) as client,
        pytest.raises(HTTPException) as exc_info,
    ):
        get_projection(client, WEEK, PLAYER_ID)

    assert_502(exc_info)


# --- get_projections -----------------------------------------------------------


def test_get_projections_empty_list_makes_no_requests(sleeper):
    with sleeper.client() as client:
        assert get_projections(client, WEEK, []) == {}

    assert sleeper.requests == []


def test_get_projections_pairs_results_with_ids_when_finished_out_of_order(
    sleeper: FakeSleeper,
):
    # 20 IDs: more than MAX_PROJECTION_WORKERS (16), so two rounds. Earlier IDs
    # wait longer, so answers come back roughly in reverse.
    ids = [f"30{n:02d}" for n in range(20)]
    sleeper.projections = {
        pid: {"stats": {"pts_ppr": n + 0.5}} for n, pid in enumerate(ids)
    }
    sleeper.projections["3007"] = None  # Sleeper's null
    sleeper.delays = {pid: (20 - n) * 0.005 for n, pid in enumerate(ids)}
    expected: dict[str, float | None] = {pid: n + 0.5 for n, pid in enumerate(ids)}
    expected["3007"] = None

    with sleeper.client() as client:
        result = get_projections(client, WEEK, ids)

    assert sleeper.completed != ids  # the threads really did finish out of order
    assert result == expected
    assert list(result) == ids


def test_get_projections_one_failure_raises_502(sleeper):
    ids = [f"30{n:02d}" for n in range(5)]
    sleeper.failing = {"/player/3003"}

    with (
        sleeper.client() as client,
        pytest.raises(HTTPException) as exc_info,
    ):
        get_projections(client, WEEK, ids)

    assert_502(exc_info)


# --- get_players ---------------------------------------------------------------


def test_get_players_empty_list_makes_no_request(dynamodb):
    assert get_players(dynamodb, PLAYERS_TABLE, []) == {}
    assert dynamodb.calls == []


def test_get_players_returns_rows_by_id_and_sends_each_key_once(dynamodb):
    result = get_players(dynamodb, PLAYERS_TABLE, ["1001", "1001", "1003", "1004"])

    # 1003 has no row: absent from the result, not an error.
    assert result == {"1001": PLAYER_ROWS["1001"], "1004": PLAYER_ROWS["1004"]}
    assert len(dynamodb.calls) == 1
    assert requested_ids(dynamodb.calls[0]) == ["1001", "1003", "1004"]


def test_get_players_retries_unprocessed_keys(sleeps, caplog):
    dynamodb = FakeDynamoDB(PLAYER_ROWS, hold_back={"1004": 1})

    result = get_players(dynamodb, PLAYERS_TABLE, ["1001", "1004"])  # type: ignore

    assert set(result) == {"1001", "1004"}
    assert len(dynamodb.calls) == 2
    assert requested_ids(dynamodb.calls[1]) == ["1004"]  # only the leftover
    assert sleeps == [pytest.approx(0.2)]
    assert not warnings_in(caplog)


def test_get_players_gives_up_after_max_attempts(sleeps, caplog):
    dynamodb = FakeDynamoDB(PLAYER_ROWS, hold_back={"1004": 99})

    result = get_players(dynamodb, PLAYERS_TABLE, ["1001", "1004"])  # type: ignore

    assert set(result) == {"1001"}
    assert len(dynamodb.calls) == 3
    assert sleeps == [pytest.approx(0.2), pytest.approx(0.4)]
    assert len(warnings_in(caplog)) == 1


def test_get_players_single_attempt_warns_about_leftovers(sleeps, caplog):
    dynamodb = FakeDynamoDB(PLAYER_ROWS, hold_back={"1004": 1})

    result = get_players(dynamodb, PLAYERS_TABLE, ["1001", "1004"], max_attempts=1)  # type: ignore

    assert set(result) == {"1001"}
    assert len(dynamodb.calls) == 1
    assert sleeps == []
    assert len(warnings_in(caplog)) == 1


# --- get_roster_positions ------------------------------------------------------


def test_get_roster_positions_returns_the_leagues_layout():
    assert get_roster_positions(LEAGUES[LEAGUE_A]) == LAYOUT_A


@pytest.mark.parametrize(
    "league",
    [
        pytest.param({"name": "x"}, id="missing"),
        pytest.param({"roster_positions": None}, id="null"),
        pytest.param({"roster_positions": "QB,RB"}, id="string"),
        pytest.param({"roster_positions": {"QB": 1}}, id="dict"),
        pytest.param({"roster_positions": ["QB", 3, "RB"]}, id="int-item"),
        pytest.param({"roster_positions": ["QB", None]}, id="null-item"),
    ],
)
def test_get_roster_positions_bad_shape_raises_502(league, caplog):
    with pytest.raises(HTTPException) as exc_info:
        get_roster_positions(league)

    assert_502(exc_info)
    assert errors_in(caplog)


# --- get_actual_points ---------------------------------------------------------


def test_get_actual_points_finds_the_team_and_returns_floats(sleeper, caplog):
    with sleeper.client() as client:
        actual = get_actual_points(client, LEAGUE_A, 5, 1)

    assert sleeper.requests == [f"{BASE_URL}/league/{LEAGUE_A}/matchups/5"]
    assert actual == {
        "1001": 9.5,
        "1002": 0.0,
        "1003": 0.0,
        "1004": 0.0,
        "1005": 4.0,
        "1006": 11.2,
        "1007": 0.0,
        "1008": 0.0,
        "1009": 0.0,
    }
    assert all(type(points) is float for points in actual.values())  # 1007's 0
    assert not warnings_in(caplog)


def test_get_actual_points_skips_items_that_are_not_dicts():
    matchups = [None, "x", 7, {"roster_id": 1, "players_points": {"1001": 2.5}}]
    with make_client(200, matchups) as client:
        assert get_actual_points(client, LEAGUE_A, 5, 1) == {"1001": 2.5}


@pytest.mark.parametrize(
    "matchups",
    [
        pytest.param([], id="no-entries"),
        pytest.param(
            [{"roster_id": 2, "players_points": {"1001": 2.5}}], id="other-teams-only"
        ),
        pytest.param(
            [{"roster_id": "1", "players_points": {"1001": 2.5}}], id="id-as-string"
        ),
    ],
)
def test_get_actual_points_without_the_teams_entry_returns_empty_and_warns(
    matchups, caplog
):
    with make_client(200, matchups) as client:
        assert get_actual_points(client, LEAGUE_A, 5, 1) == {}

    assert len(warnings_in(caplog)) == 1


@pytest.mark.parametrize("value", [None, [], "x", 7])
def test_get_actual_points_players_points_not_a_dict_raises_502(value, caplog):
    matchups = [{"roster_id": 1, "players_points": value}]
    with (
        make_client(200, matchups) as client,
        pytest.raises(HTTPException) as exc_info,
    ):
        get_actual_points(client, LEAGUE_A, 5, 1)

    assert_502(exc_info)
    assert errors_in(caplog)


def test_get_actual_points_non_list_raises_502():
    with (
        make_client(200, {"roster_id": 1, "players_points": {}}) as client,
        pytest.raises(HTTPException) as exc_info,
    ):
        get_actual_points(client, LEAGUE_A, 5, 1)

    assert_502(exc_info)


@pytest.mark.parametrize("value", ["7.2", True, None, [1]])
def test_get_actual_points_unusable_value_becomes_none_and_warns(value, caplog):
    # True is an int to isinstance, so it needs its own rejection.
    matchups = [{"roster_id": 1, "players_points": {"1001": value, "1002": 3}}]
    with make_client(200, matchups) as client:
        actual = get_actual_points(client, LEAGUE_A, 5, 1)

    assert actual == {"1001": None, "1002": 3.0}
    warnings = warnings_in(caplog)
    assert len(warnings) == 1
    assert "1001" in warnings[0].getMessage()


# --- GET /api/health -----------------------------------------------------------


def test_health_needs_no_config_or_aws():
    # No overrides: health must work before the Lambda has LEAGUE_IDS.
    response = TestClient(main.app).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# --- GET /api/leagues ----------------------------------------------------------


def test_list_leagues(api):
    response = api.get("/api/leagues")

    assert response.status_code == 200
    assert response.json() == [
        {"key": 0, "name": "Test League A"},
        {"key": 1, "name": "League 2"},  # blank name: fallback uses key + 1
    ]
    assert_no_ids(response)


# --- GET /api/leagues/{league_key}/teams ---------------------------------------


def test_list_teams_names_and_order(api):
    response = api.get("/api/leagues/0/teams")

    assert response.status_code == 200
    # Case-insensitive order: plain sorting would put "Bravo" before "alpha".
    assert response.json() == [
        {"roster_id": 2, "team_name": "alpha squad", "avatar": None},  # not Sleeper's
        {
            "roster_id": 1,
            "team_name": "Bravo Ballers",  # stripped
            "avatar": "/avatars/0a1b2c.jpg",
        },
        {"roster_id": 3, "team_name": "Team 3", "avatar": None},  # no owner
        # blank team and display name; avatar stored as null
        {"roster_id": 5, "team_name": "Team 5", "avatar": None},
        # owner has no users row yet
        {"roster_id": 6, "team_name": "Team 6", "avatar": None},
        # blank team name; row stored before avatars, so no attribute
        {"roster_id": 4, "team_name": "Team Dana", "avatar": None},
    ]
    assert "Ghost Team" not in response.text  # a users row without a roster
    assert_no_ids(response)


def test_list_teams_never_returns_sleepers_avatar_urls(api):
    # Only the site's own /avatars/ path, so browsers never contact Sleeper.
    response = api.get("/api/leagues/0/teams")

    assert "sleepercdn" not in response.text
    assert "example.com" not in response.text


def test_list_teams_uses_the_selected_leagues_users(api):
    response = api.get("/api/leagues/1/teams")

    assert response.json() == [
        {"roster_id": 1, "team_name": "Bravo B-Team", "avatar": "/avatars/3d4e5f.jpeg"}
    ]


# --- GET /api/leagues/{league_key}/teams/{roster_id}/roster --------------------

ROSTER_URL = "/api/leagues/0/teams/1/roster"


def test_get_roster_players(api, dynamodb):
    response = api.get(ROSTER_URL)

    assert response.status_code == 200
    body = response.json()
    assert (body["season"], body["week"]) == ("2026", 5)
    assert len(body["players"]) == len(MAIN_ROSTER_PLAYERS)
    summary = {
        p["player_id"]: (
            p["starter_slot"],
            p["reserve"],
            p["team"],
            p["projected_points"],
            p["opponent"],
            p["game_status"],
            p["locked"],
        )
        for p in body["players"]
    }
    # slot, reserve, team, points, opponent, game_status, locked
    assert summary == {
        "1001": (0, False, "KC", 21.4, "LV", "in_game", True),  # live starter
        "1002": (2, False, "PHI", None, None, "bye", False),
        "1003": (3, False, None, 5.5, None, None, False),  # no DynamoDB row
        "1004": (4, False, "NYG", 12.0, "DAL", "pre_game", False),
        "1005": (None, False, "LV", 8.25, "KC", "in_game", True),  # locked bench
        "1006": (None, True, "NE", None, "BUF", "complete", True),  # IR
        "1007": (None, False, "BUF", None, "NE", "complete", True),  # Out
        "1008": (None, False, None, None, None, None, False),  # free agent
        "1009": (5, False, "MIA", 3.1, "NYJ", "canceled", False),
    }
    assert list(dynamodb.calls[0]) == [PLAYERS_TABLE]
    assert_no_ids(response)


def test_get_roster_player_fields(api):
    players = {p["player_id"]: p for p in api.get(ROSTER_URL).json()["players"]}

    # Exactly the model's fields (no refreshed_at), with details cleaned.
    assert players["1004"] == {
        "player_id": "1004",
        "starter_slot": 4,
        "reserve": False,
        "first_name": "Wade",
        "last_name": "Receiver",
        "shirt_number": 0,
        "position": "WR",
        "team": "NYG",
        "injury_status": None,
        "projected_points": 12.0,
        "opponent": "DAL",
        "game_status": "pre_game",
        "locked": False,
        "actual_points": 0.0,
    }
    assert players["1003"] == {
        "player_id": "1003",
        "starter_slot": 3,
        "reserve": False,
        "first_name": None,
        "last_name": None,
        "shirt_number": None,
        "position": None,
        "team": None,
        "injury_status": None,
        "projected_points": 5.5,
        "opponent": None,
        "game_status": None,
        "locked": False,
        "actual_points": 0.0,
    }


def test_get_roster_shirt_numbers(api):
    players = api.get(ROSTER_URL).json()["players"]

    numbers = {p["player_id"]: p["shirt_number"] for p in players}
    assert numbers == {
        "1001": 15,
        "1002": 22,
        "1003": None,  # no DynamoDB row
        "1004": 0,  # a real shirt number, not a missing one
        "1005": 87,
        "1006": 31,
        "1007": None,  # row stored before shirt numbers
        "1008": None,  # stored as null
        "1009": 11,
    }
    # Whole numbers in the JSON (15, not 15.0), so the frontend shows "#15".
    assert '"shirt_number":15,' in api.get(ROSTER_URL).text


def test_get_roster_actual_points(api):
    players = api.get(ROSTER_URL).json()["players"]

    actual = {p["player_id"]: p["actual_points"] for p in players}
    assert actual["1001"] == 9.5  # locked starter, points so far
    assert actual["1005"] == 4.0  # locked bench player
    assert actual["1007"] == 0.0  # Sleeper's whole-number 0
    assert all(type(points) is float for points in actual.values())


def test_get_roster_names(api, users_table):
    response = api.get(ROSTER_URL)

    body = response.json()
    assert body["league_name"] == "Test League A"  # stripped
    assert body["team_name"] == "Bravo Ballers"  # stripped
    assert len(users_table.queries) == 1
    assert_no_ids(response)


@pytest.mark.parametrize(
    ("url", "league_name", "team_name"),
    [
        pytest.param(
            "/api/leagues/1/teams/1/roster",
            "League 2",
            "Bravo B-Team",
            id="blank-league-name-and-the-selected-leagues-users",
        ),
        pytest.param(
            "/api/leagues/0/teams/3/roster", "Test League A", "Team 3", id="no-owner"
        ),
        pytest.param(
            "/api/leagues/0/teams/4/roster",
            "Test League A",
            "Team Dana",
            id="blank-team-name",
        ),
        pytest.param(
            "/api/leagues/0/teams/6/roster",
            "Test League A",
            "Team 6",
            id="no-users-row",
        ),
    ],
)
def test_get_roster_name_fallbacks(api, sleeper, url, league_name, team_name):
    # Rosters 4 and 6 have no players, so their starters list is empty.
    response = api.get(url)

    assert response.status_code == 200
    body = response.json()
    assert (body["league_name"], body["team_name"]) == (league_name, team_name)


@pytest.mark.parametrize(
    ("url", "team_avatar"),
    [
        pytest.param(ROSTER_URL, "/avatars/0a1b2c.jpg", id="sleeper-upload"),
        pytest.param(
            "/api/leagues/1/teams/1/roster",
            "/avatars/3d4e5f.jpeg",
            id="the-selected-leagues-users",
        ),
        pytest.param("/api/leagues/0/teams/2/roster", None, id="not-a-sleeper-upload"),
        pytest.param("/api/leagues/0/teams/3/roster", None, id="no-owner"),
        pytest.param("/api/leagues/0/teams/4/roster", None, id="no-avatar-attribute"),
        pytest.param("/api/leagues/0/teams/5/roster", None, id="avatar-stored-as-null"),
        pytest.param("/api/leagues/0/teams/6/roster", None, id="no-users-row"),
    ],
)
def test_get_roster_team_avatar(api, url, team_avatar):
    response = api.get(url)

    assert response.status_code == 200
    assert response.json()["team_avatar"] == team_avatar
    # Only the site's own /avatars/ path, so browsers never contact Sleeper.
    assert "sleepercdn" not in response.text
    assert "example.com" not in response.text
    assert_no_ids(response)


def test_get_roster_lineup(api):
    response = api.get(ROSTER_URL)

    body = response.json()
    assert body["slots"] == SLOTS_A  # starting slots only, no BN
    lineup = body["lineup"]
    # QB: 1001 is locked, so he keeps slot 0 and counts his 9.5 actual points.
    # RB: 1002 (bye, 0 points) is the only RB; the second RB slot stays empty.
    # WR: 1004, then 1009 (canceled, 0 points) as the only WR left.
    # WRRB_FLEX: nobody eligible is left (1005 is a locked TE, 1008 a K).
    assert lineup["starter_ids"] == ["1001", "1002", None, "1004", "1009", None]
    # Roster order, without 1006 (IR). 1003 has no DynamoDB row, so no
    # position, so the optimiser can't start him.
    assert lineup["bench_ids"] == ["1003", "1005", "1007", "1008"]
    assert lineup["optimal_total"] == pytest.approx(21.5)  # 9.5 + 0 + 12 + 0
    # The current lineup counts 1003's 5.5, which is why it's higher here.
    assert lineup["current_total"] == pytest.approx(27.0)  # 9.5 + 0 + 5.5 + 12 + 0
    assert_no_ids(response)


def test_get_roster_calls_sleeper_in_order(api, sleeper):
    api.get(ROSTER_URL)

    # The league is fetched once, for both its slot layout and its name.
    assert sleeper.requests[:5] == [
        f"{BASE_URL}/league/{LEAGUE_A}/rosters",
        f"{BASE_URL}/league/{LEAGUE_A}",
        f"{BASE_URL}/state/nfl",
        "https://api.sleeper.com/schedule/nfl/regular/2026",
        f"{BASE_URL}/league/{LEAGUE_A}/matchups/5",  # display_week, not week
    ]
    assert all("/projections/" in url for url in sleeper.requests[5:])


def test_get_roster_warns_about_players_missing_from_dynamodb(api, caplog):
    api.get(ROSTER_URL)

    assert any("1003" in r.getMessage() for r in warnings_in(caplog))


def test_get_roster_uses_the_selected_league(api):
    body = api.get("/api/leagues/1/teams/1/roster").json()

    assert [p["player_id"] for p in body["players"]] == ["2001"]
    assert body["slots"] == ["TE"]
    assert body["lineup"]["starter_ids"] == ["2001"]


def test_get_roster_empty_roster(api, sleeper, dynamodb):
    # Roster 3 has players, starters and reserve all null, and no matchup entry.
    response = api.get("/api/leagues/0/teams/3/roster")

    assert response.status_code == 200
    body = response.json()
    assert body["players"] == []
    assert body["lineup"] == {
        "starter_ids": [None] * 6,
        "bench_ids": [],
        "optimal_total": 0.0,
        "current_total": 0.0,
    }
    assert dynamodb.calls == []
    assert not any("/projections/" in url for url in sleeper.requests)


def test_get_roster_empty_starters_list_is_not_a_layout_mismatch(api, sleeper):
    sleeper.rosters[LEAGUE_A][1].update(players=[], starters=[], reserve=[])

    response = api.get("/api/leagues/0/teams/2/roster")

    assert response.status_code == 200
    assert response.json()["lineup"]["starter_ids"] == [None] * 6


def test_get_roster_starters_not_matching_the_layout_is_502(
    api, sleeper, dynamodb, caplog
):
    # Nine starting slots, but roster 1 has six starters.
    real_layout = ["QB", "RB", "RB", "WR", "WR", "TE", "WRRB_FLEX", "K", "DEF"]
    sleeper.leagues[LEAGUE_A]["roster_positions"] = real_layout + ["BN"] * 6

    response = api.get(ROSTER_URL)

    assert response.status_code == 502
    assert response.json() == {"detail": "Sleeper request failed"}
    assert errors_in(caplog)
    assert dynamodb.calls == []


def test_get_roster_bad_layout_is_502_before_the_week_is_fetched(
    api, sleeper, dynamodb
):
    sleeper.leagues[LEAGUE_A]["roster_positions"] = None

    response = api.get(ROSTER_URL)

    assert response.status_code == 502
    assert response.json() == {"detail": "Sleeper request failed"}
    assert not any(url.endswith("/state/nfl") for url in sleeper.requests)
    assert dynamodb.calls == []


def test_get_roster_league_not_a_dict_is_502_before_the_week_is_fetched(
    api, sleeper, dynamodb
):
    sleeper.leagues[LEAGUE_A] = [LAYOUT_A]  # type: ignore

    response = api.get(ROSTER_URL)

    assert response.status_code == 502
    assert response.json() == {"detail": "Sleeper request failed"}
    assert not any(url.endswith("/state/nfl") for url in sleeper.requests)
    assert dynamodb.calls == []


def test_get_roster_known_slot_types_do_not_warn(api, caplog):
    api.get(ROSTER_URL)

    # The only expected warning is the one about 1003's missing row.
    assert [
        r.getMessage() for r in warnings_in(caplog) if "1003" not in r.getMessage()
    ] == []


def test_get_roster_unknown_slot_type_warns_and_stays_empty(api, sleeper, caplog):
    layout = [s if s != "WRRB_FLEX" else "IDP_FLEX" for s in LAYOUT_A]
    sleeper.leagues[LEAGUE_A]["roster_positions"] = layout

    response = api.get(ROSTER_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["slots"][5] == "IDP_FLEX"
    assert body["lineup"]["starter_ids"][5] is None
    assert any("IDP_FLEX" in r.getMessage() for r in warnings_in(caplog))


def test_get_roster_without_a_matchup_entry_still_answers(api, sleeper, caplog):
    sleeper.matchups[LEAGUE_A] = []

    response = api.get(ROSTER_URL)

    assert response.status_code == 200
    body = response.json()
    assert all(p["actual_points"] is None for p in body["players"])
    # The locked QB's points are unknown, so he counts 0.
    assert body["lineup"]["optimal_total"] == pytest.approx(12.0)
    assert body["lineup"]["current_total"] == pytest.approx(17.5)
    # A warning about the matchup, besides the usual one about 1003's row.
    assert any("1003" not in r.getMessage() for r in warnings_in(caplog))


def test_get_roster_failing_matchups_is_502_before_dynamodb(api, sleeper, dynamodb):
    sleeper.failing = {"/matchups/"}

    response = api.get(ROSTER_URL)

    assert response.status_code == 502
    assert response.json() == {"detail": "Sleeper request failed"}
    assert dynamodb.calls == []


def test_get_roster_unknown_team_is_404_before_any_other_call(
    api, sleeper, dynamodb, users_table
):
    response = api.get("/api/leagues/0/teams/99/roster")

    assert response.status_code == 404
    assert response.json() == {"detail": "Team not found"}
    assert len(sleeper.requests) == 1  # the rosters fetch only
    assert dynamodb.calls == []
    assert users_table.queries == []


def test_get_roster_one_failing_projection_is_502(api, sleeper):
    sleeper.failing = {"/player/1005"}

    response = api.get(ROSTER_URL)

    assert response.status_code == 502
    assert response.json() == {"detail": "Sleeper request failed"}


def test_get_roster_dynamodb_failure_spends_no_projection_calls(api, sleeper, dynamodb):
    dynamodb.error = RuntimeError("DynamoDB unavailable")
    client = TestClient(main.app, raise_server_exceptions=False)

    response = client.get(ROSTER_URL)

    assert response.status_code == 500
    assert not any("/projections/" in url for url in sleeper.requests)


# --- Errors shared by the routes -----------------------------------------------


@pytest.mark.parametrize("league_key", [2, -1])
@pytest.mark.parametrize(
    "url", ["/api/leagues/{}/teams", "/api/leagues/{}/teams/1/roster"]
)
def test_unknown_league_is_404_without_calling_sleeper(api, sleeper, url, league_key):
    response = api.get(url.format(league_key))

    assert response.status_code == 404
    assert response.json() == {"detail": "League not found"}
    assert sleeper.requests == []


@pytest.mark.parametrize(
    "url",
    [
        "/api/leagues/abc/teams",
        "/api/leagues/abc/teams/1/roster",
        "/api/leagues/0/teams/abc/roster",
    ],
)
def test_non_integer_path_parameter_is_422(api, url):
    assert api.get(url).status_code == 422


@pytest.mark.parametrize("url", ["/api/leagues", "/api/leagues/0/teams", ROSTER_URL])
def test_sleeper_down_is_502_with_fixed_detail(api, sleeper, url):
    sleeper.failing = {"https://"}  # every request

    response = api.get(url)

    assert response.status_code == 502
    assert response.json() == {"detail": "Sleeper request failed"}
