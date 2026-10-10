import functools
import json
import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING, Annotated, NamedTuple

import boto3
import httpx
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from mangum import Mangum
from pydantic import BaseModel
from shared.config import Config, load_config
from shared.logs import configure_logging
from shared.sleeper import BASE_URL, fetch_json

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import Table

LEAGUE_PATH = "/league/{league_id}"

configure_logging()

logger = logging.getLogger(__name__)


class Tables(NamedTuple):
    players: Table
    users: Table


class League(BaseModel):
    key: int
    name: str


class Team(BaseModel):
    roster_id: int
    team_name: str


@functools.cache
def get_config() -> Config:
    return load_config()


@functools.cache
def get_tables() -> Tables:
    config = get_config()

    dynamodb = boto3.resource("dynamodb")
    players_table = dynamodb.Table(config.players_table)
    users_table = dynamodb.Table(config.users_table)

    return Tables(players_table, users_table)


def get_sleeper_client() -> Iterator[httpx.Client]:
    with httpx.Client(base_url=BASE_URL, timeout=httpx.Timeout(5, connect=2)) as client:
        yield client


def fetch_sleeper[T](client: httpx.Client, path: str, expected_type: type[T]) -> T:

    try:
        return fetch_json(client, path, expected_type)
    except httpx.HTTPError, json.JSONDecodeError, TypeError:
        logger.exception("Sleeper request failed for: %s", path)
        raise HTTPException(status_code=502, detail="Sleeper request failed") from None


def get_league_id(
    league_key: int, config: Annotated[Config, Depends(get_config)]
) -> str:

    if 0 <= league_key < len(config.league_ids):
        return config.league_ids[league_key]
    else:
        raise HTTPException(status_code=404, detail="League not found")


def clean_str(value: object) -> str | None:
    if isinstance(value, str):
        return value.strip()
    else:
        return None


router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@router.get("/leagues")
def list_leagues(
    config: Annotated[Config, Depends(get_config)],
    client: Annotated[httpx.Client, Depends(get_sleeper_client)]
) -> list[League]:

    leagues = []

    for key, league_id in enumerate(config.league_ids):
        path = LEAGUE_PATH.format(league_id=league_id)
        data = fetch_sleeper(client, path, dict)
        name = data.get("name") or f"League {key + 1}"
        leagues.append(League(key=key, name=name))

    return leagues


app = FastAPI(
    title="Fantasy Lineup Optimiser API",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.include_router(router)

handler = Mangum(app, lifespan="off")
