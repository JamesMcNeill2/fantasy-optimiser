import functools
import json
import logging
import time
from collections.abc import Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Annotated, NamedTuple

import boto3
import httpx
from boto3.dynamodb.conditions import Key
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from mangum import Mangum
from pydantic import BaseModel
from shared.config import Config, load_config
from shared.logs import configure_logging
from shared.optimiser import (
    SLOT_ELIGIBILITY,
    LineupPlayer,
    optimise_lineup,
    starting_positions,
)
from shared.sleeper import BASE_URL, fetch_json

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table
    from mypy_boto3_dynamodb.type_defs import (
        KeysAndAttributesServiceResourceUnionTypeDef,
    )

LEAGUE_PATH = "/league/{league_id}"
ROSTERS_PATH = "/league/{league_id}/rosters"
STATE_PATH = "/state/nfl"
MATCHUPS_PATH = "/league/{league_id}/matchups/{week}"
PROJECTION_URL = "https://api.sleeper.com/projections/nfl/player/{player_id}?season_type={season_type}&season={season}&week={week}"
SCHEDULE_URL = "https://api.sleeper.com/schedule/nfl/{season_type}/{season}"
MAX_PROJECTION_WORKERS = 16
LOCKED_STATUSES = frozenset({"in_game", "complete"})

configure_logging()
logger = logging.getLogger(__name__)


class Tables(NamedTuple):
    """Container for the DynamoDB player and user tables.

    Attributes:
        players: The players table resource.
        users: The users table resource.
    """

    players: Table
    users: Table


class NflWeek(NamedTuple):
    """Metadata describing the current NFL week.

    Attributes:
        season: The active season identifier.
        week: The current week number.
        season_type: The current season type: regular, post and pre.
    """

    season: str
    week: int
    season_type: str


class WeekGame(NamedTuple):
    """Game metadata for one team in a given week.

    Attributes:
        opponent: The opposing team abbreviation.
        status: The current game status string.
    """

    opponent: str
    status: str


class League(BaseModel):
    """A Sleeper league summary returned by the API.

    Attributes:
        key: The configured index of the league.
        name: The display name for the league.
    """

    key: int
    name: str


class Team(BaseModel):
    """A team summary within a league.

    Attributes:
        roster_id: The Sleeper roster identifier.
        team_name: The display name for the team.
    """

    roster_id: int
    team_name: str


class RosterPlayer(BaseModel):
    """A single player entry from a roster response.

    Attributes:
        player_id: The Sleeper player identifier.
        starter_slot: The starter slot index when the player is active.
        reserve: Whether the player is in the reserve list.
        first_name: The player's first name when available.
        last_name: The player's last name when available.
        position: The player's position.
        team: The player's team abbreviation.
        injury_status: The player's injury status.
        projected_points: The projected points for the week.
        opponent: The player's opponent for the week.
        game_status: The current game state.
        locked: Whether the player is in a locked game state.
        actual_points: The player's points scored in the current week, when available.
    """

    player_id: str
    starter_slot: int | None = None
    reserve: bool
    first_name: str | None = None
    last_name: str | None = None
    position: str | None = None
    team: str | None = None
    injury_status: str | None = None
    projected_points: float | None = None
    opponent: str | None = None
    game_status: str | None = None
    locked: bool = False
    actual_points: float | None = None


class OptimalLineup(BaseModel):
    """The best lineup evaluated for the current roster snapshot.

    Attributes:
        starter_ids: The selected starter player identifiers in lineup order.
        bench_ids: The bench player identifiers that were left out of the optimal lineup.
        optimal_total: The projected total points for the optimal lineup.
        current_total: The projected total points for the current lineup as drafted.
    """

    starter_ids: list[str | None]
    bench_ids: list[str]
    optimal_total: float
    current_total: float


class RosterResponse(BaseModel):
    """A roster response containing all players for a team.

    Attributes:
        players: The rostered players for the team.
        season: The season identifier for the roster data.
        week: The week number for the roster data.
        slots: The ordered starting lineup positions for the league.
        lineup: The optimal lineup evaluation for the roster.
    """

    players: list[RosterPlayer]
    season: str
    week: int
    slots: list[str]
    lineup: OptimalLineup


