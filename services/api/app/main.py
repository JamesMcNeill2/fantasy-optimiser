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


router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app = FastAPI(
    title="Fantasy Lineup Optimiser API",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.include_router(router)

handler = Mangum(app, lifespan="off")
