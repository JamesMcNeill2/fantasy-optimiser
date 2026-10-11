import functools
import json
import logging
import time
from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING, Annotated, NamedTuple

import boto3
import httpx
from boto3.dynamodb.conditions import Key
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from mangum import Mangum
from pydantic import BaseModel
from shared.config import Config, load_config
from shared.logs import configure_logging
from shared.sleeper import BASE_URL, fetch_json

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table
    from mypy_boto3_dynamodb.type_defs import (
        KeysAndAttributesServiceResourceUnionTypeDef,
    )

LEAGUE_PATH = "/league/{league_id}"
ROSTERS_PATH = "league/{league_id}/rosters"

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


class RosterPlayer(BaseModel):
    player_id: str
    starter: bool
    reserve: bool
    first_name: str | None = None
    last_name: str | None = None
    position: str | None = None
    team: str | None = None
    injury_status: str | None = None


class RosterResponse(BaseModel):
    players: list[RosterPlayer]


@functools.cache
def get_config() -> Config:
    return load_config()


@functools.cache
def get_dynamodb() -> DynamoDBServiceResource:
    return boto3.resource("dynamodb")


@functools.cache
def get_tables() -> Tables:
    config = get_config()

    dynamodb = get_dynamodb()
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


def fetch_rosters(client: httpx.Client, league_id: str) -> list:
    return fetch_sleeper(client, ROSTERS_PATH.format(league_id=league_id), list)


def get_players(
    dynamodb: DynamoDBServiceResource,
    table_name: str,
    player_ids: list[str],
    max_attempts: int = 3,
) -> dict[str, dict]:

    if not player_ids:
        return {}

    ids = list(dict.fromkeys(player_ids))
    request: Mapping[str, KeysAndAttributesServiceResourceUnionTypeDef] = {
        table_name: {"Keys": [{"player_id": pid} for pid in ids]}
    }

    found: dict[str, dict] = {}

    for attempt in range(max_attempts):
        if attempt:
            time.sleep(0.1 * 2**attempt)
        response = dynamodb.batch_get_item(RequestItems=request)
        for item in response["Responses"].get(table_name, []):
            found[str(item["player_id"])] = item
        request = response.get("UnprocessedKeys") or {}
        if not request:
            break

    if request:
        logger.warning(
            "Player lookup left keys unprocessed after %d attempts", max_attempts
        )

    return found


router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/leagues")
def list_leagues(
    config: Annotated[Config, Depends(get_config)],
    client: Annotated[httpx.Client, Depends(get_sleeper_client)],
) -> list[League]:

    leagues = []

    for key, league_id in enumerate(config.league_ids):
        league_data = fetch_sleeper(
            client, LEAGUE_PATH.format(league_id=league_id), dict
        )
        name = league_data.get("name") or f"League {key + 1}"
        leagues.append(League(key=key, name=name))

    return leagues


@router.get("/leagues/{league_key}/teams")
def list_teams(
    league_id: Annotated[str, Depends(get_league_id)],
    tables: Annotated[Tables, Depends(get_tables)],
    client: Annotated[httpx.Client, Depends(get_sleeper_client)],
) -> list[Team]:

    rosters = fetch_rosters(client, ROSTERS_PATH.format(league_id=league_id))
    response = tables.users.query(KeyConditionExpression=Key("league_id").eq(league_id))
    items = response["Items"]
    users_by_id = {item["user_id"]: item for item in items}

    teams = []
    for roster in rosters:
        roster_id = roster["roster_id"]
        user = users_by_id.get(roster.get("owner_id"))
        team_name = clean_str(user.get("team_name")) if user else None
        display_name = clean_str(user.get("display_name")) if user else None
        if team_name is None:
            if display_name is not None:
                team_name = f"Team {display_name}"
            else:
                team_name = f"Team {roster_id}"
        teams.append(Team(roster_id=roster_id, team_name=team_name))

    teams.sort(key=lambda team: team.team_name.casefold())
    return teams


@router.get("/leagues/{league_key}/teams/{roster_id}/roster")
def get_roster(
    league_id: Annotated[str, Depends(get_league_id)],
    roster_id: int,
    client: Annotated[httpx.Client, Depends(get_sleeper_client)],
    dynamodb: Annotated[DynamoDBServiceResource, Depends(get_dynamodb)],
    tables: Annotated[Tables, Depends(get_tables)],
) -> RosterResponse:

    rosters = fetch_rosters(client, league_id)
    roster = next((r for r in rosters if r["roster_id"] == roster_id), None)
    if roster is None:
        raise HTTPException(status_code=404, detail="Team not found")

    player_ids = roster.get("players") or []
    starters = set(roster.get("starters") or [])
    reserve = set(roster.get("reserve") or [])

    found = get_players(dynamodb, tables.players.name, player_ids)
    missing = [pid for pid in player_ids if pid not in found]
    if missing:
        logger.warning("No player rows for %s", ", ".join(missing))

    players = []
    for player_id in player_ids:
        details = found.get(player_id, {})
        players.append(
            RosterPlayer(
                player_id=player_id,
                starter=player_id in starters,
                reserve=player_id in reserve,
                first_name=clean_str(details.get("first_name")),
                last_name=clean_str(details.get("last_name")),
                position=clean_str(details.get("position")),
                team=clean_str(details.get("team")),
                injury_status=clean_str(details.get("injury_status")),
            )
        )

    return RosterResponse(players=players)


app = FastAPI(
    title="Fantasy Lineup Optimiser API",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.include_router(router)

handler = Mangum(app, lifespan="off")
