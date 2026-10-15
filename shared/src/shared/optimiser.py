from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

SLOT_ELIGIBILITY: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "QB": frozenset({"QB"}),
        "RB": frozenset({"RB"}),
        "WR": frozenset({"WR"}),
        "TE": frozenset({"TE"}),
        "K": frozenset({"K"}),
        "DEF": frozenset({"DEF"}),
        "FLEX": frozenset({"RB", "WR", "TE"}),
        "WRRB_FLEX": frozenset({"RB", "WR"}),
        "REC_FLEX": frozenset({"WR", "TE"}),
        "SUPER_FLEX": frozenset({"QB", "RB", "WR", "TE"}),
    }
)
NO_POINTS_STATUSES = frozenset({"bye", "canceled"})


@dataclass(frozen=True, kw_only=True, slots=True)
class LineupPlayer:
    """Represent a player's lineup, scoring, and availability details.

    Attributes:
        player_id: Unique identifier for the player.
        eligible: Position types for which the player is eligible.
        projected_points: Projected points, if available.
        actual_points: Actual points, if available.
        game_status: Current game status, if known.
        starter_slot: Current starting-slot index, if assigned.
        reserve: Whether the player is on a reserve roster slot.
        locked: Whether the player's lineup position is locked.
    """

    player_id: str
    eligible: frozenset[str]  # {"RB"}
    projected_points: float | None
    actual_points: float | None
    game_status: str | None
    starter_slot: int | None
    reserve: bool
    locked: bool


@dataclass(frozen=True, kw_only=True, slots=True)
class Lineup:
    """Represent an optimized lineup and its point totals.

    Attributes:
        starters: Player IDs by starting slot; ``None`` marks an empty slot.
        bench: Player IDs assigned to the bench.
        optimal_total: Points from the optimized starting lineup.
        current_total: Points from the current starting lineup.
    """

    starters: tuple[str | None, ...]
    bench: tuple[str, ...]
    optimal_total: float
    current_total: float


def selection_value(player: LineupPlayer) -> float:
    """Return a player's projected value for lineup selection.

    Players with no usable projection receive zero points.

    Args:
        player: Player whose projected value is being evaluated.

    Returns:
        The player's projected points, or zero when unavailable.
    """
    if player.game_status in NO_POINTS_STATUSES or player.projected_points is None:
        return 0.0
    return player.projected_points


def total_value(player: LineupPlayer) -> float:
    """Return the points counted for a player in a lineup total.

    Locked players use actual points; unlocked players use selection value.

    Args:
        player: Player whose lineup value is being evaluated.

    Returns:
        The player's actual or projected points, defaulting to zero.
    """
    if not player.locked:
        return selection_value(player)
    return player.actual_points if player.actual_points is not None else 0.0


def availability_pool(players: list[LineupPlayer]) -> list[LineupPlayer]:
    """Select players eligible to fill open starting slots.

    Args:
        players: All players on the roster.

    Returns:
        Unlocked, non-reserve players with at least one eligibility.
    """
    return [p for p in players if not p.locked and not p.reserve and p.eligible]


def starting_positions(roster_positions: list[str]) -> list[str]:
    """Remove bench positions from a list of roster positions.

    Args:
        roster_positions: All roster slot types, including bench slots.

    Returns:
        Starting slot types in their original order.
    """
    return [slot for slot in roster_positions if slot != "BN"]


def open_slots(slots: list[str], players: list[LineupPlayer]) -> list[int]:
    """Return starting-slot indices not occupied by locked players.

    Args:
        slots: Starting slot types.
        players: Roster players, including locked starters.

    Returns:
        Indices of unoccupied starting slots.

    Raises:
        ValueError: A locked player's slot is out of range or already taken.
    """
    taken: set[int] = set()
    slot_count = len(slots)
    for player in players:
        slot = player.starter_slot
        if not player.locked or slot is None:
            continue
        if slot not in range(slot_count):
            raise ValueError(
                f"Locked player {player.player_id} has starter_slot {slot}; "
                f"the league has {slot_count} starting slots"
            )
        if slot in taken:
            raise ValueError(
                f"Locked player {player.player_id} has starter_slot {slot}, "
                "already held by another locked player"
            )
        taken.add(slot)

    return [i for i in range(slot_count) if i not in taken]


def can_fill(player: LineupPlayer, slot: str) -> bool:
    """Check whether a player is eligible for a slot type.

    Args:
        player: Player to check.
        slot: Starting slot type.

    Returns:
        Whether the player's eligible positions include a position allowed
        by the slot.
    """
    return not player.eligible.isdisjoint(SLOT_ELIGIBILITY.get(slot, frozenset()))