@functools.cache
def get_config() -> Config:
    """Load and cache the application configuration.

    Returns:
        Config: The loaded application configuration.
    """
    return load_config()


@functools.cache
def get_dynamodb() -> DynamoDBServiceResource:
    """Create and cache the DynamoDB resource client.

    Returns:
        DynamoDBServiceResource: The configured DynamoDB resource.
    """
    return boto3.resource("dynamodb")


@functools.cache
def get_tables() -> Tables:
    """Resolve the configured DynamoDB tables used by the API.

    Returns:
        Tables: The players and users DynamoDB table resources.
    """
    config = get_config()
    dynamodb = get_dynamodb()
    players_table = dynamodb.Table(config.players_table)
    users_table = dynamodb.Table(config.users_table)

    return Tables(players_table, users_table)


def get_sleeper_client() -> Iterator[httpx.Client]:
    """Yield a configured HTTP client for Sleeper API requests.

    Yields:
        httpx.Client: A Sleeper API client for this request.
    """
    with httpx.Client(base_url=BASE_URL, timeout=httpx.Timeout(5, connect=2)) as client:
        yield client


def sleeper_failure() -> HTTPException:
    """Build a standard error response for Sleeper API failures.

    Returns:
        HTTPException: A 502 HTTP exception indicating the Sleeper request failed.
    """
    return HTTPException(status_code=502, detail="Sleeper request failed")


def fetch_sleeper[T](client: httpx.Client, path: str, expected_type: type[T]) -> T:
    """Fetch JSON from Sleeper, checking it has the expected type; any failure becomes a 502.

    Args:
        client: The HTTP client used for the request.
        path: The Sleeper API path to fetch.
        expected_type: The type to coerce the payload into.

    Returns:
        T: The parsed payload as the expected type.

    Raises:
        HTTPException: If the request or payload handling fails.
    """
    try:
        return fetch_json(client, path, expected_type)
    except httpx.HTTPError, json.JSONDecodeError, TypeError:
        logger.exception("Sleeper request failed for: %s", path)
        raise sleeper_failure() from None


def get_league_id(
    league_key: int, config: Annotated[Config, Depends(get_config)]
) -> str:
    """Resolve a configured league identifier from its numeric index.

    Args:
        league_key: The zero-based index into the configured league list.
        config: The API configuration that owns the league IDs.

    Returns:
        str: The Sleeper league identifier for the requested key.

    Raises:
        HTTPException: If the provided league key does not exist.
    """
    if 0 <= league_key < len(config.league_ids):
        return config.league_ids[league_key]
    else:
        raise HTTPException(status_code=404, detail="League not found")


def clean_str(value: object) -> str | None:
    """Normalize a string field by trimming whitespace and dropping empty values.

    Args:
        value: The value to normalize.

    Returns:
        str | None: The trimmed string, or None when the value is empty or not a string.
    """
    if not isinstance(value, str):
        return None
    return value.strip() or None


def fetch_rosters(client: httpx.Client, league_id: str) -> list:
    """Fetch the roster payload for a given Sleeper league.

    Args:
        client: The HTTP client used to talk to Sleeper.
        league_id: The Sleeper league identifier.

    Returns:
        list: The raw roster payload returned by Sleeper.

    Raises:
        HTTPException: A 502 HTTP exception indicating the Sleeper request failed.
    """
    return fetch_sleeper(client, ROSTERS_PATH.format(league_id=league_id), list)


