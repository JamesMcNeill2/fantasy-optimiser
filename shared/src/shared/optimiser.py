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
    starters: tuple[str | None, ...]
    bench: tuple[str, ...]
    optimal_total: float
    current_total: float


def selection_value(player: LineupPlayer) -> float:
    if player.game_status in NO_POINTS_STATUSES or player.projected_points is None:
        return 0.0
    return player.projected_points


def total_value(player: LineupPlayer) -> float:
    if not player.locked:
        return selection_value(player)
    return player.actual_points if player.actual_points is not None else 0.0


def availability_pool(players: list[LineupPlayer]) -> list[LineupPlayer]:
    return [p for p in players if not p.locked and not p.reserve and p.eligible]


def starting_positions(roster_positions: list[str]) -> list[str]:
    return [slot for slot in roster_positions if slot != "BN"]


def open_slots(slots: list[str], players: list[LineupPlayer]) -> list[int]:
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
    return not player.eligible.isdisjoint(SLOT_ELIGIBILITY.get(slot, frozenset()))


# Starting Slots = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K", "DEF"]
# Open Slots = [0, 1, 2, 3, 4, 5, 6, 7, 8]
def fill_order(starting_slots: list[str], open_slots: list[int]) -> list[int]:

    return sorted(
        open_slots,
        key=lambda i: len(SLOT_ELIGIBILITY.get(starting_slots[i], frozenset())),
    )


def rank_key(player: LineupPlayer) -> tuple[float, bool, str]:

    points = -selection_value(player)
    starter = player.starter_slot is None
    player_id = player.player_id

    return (points, starter, player_id)


# Starting Slots = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K", "DEF"]
# Open Slots = [0, 1, 2, 3, 4, 5, 6, 7, 8]
def greedy_fill(
    starting_slots: list[str], open_slots: list[int], pool: list[LineupPlayer]
) -> dict[int, LineupPlayer]:

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

    # ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K", "DEF"]
    positions = starting_positions(roster_positions)
    slots_open = open_slots(positions, roster_players)  # [0, 1, 2, 3, 4, 5, 6, 7, 8]
    pool = availability_pool(roster_players)  # [Player, Player, ...]
    chosen_players = greedy_fill(
        positions, slots_open, pool
    )  # [{0: Player, 1: Player, ...}]

    starter_players: list[LineupPlayer | None] = [None] * len(positions)
    for player in roster_players:
        if player.locked and player.starter_slot is not None:
            starter_players[player.starter_slot] = player
    for slot, player in chosen_players.items():
        starter_players[slot] = player

    starter_ids = []
    for player in starter_players:
        if player is None:
            starter_ids.append(None)
        else:
            starter_ids.append(player.player_id)
    starter_ids_tuple = tuple(starter_ids)

    bench_ids = []
    for player in roster_players:
        if player.player_id not in starter_ids_tuple and not player.reserve:
            bench_ids.append(player.player_id)

    bench_ids_tuple = tuple(bench_ids)

    optimal_total = 0.0
    for player in starter_players:
        if player is not None:
            optimal_total += total_value(player)

    current_total = 0.0
    for player in roster_players:
        if player.starter_slot is not None:
            current_total += total_value(player)

    return Lineup(
        starters=starter_ids_tuple,
        bench=bench_ids_tuple,
        optimal_total=optimal_total,
        current_total=current_total,
    )
