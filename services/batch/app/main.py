import datetime
import logging
import os
import time
from dataclasses import dataclass

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
def handler(event, context):
    return {"status": "ok"}