def get_players(
    dynamodb: DynamoDBServiceResource,
    table_name: str,
    player_ids: list[str],
    max_attempts: int = 3,
) -> dict[str, dict]:
    """Batch-load player records for the given IDs, retrying unprocessed keys.

    Args:
        dynamodb: The DynamoDB resource to query.
        table_name: The DynamoDB table name to read from.
        player_ids: The list of player IDs to resolve.
        max_attempts: The maximum number of attempts for unprocessed keys.

    Returns:
        dict[str, dict]: A mapping of player IDs to DynamoDB item payloads.
    """
    # Check player_ids contains values
    if not player_ids:
        return {}

    # Deduplicate requested player IDs before issuing the batch lookup
    ids = list(dict.fromkeys(player_ids))
    request: Mapping[str, KeysAndAttributesServiceResourceUnionTypeDef] = {
        table_name: {"Keys": [{"player_id": pid} for pid in ids]}
    }

    found: dict[str, dict] = {}

    # Query DynamoDB for player data
    for attempt in range(max_attempts):
        if attempt:
            time.sleep(0.1 * 2**attempt)
        response = dynamodb.batch_get_item(RequestItems=request)
        for item in response["Responses"].get(table_name, []):
            found[str(item["player_id"])] = item
        request = response.get("UnprocessedKeys") or {}
        if not request:
            break

    # Log a warning if a players data hasn't been returned
    if request:
        logger.warning(
            "Player lookup left keys unprocessed after %d attempts", max_attempts
        )

    return found


def get_nfl_week(client: httpx.Client) -> NflWeek:
    """Fetch the current NFL season metadata from Sleeper state data.

    Args:
        client: The HTTP client used to fetch Sleeper state.

    Returns:
        NflWeek: The current season, week, and season type.

    Raises:
        HTTPException: If the state payload does not contain valid NFL metadata.
    """
    # Fetch the metadata from Sleeper
    state = fetch_sleeper(client, STATE_PATH, dict)
    season = clean_str(state.get("season"))
    season_type = clean_str(state.get("season_type"))
    display_week = state.get("display_week")

    # Ensure the data has been retrieved correctly
    if season is None or season_type is None or type(display_week) is not int:
        logger.error("Unexpected NFL state: %s", state)
        raise sleeper_failure()

    return NflWeek(season=season, week=display_week, season_type=season_type)


def get_week_games(client: httpx.Client, nfl_week: NflWeek) -> dict[str, WeekGame]:
    """Build a mapping of teams to their opponent and game state for the given week.

    Args:
        client: The HTTP client used to fetch the schedule.
        nfl_week: The NFL week metadata to use when querying the schedule.

    Returns:
        dict[str, WeekGame]: A mapping of team abbreviations to opponent and status data.

    Raises:
        HTTPException: A 502 HTTP exception indicating the Sleeper request failed.
    """
    # Fetch the schedule data from Sleeper
    schedule_url = SCHEDULE_URL.format(
        season_type=nfl_week.season_type, season=nfl_week.season
    )
    schedule = fetch_sleeper(client, schedule_url, list)

    # Filter the schedule data to this weeks games
    games: dict[str, WeekGame] = {}
    skipped = 0
    for game in schedule:
        if not isinstance(game, dict) or game.get("week") != nfl_week.week:
            continue
        home = clean_str(game.get("home"))
        away = clean_str(game.get("away"))
        status = clean_str(game.get("status"))
        if home is None or away is None or status is None:
            skipped += 1
            continue
        games[home] = WeekGame(opponent=away, status=status)
        games[away] = WeekGame(opponent=home, status=status)

    # Log any skipped games
    if skipped:
        logger.warning("Skipped %d malformed games in %s", skipped, nfl_week)

    # Log if there was an error retrieving schedule data
    if not games:
        logger.warning(
            "No games found for %s (bad schedule data, not a bye week)", nfl_week
        )

    return games


def describe_game(
    team: str | None, games: Mapping[str, WeekGame]
) -> tuple[str | None, str | None]:
    """Return the opponent and live status for a team, if available.

    Args:
        team: The team abbreviation to inspect.
        games: A mapping of team abbreviations to their current game metadata.

    Returns:
        tuple[str | None, str | None]: The opponent and game status, or None values when unavailable.
    """
    if team is None or not games:
        return None, None
    game = games.get(team)
    if game is None:
        return None, "bye"
    return game.opponent, game.status


