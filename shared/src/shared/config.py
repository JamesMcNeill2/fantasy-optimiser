import os
from dataclasses import dataclass


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid"""


@dataclass(frozen=True)
class Config:
    players_table: str
    users_table: str
    league_ids: tuple[str, ...]


def load_config() -> Config:
    """
    Load and validate required settings from environment variables.

    Returns:
        Config: Validated application configuration loaded from the environment.

    Raises:
        ConfigError: If any required environment variable is missing or if
            LEAGUE_IDS is not a comma-separated list of numeric IDs.
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
