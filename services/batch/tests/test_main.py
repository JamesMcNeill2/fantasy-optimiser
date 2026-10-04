import json
from pathlib import Path

import httpx
import pytest

from app.main import ConfigError, fetch_json, load_config, player_items, user_items

FIXTURES = Path(__file__).parent / "fixtures"
REFRESHED_AT = "2026-10-04T08:00:00+00:00"

EXPECTED_PLAYER_IDS = {
    "13295",
    "6918",
    "9487",
    "12493",
    "11533",
    "HOU",
    "6462",
    "2881",
    "11584",
}

EXPECTED_PLAYER_KEYS = {
    "player_id",
    "first_name",
    "last_name",
    "position",
    "team",
    "injury_status",
    "refreshed_at",
}

EXPECTED_USER_KEYS = {
    "league_id",
    "user_id",
    "display_name",
    "team_name",
    "refreshed_at",
}


@pytest.fixture
def players_raw():
    return json.loads((FIXTURES / "players_sample.json").read_text(encoding="utf-8"))


@pytest.fixture
def users_raw():
    return json.loads((FIXTURES / "users_sample.json").read_text(encoding="utf-8"))


@pytest.fixture
def table_env(monkeypatch):
    monkeypatch.setenv("PLAYERS_TABLE", "players-table")
    monkeypatch.setenv("USERS_TABLE", "users-table")


def make_client(status, payload):
    body = json.dumps(payload).encode()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(status, stream=httpx.ByteStream(body))
    )
    return httpx.Client(transport=transport, base_url="https://sleeper.test")


# Player tests
def test_player_items_keep_fantasy_positions(players_raw):
    items = player_items(players_raw, REFRESHED_AT)

    assert len(items) == len(EXPECTED_PLAYER_IDS)
    assert {item["player_id"] for item in items} == EXPECTED_PLAYER_IDS


def test_player_items_have_exactly_the_expected_keys(players_raw):
    items = player_items(players_raw, REFRESHED_AT)

    for item in items:
        assert set(item) == EXPECTED_PLAYER_KEYS


def test_player_items_drops_non_fantasy_and_missing_positions(players_raw):
    ids = {item["player_id"] for item in player_items(players_raw, REFRESHED_AT)}

    assert "11255" in players_raw
    assert "6751" in players_raw
    assert "11255" not in ids
    assert "6751" not in ids


def test_player_items_passes_none_through(players_raw):
    by_id = {
        item["player_id"]: item for item in player_items(players_raw, REFRESHED_AT)
    }

    assert "team" in by_id["6462"]
    assert by_id["6462"]["team"] is None
    assert by_id["11584"]["injury_status"] == "Questionable"


def test_player_items_attaches_refreshed_at(players_raw):
    items = player_items(players_raw, REFRESHED_AT)

    for item in items:
        assert item["refreshed_at"] == REFRESHED_AT


# User tests
def test_user_items_attaches_refreshed_at(users_raw):
    items = user_items(users_raw, "123", REFRESHED_AT)

    for item in items:
        assert item["refreshed_at"] == REFRESHED_AT


def test_user_items_assign_league_id_passed_in(users_raw):
    items = user_items(users_raw, "123", REFRESHED_AT)

    assert len(items) == 3
    for item in items:
        assert item["league_id"] == "123"


def test_user_items_extract_team_names(users_raw):
    items = user_items(users_raw, "123", REFRESHED_AT)

    assert [item["team_name"] for item in items] == ["Test Team", None, None]


def test_user_items_have_exactly_the_expected_keys(users_raw):
    items = user_items(users_raw, "123", REFRESHED_AT)

    for item in items:
        assert set(item) == EXPECTED_USER_KEYS


# Fetch_json() tests
def test_fetch_json_returns_data_when_type_matches():
    payload = {"4046": {"position": "QB"}}

    with make_client(200, payload) as client:
        result = fetch_json(client, "/players/nfl", dict)

    assert result == payload


def test_fetch_json_raises_type_error_on_type_mismatch():
    payload = {"4046": {"position": "QB"}}

    with (
        make_client(200, payload) as client,
        pytest.raises(TypeError, match="got dict"),
    ):
        fetch_json(client, "/players/nfl", list)


def test_fetch_json_raises_status_error_on_404_response():
    with (
        make_client(404, {}) as client,
        pytest.raises(httpx.HTTPStatusError) as exc_info,
    ):
        fetch_json(client, "/players/nfl", dict)

    assert exc_info.value.response.status_code == 404


# Config tests
def test_load_config_names_all_missing(monkeypatch):
    names = ("LEAGUE_IDS", "PLAYERS_TABLE", "USERS_TABLE")
    for name in names:
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ConfigError) as exc_info:
        load_config()

    for name in names:
        assert name in str(exc_info.value)


@pytest.mark.usefixtures("table_env")
def test_load_config_cleans_league_ids(monkeypatch):
    monkeypatch.setenv("LEAGUE_IDS", " 123, 456,")

    config = load_config()

    assert config.league_ids == ("123", "456")
    assert config.players_table == "players-table"
    assert config.users_table == "users-table"


@pytest.mark.usefixtures("table_env")
def test_load_config_rejects_non_numeric_league_ids(monkeypatch):
    monkeypatch.setenv("LEAGUE_IDS", "123,abc")

    with pytest.raises(ConfigError, match="numeric"):
        load_config()


@pytest.mark.usefixtures("table_env")
def test_load_config_treats_whitespace_league_ids_as_missing(monkeypatch):
    monkeypatch.setenv("LEAGUE_IDS", "   ")

    with pytest.raises(ConfigError, match="Missing"):
        load_config()


@pytest.mark.usefixtures("table_env")
def test_load_config_rejects_league_ids_empty_after_cleaning(monkeypatch):
    monkeypatch.setenv("LEAGUE_IDS", ",")

    with pytest.raises(ConfigError, match="numeric"):
        load_config()