def get_projection(
    client: httpx.Client, nfl_week: NflWeek, player_id: str
) -> float | None:
    """Fetch the projected (proj) points for a single player in the current week.

    Args:
        client: The HTTP client used to fetch projection data.
        nfl_week: The NFL week context for the projection request.
        player_id: The Sleeper player identifier.

    Returns:
        float | None: The projected points for the player in the current week, or None when unavailable.

    Raises:
        HTTPException: A 502 HTTP exception indicating the Sleeper request failed.
    """
    # Retrieve the projected points from Sleeper
    proj_url = PROJECTION_URL.format(player_id=player_id, **nfl_week._asdict())
    proj_data = fetch_sleeper(client, proj_url, object)

    # Ensure the data has been retrieved in the expected format
    if proj_data is None:
        return None
    if not isinstance(proj_data, dict):
        logger.error("Unexpected projection for %s: %r", player_id, proj_data)
        raise sleeper_failure()

    proj_stats = proj_data.get("stats")
    if not isinstance(proj_stats, dict):
        logger.warning("No stats in projection for %s: %r", player_id, proj_stats)
        return None

    proj_points = proj_stats.get("pts_ppr")
    if isinstance(proj_points, bool) or not isinstance(proj_points, (int, float)):
        logger.warning("No numeric pts_ppr for %s: %r", player_id, proj_points)
        return None

    return float(proj_points)


def get_projections(
    client: httpx.Client, nfl_week: NflWeek, player_ids: list[str]
) -> dict[str, float | None]:
    """Fetch projected points for multiple players in parallel.

    Args:
        client: The HTTP client used to fetch projection data.
        nfl_week: The NFL week context for the projections.
        player_ids: The player IDs to fetch projections for.

    Returns:
        dict[str, float | None]: A mapping of player IDs to projected points.

    Raises:
        HTTPException: A 502 HTTP exception indicating the Sleeper request failed.
    """
    if not player_ids:
        return {}
    with ThreadPoolExecutor(max_workers=MAX_PROJECTION_WORKERS) as pool:
        points = pool.map(lambda pid: get_projection(client, nfl_week, pid), player_ids)
        return dict(zip(player_ids, points))


def get_roster_positions(client: httpx.Client, league_id: str) -> list[str]:
    """Fetch the roster slot ordering for a Sleeper league.

    Args:
        client: The HTTP client used to query Sleeper.
        league_id: The Sleeper league identifier.

    Returns:
        list[str]: The ordered roster positions defined by the league.

    Raises:
        HTTPException: If the league does not return a valid roster position list.
    """
    # Get the league specific roster slot order
    # Eg. ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K", "DEF", "BN", "BN", "BN", "BN", "BN", "BN"]
    league = fetch_sleeper(client, LEAGUE_PATH.format(league_id=league_id), dict)
    roster_positions = league.get("roster_positions")

    # Check roster_positions is a list
    # Error if any other data type
    if not isinstance(roster_positions, list):
        logger.error(
            "Roster positions not returned as list. Returned as: %s",
            type(roster_positions).__name__,
        )
        raise sleeper_failure()

    # Check the roster_positions values are strings
    # Error if any other data type
    non_str_positions = []
    for position in roster_positions:
        if not isinstance(position, str):
            non_str_positions.append(position)
    if non_str_positions:
        logger.error("Non string roster positions found: %s", non_str_positions)
        raise sleeper_failure()

    return roster_positions


