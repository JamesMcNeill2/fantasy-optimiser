import json
from pathlib import Path

import pytest
from app.main import player_items, user_items

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
    "shirt_number",
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
    "avatar",
    "refreshed_at",
}


@pytest.fixture
def players_raw():
    return json.loads((FIXTURES / "players_sample.json").read_text(encoding="utf-8"))


@pytest.fixture
def users_raw():
    return json.loads((FIXTURES / "users_sample.json").read_text(encoding="utf-8"))


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


def test_player_items_copy_shirt_numbers(players_raw):
    by_id = {
        item["player_id"]: item for item in player_items(players_raw, REFRESHED_AT)
    }

    assert players_raw["11533"]["number"] is not None
    assert by_id["11533"]["shirt_number"] == players_raw["11533"]["number"]
    assert isinstance(by_id["11533"]["shirt_number"], int)
    assert "shirt_number" in by_id["HOU"]
    assert by_id["HOU"]["shirt_number"] is None


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


def test_user_items_extract_avatars(users_raw):
    items = user_items(users_raw, "123", REFRESHED_AT)

    assert [item["avatar"] for item in items] == [
        "https://sleepercdn.com/uploads/12345.jpg",
        None,
        None,
    ]


def test_user_items_have_exactly_the_expected_keys(users_raw):
    items = user_items(users_raw, "123", REFRESHED_AT)

    for item in items:
        assert set(item) == EXPECTED_USER_KEYS
