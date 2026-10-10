import pytest
from shared.config import ConfigError, load_config


@pytest.fixture
def table_env(monkeypatch):
    monkeypatch.setenv("PLAYERS_TABLE", "players-table")
    monkeypatch.setenv("USERS_TABLE", "users-table")

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