def get_actual_points(
    client: httpx.Client, league_id: str, week: int, roster_id: int
) -> dict[str, float | None]:
    """Fetch actual player points for a roster in a specific matchup week.

    Args:
        client: The HTTP client used to query Sleeper.
        league_id: The Sleeper league identifier.
        week: The NFL week to read matchup data from.
        roster_id: The roster identifier to inspect.

    Returns:
        dict[str, float | None]: A mapping of player IDs to actual points scored, or None when unavailable.

    Raises:
        HTTPException: If the matchup payload is malformed for the requested roster.
    """
    # Get this weeks matchups for a league
    matchups = fetch_sleeper(
        client, MATCHUPS_PATH.format(league_id=league_id, week=week), list
    )
    rosters_points = None

    # Get the current actual points for a roster
    rosters_points = None
    for roster in matchups:
        if not isinstance(roster, dict):
            continue
        if roster.get("roster_id") == roster_id:
            rosters_points = roster
            break

    # Check roster_points has values
    if rosters_points is None:
        logger.warning("Roster points not found for rosters.")
        return {}

    # Get and check the points returned
    players_points = rosters_points.get("players_points")
    if not isinstance(players_points, dict):
        logger.error(
            "Players points is not a dict. Got: %s", type(players_points).__name__
        )
        raise sleeper_failure()

    # Check and return the actual points values
    actual_points: dict[str, float | None] = {}
    for player_id, points in players_points.items():
        if isinstance(points, bool) or not isinstance(points, (int, float)):
            logger.warning("No numeric points for %s: %r", player_id, points)
            actual_points[player_id] = None
        else:
            actual_points[player_id] = float(points)
    return actual_points


# Define the root router
router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    """Return a simple health-check payload for the API.

    Returns:
        dict[str, str]: The API health status payload.
    """
    return {"status": "ok"}


@router.get("/leagues")
def list_leagues(
    config: Annotated[Config, Depends(get_config)],
    client: Annotated[httpx.Client, Depends(get_sleeper_client)],
) -> list[League]:
    """List configured leagues with their display names from Sleeper.

    Args:
        config: The application configuration containing the configured league IDs.
        client: The HTTP client used to query Sleeper.

    Returns:
        list[League]: The league definitions including display names.
    """
    leagues = []
    for key, league_id in enumerate(config.league_ids):
        league_data = fetch_sleeper(
            client, LEAGUE_PATH.format(league_id=league_id), dict
        )
        name = clean_str(league_data.get("name")) or f"League {key + 1}"
        leagues.append(League(key=key, name=name))

    return leagues