# Starting Slots = ["QB", "RB", "RB", "WR", "WR", "TE", "WRRB_FLEX", "K", "DEF"]
# Open Slots = [0, 1, 2, 3, 4, 5, 6, 7, 8]
def fill_order(starting_slots: list[str], open_slots: list[int]) -> list[int]:
    """Order open slots from most restrictive to least restrictive.

    Args:
        starting_slots: Starting slot types indexed by roster position.
        open_slots: Indices of available starting slots.

    Returns:
        Slot indices sorted by the number of position types each accepts.
    """

    return sorted(
        open_slots,
        key=lambda i: len(SLOT_ELIGIBILITY.get(starting_slots[i], frozenset())),
    )


def rank_key(player: LineupPlayer) -> tuple[float, bool, str]:
    """Return the deterministic sorting key for lineup candidates.

    Candidates sort by descending selection value, then starter assignment,
    then player ID.

    Args:
        player: Candidate player to rank.

    Returns:
        A tuple suitable for sorting candidate players.
    """

    points = -selection_value(player)
    starter = player.starter_slot is None
    player_id = player.player_id

    return (points, starter, player_id)


# Starting Slots = ["QB", "RB", "RB", "WR", "WR", "TE", "WRRB_FLEX", "K", "DEF"]
# Open Slots = [0, 1, 2, 3, 4, 5, 6, 7, 8]
def greedy_fill(
    starting_slots: list[str], open_slots: list[int], pool: list[LineupPlayer]
) -> dict[int, LineupPlayer]:
    """Greedily assign eligible players to open starting slots.

    Slots are considered in restrictive-first order, assigning the
    highest-ranked remaining eligible player to each slot when possible.

    Args:
        starting_slots: Starting slot types indexed by roster position.
        open_slots: Indices of unoccupied starting slots.
        pool: Players available for assignment.

    Returns:
        A mapping from filled slot indices to assigned players.
    """

    remaining = list(pool)
    chosen: dict[int, LineupPlayer] = {}

    for slot in fill_order(starting_slots, open_slots):  # [0, 1, 3, 5, 8, 6]
        slot_type = starting_slots[slot]
        candidates = [p for p in remaining if can_fill(p, slot_type)]
        if not candidates:
            continue
        best = min(candidates, key=rank_key)
        chosen[slot] = best
        remaining.remove(best)

    return chosen


def optimise_lineup(
    roster_positions: list[str], roster_players: list[LineupPlayer]
) -> Lineup:
    """Build the optimal lineup for a roster and total its points.

    Locked starters keep their slots and locked bench players stay benched. The
    open slots are filled from unlocked, non-IR players, narrowest slot first,
    each taking the best remaining eligible player. This is exact when every
    player has one eligible position and the flex slots are nested.

    Args:
        roster_positions: The league's slot types in order, including BN
            entries.
        roster_players: Every player on the roster.

    Returns:
        Lineup: Starters by slot (None for an empty slot), the bench excluding
            IR players, and the optimal and current totals. Locked players count
            their actual points; everyone else counts their projection.

    Raises:
        ValueError: If a locked starter's slot is outside the starting slots,
            or two locked starters share a slot.
    """
    # Get all of the position information
    # ["QB", "RB", "RB", "WR", "WR", "TE", "WRRB_FLEX", "K", "DEF"]
    positions = starting_positions(roster_positions)
    slots_open = open_slots(positions, roster_players)  # [0, 1, 2, 3, 4, 5, 6, 7, 8]
    pool = availability_pool(roster_players)  # [Player, Player, ...]

    # Decide which players deserve to be started
    chosen_players = greedy_fill(
        positions, slots_open, pool
    )  # {0: Player, 1: Player, ...}

    # Preserve locked starters and place the optimized players in their slots
    starter_players: list[LineupPlayer | None] = [None] * len(positions)
    for player in roster_players:
        if player.locked and player.starter_slot is not None:
            starter_players[player.starter_slot] = player
    for slot, player in chosen_players.items():
        starter_players[slot] = player

    # Determine the starting player ids
    starter_ids = []
    for player in starter_players:
        if player is None:
            starter_ids.append(None)
        else:
            starter_ids.append(player.player_id)
    starter_ids_tuple = tuple(starter_ids)

    # Determine the benched players ids
    bench_ids = []
    for player in roster_players:
        if player.player_id not in starter_ids_tuple and not player.reserve:
            bench_ids.append(player.player_id)
    bench_ids_tuple = tuple(bench_ids)

    # Determine the optimal points total
    # Based on the optimal lineups projected points
    optimal_total = 0.0
    for player in starter_players:
        if player is not None:
            optimal_total += total_value(player)

    # Determine the current projected points total
    # Based on the current starting lineup
    current_total = 0.0
    for player in roster_players:
        if player.starter_slot is not None:
            current_total += total_value(player)

    # Create and return the Lineup class for this roster
    return Lineup(
        starters=starter_ids_tuple,
        bench=bench_ids_tuple,
        optimal_total=optimal_total,
        current_total=current_total,
    )
