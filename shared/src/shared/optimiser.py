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
    eligible: frozenset[str]
    proj_points: float | None
    actual_points: float | None
    game_status: str | None
    starter_slot: int | None
    reserve: bool
    locked: bool


def selection_value(player: LineupPlayer) -> float:
    if player.game_status in NO_POINTS_STATUSES or player.proj_points is None:
        return 0.0
    return player.proj_points


def total_value(player: LineupPlayer) -> float:
    if not player.locked:
        return selection_value(player)
    return player.actual_points if player.actual_points is not None else 0.0


def availability_pool(players: list[LineupPlayer]) -> list[LineupPlayer]:
    return [p for p in players if not p.locked and not p.reserve and p.eligible]


def starting_slots(roster_positions: list[str]) -> list[str]:
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