@router.get("/leagues/{league_key}/teams")
def list_teams(
    league_id: Annotated[str, Depends(get_league_id)],
    tables: Annotated[Tables, Depends(get_tables)],
    client: Annotated[httpx.Client, Depends(get_sleeper_client)],
) -> list[Team]:
    """List all teams in a league with their resolved display names.

    Args:
        league_id: The Sleeper league identifier.
        tables: The configured DynamoDB tables used by the API.
        client: The HTTP client used to query Sleeper.

    Returns:
        list[Team]: The teams in the league sorted by display name.
    """
    # Acquire the rosters
    rosters = fetch_rosters(client, league_id)
    response = tables.users.query(KeyConditionExpression=Key("league_id").eq(league_id))
    items = response["Items"]
    users_by_id = {item["user_id"]: item for item in items}

    # Resolve team names in each league
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

    # Sort teams into alphabetical order
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
    """Return the full player roster for a team along with current-game metadata.

    Args:
        league_id: The Sleeper league identifier.
        roster_id: The roster identifier to fetch.
        client: The HTTP client used to query Sleeper.
        dynamodb: The DynamoDB resource used for player metadata lookups.
        tables: The configured DynamoDB tables.

    Returns:
        RosterResponse: The roster payload for the requested team.

    Raises:
        HTTPException: If the team does not exist in the league roster.
        HTTPException: A 502 HTTP exception indicating the Sleeper request failed.
    """
    # Acquire the rosters
    rosters = fetch_rosters(client, league_id)
    roster = next((r for r in rosters if r["roster_id"] == roster_id), None)
    if roster is None:
        raise HTTPException(status_code=404, detail="Team not found")

    # Define reserve and starting players
    player_ids = roster.get("players") or []  # players = ["1111"] * 15
    reserve = set(roster.get("reserve") or [])  # reserve = ["2222"]
    # {0: 0000, 1: 1111, 2: 2222, 3: 3333, 4: 4444, 5: 5555, 6: 6666, 7: 7777, 8: DEF}
    starter_ids = {
        pid: i for i, pid in enumerate(roster.get("starters") or []) if pid != "0"
    }

    # Get the league appropriate starting positions
    # ["QB", "RB", RB", "WR", "WR", "TE", "WRRB_FLEX", "K", "DEF", BN", "BN", "BN", "BN", "BN", "BN"]
    roster_positions = get_roster_positions(client, league_id)
    # positions = ["QB", "RB", "RB", "WR", "WR", "TE", "WRRB_FLEX", "K", "DEF"]
    positions = starting_positions(roster_positions)

    # Get and check all of the rosters current starters
    starters = roster.get("starters") or []
    if starters and len(positions) != len(roster.get("starters")):
        logger.error(
            "Positions and starters have different lengths. positions: %s, starter_ids: %s",
            len(positions),
            len(starters),
        )
        raise sleeper_failure()

    # Check that the positions returned are valid
    unknown_positions = []
    for position in positions:
        if position not in SLOT_ELIGIBILITY:
            unknown_positions.append(position)
    if unknown_positions:
        logger.warning(
            "%s position not in SLOT_ELIGIBILITY", ", ".join(unknown_positions)
        )

    # Get NFL metadata for the current week
    nfl_week = get_nfl_week(client)
    games = get_week_games(client, nfl_week)

    # actual_points = {0000: 0.0, 1111: 0.0, 2222: 7.2, 3333: 0.0, 4444: 0.0, 5555: 14.7, 6666: 0.0, 7777: 0.0, DEF: 0.0}
    actual_points = get_actual_points(client, league_id, nfl_week.week, roster_id)

    # Get the players data from DynamoDB
    players_data = get_players(
        dynamodb, tables.players.name, player_ids, max_attempts=3
    )
    missing = [pid for pid in player_ids if pid not in players_data]
    if missing:
        logger.warning("No player rows for %s", ", ".join(missing))

    # Create the RosterPlayer class for each player in a teams roster
    proj_pts = get_projections(client, nfl_week, player_ids)
    roster_players = []
    for player_id in player_ids:
        details = players_data.get(player_id, {})
        team = clean_str(details.get("team"))
        opponent, game_status = describe_game(team, games)
        roster_players.append(
            RosterPlayer(
                player_id=player_id,
                starter_slot=starter_ids.get(player_id),
                reserve=player_id in reserve,
                first_name=clean_str(details.get("first_name")),
                last_name=clean_str(details.get("last_name")),
                position=clean_str(details.get("position")),
                team=team,
                injury_status=clean_str(details.get("injury_status")),
                projected_points=proj_pts.get(player_id),
                opponent=opponent,
                game_status=game_status,
                locked=game_status in LOCKED_STATUSES,
                actual_points=actual_points.get(player_id),
            )
        )

    # Create the LineupPlayer class for each player in the roster
    lineup_players = []
    for player in roster_players:
        lineup_players.append(
            LineupPlayer(
                player_id=player.player_id,
                eligible=frozenset({player.position})
                if player.position
                else frozenset(),
                projected_points=player.projected_points,
                actual_points=player.actual_points,
                game_status=player.game_status,
                starter_slot=player.starter_slot,
                reserve=player.reserve,
                locked=player.locked,
            )
        )

    # Get the optimal lineup for a roster and store it in a OptimalLineup
    optimal_lineup_tuples = optimise_lineup(roster_positions, lineup_players)
    optimal_lineup = OptimalLineup(
        starter_ids=list(optimal_lineup_tuples.starters),
        bench_ids=list(optimal_lineup_tuples.bench),
        optimal_total=optimal_lineup_tuples.optimal_total,
        current_total=optimal_lineup_tuples.current_total,
    )

    # Return the completed roster for a team
    return RosterResponse(
        players=roster_players,
        season=nfl_week.season,
        week=nfl_week.week,
        slots=positions,
        lineup=optimal_lineup,
    )


app = FastAPI(
    title="Fantasy Lineup Optimiser API",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.include_router(router)

handler = Mangum(app, lifespan="off")
