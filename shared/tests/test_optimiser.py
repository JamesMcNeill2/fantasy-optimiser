"""Tests for shared.optimiser: the lineup rules, the greedy fill and the result.

Every test builds players by hand, so nothing here touches Sleeper or AWS. The
brute-force tests compare the greedy fill with an exhaustive search on seeded
random rosters, which is what shows the fill order makes greedy exact.
"""

import random
from dataclasses import FrozenInstanceError, replace

import pytest

from shared.optimiser import (
    NO_POINTS_STATUSES,
    SLOT_ELIGIBILITY,
    LineupPlayer,
    availability_pool,
    can_fill,
    fill_order,
    greedy_fill,
    open_slots,
    optimise_lineup,
    rank_key,
    selection_value,
    starting_slots,
    total_value,
)

# Both leagues' real layout (13 October 2026), and its starting slots.
LAYOUT = ["QB", "RB", "RB", "WR", "WR", "TE", "WRRB_FLEX", "K", "DEF"] + ["BN"] * 6
SLOTS = ["QB", "RB", "RB", "WR", "WR", "TE", "WRRB_FLEX", "K", "DEF"]
ALL_OPEN = list(range(9))

# An unlocked bench RB projected 7.6 before kickoff; each test changes only what
# it needs with player(...).
BASE = LineupPlayer(
    player_id="1",
    eligible=frozenset({"RB"}),
    proj_points=7.6,
    actual_points=None,
    game_status="pre_game",
    starter_slot=None,
    reserve=False,
    locked=False,
)


def player(**changes) -> LineupPlayer:
    """Return BASE with the given fields changed."""
    return replace(BASE, **changes)


def make(
    player_id: str,
    position: str | set[str],
    points: float | None,
    *,
    slot: int | None = None,
    locked: bool = False,
    actual: float | None = None,
    status: str | None = "pre_game",
    reserve: bool = False,
) -> LineupPlayer:
    """Build a player from the handful of fields the lineup tests care about."""
    eligible = (
        frozenset(position) if isinstance(position, set) else frozenset({position})
    )
    return LineupPlayer(
        player_id=player_id,
        eligible=eligible,
        proj_points=points,
        actual_points=actual,
        game_status=status,
        starter_slot=slot,
        reserve=reserve,
        locked=locked,
    )


def locked_at(
    player_id: str, position: str, slot: int, actual: float = 10.0
) -> LineupPlayer:
    """A starter whose game has finished, so he can't move."""
    return make(
        player_id,
        position,
        9.0,
        slot=slot,
        locked=True,
        actual=actual,
        status="complete",
    )


def ids(chosen: dict[int, LineupPlayer]) -> dict[int, str]:
    """greedy_fill's result as {slot: player_id}, for readable comparisons."""
    return {slot: p.player_id for slot, p in chosen.items()}


# The 4.5 example: one player for every slot, plus a spare TE who is worth more
# than the flex pick but can't play WRRB_FLEX.
EXAMPLE_POOL = [
    make("QB20", "QB", 20.0),
    make("RB15", "RB", 15.0),
    make("RB12", "RB", 12.0),
    make("RB9", "RB", 9.0),
    make("WR14", "WR", 14.0),
    make("WR8", "WR", 8.0),
    make("TE11", "TE", 11.0),
    make("TE10", "TE", 10.0),
    make("K7", "K", 7.0),
    make("DEF6", "DEF", 6.0),
]


# --- Constants --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("slot", "positions"),
    [
        ("QB", {"QB"}),
        ("RB", {"RB"}),
        ("WR", {"WR"}),
        ("TE", {"TE"}),
        ("K", {"K"}),
        ("DEF", {"DEF"}),
        ("WRRB_FLEX", {"RB", "WR"}),
        ("REC_FLEX", {"WR", "TE"}),
        ("FLEX", {"RB", "WR", "TE"}),
        ("SUPER_FLEX", {"QB", "RB", "WR", "TE"}),
    ],
)
def test_slot_eligibility(slot, positions):
    assert SLOT_ELIGIBILITY[slot] == frozenset(positions)
    assert type(SLOT_ELIGIBILITY[slot]) is frozenset


def test_slot_eligibility_has_exactly_these_slots_and_not_bench():
    assert len(SLOT_ELIGIBILITY) == 10
    assert "BN" not in SLOT_ELIGIBILITY


def test_slot_eligibility_is_read_only():
    with pytest.raises(TypeError):
        SLOT_ELIGIBILITY["X"] = frozenset()  # type: ignore[index]


def test_no_points_statuses_use_sleepers_spelling():
    # Sleeper's schedule says "canceled"; "cancelled" would never match.
    assert NO_POINTS_STATUSES == frozenset({"bye", "canceled"})


# --- LineupPlayer -------------------------------------------------------------------


def test_lineup_player_is_frozen():
    with pytest.raises(FrozenInstanceError):
        BASE.locked = True  # type: ignore[misc]


def test_lineup_player_is_keyword_only():
    with pytest.raises(TypeError):
        LineupPlayer("1", frozenset(), 1.0, None, None, None, False, False)  # type: ignore[misc]


def test_lineup_player_is_hashable():
    assert len({BASE, player()}) == 1
    assert len({BASE, player(player_id="2")}) == 2


# --- selection_value ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("points", "status", "expected"),
    [
        (7.6, "pre_game", 7.6),
        (None, "pre_game", 0.0),
        (5.0, "bye", 0.0),
        (5.0, "canceled", 0.0),
        (5.0, None, 5.0),
    ],
)
def test_selection_value(points, status, expected):
    result = selection_value(player(proj_points=points, game_status=status))
    assert result == expected
    assert type(result) is float


def test_selection_value_ignores_lock_and_actual_points():
    p = player(locked=True, game_status="complete", proj_points=9.0, actual_points=13.4)
    assert selection_value(p) == 9.0


# --- total_value ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("locked", "actual", "points", "status", "expected"),
    [
        (True, 13.4, 9.0, "complete", 13.4),
        (True, 3.2, 12.0, "in_game", 3.2),
        (True, None, 9.0, "complete", 0.0),
        (False, None, 7.6, "pre_game", 7.6),
        (False, None, 5.0, "bye", 0.0),
        (False, None, None, "pre_game", 0.0),
        (False, 2.0, 7.6, "pre_game", 7.6),
    ],
)
def test_total_value(locked, actual, points, status, expected):
    p = player(
        locked=locked, actual_points=actual, proj_points=points, game_status=status
    )
    result = total_value(p)
    assert result == expected
    assert type(result) is float


# --- availability_pool ------------------------------------------------------------------


def test_pool_keeps_unlocked_players_in_order_and_drops_the_rest():
    bench = player(player_id="10")
    starter = player(player_id="11", starter_slot=3)
    locked_starter = player(
        player_id="12", starter_slot=0, locked=True, game_status="complete"
    )
    locked_bench = player(player_id="13", locked=True, game_status="in_game")
    on_ir = player(player_id="14", reserve=True)
    no_positions = player(player_id="15", eligible=frozenset())
    everyone = [bench, starter, locked_starter, locked_bench, on_ir, no_positions]
    before = list(everyone)

    assert availability_pool(everyone) == [bench, starter]
    assert everyone == before


def test_pool_of_nobody_is_empty():
    assert availability_pool([]) == []


# --- starting_slots ---------------------------------------------------------------------


def test_starting_slots_drops_bench_and_leaves_input_alone():
    layout = list(LAYOUT)
    assert starting_slots(layout) == SLOTS
    assert layout == LAYOUT


@pytest.mark.parametrize(
    ("positions", "expected"),
    [
        (["BN", "QB", "BN", "RB"], ["QB", "RB"]),
        (["BN", "BN"], []),
        (SLOTS, SLOTS),
    ],
)
def test_starting_slots_other_layouts(positions, expected):
    assert starting_slots(list(positions)) == expected


# --- open_slots -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("players", "expected"),
    [
        ([], ALL_OPEN),
        ([locked_at("Q", "QB", 0)], [1, 2, 3, 4, 5, 6, 7, 8]),
        ([locked_at("Q", "QB", 0), locked_at("K", "K", 7)], [1, 2, 3, 4, 5, 6, 8]),
        ([locked_at("K", "K", 7), locked_at("Q", "QB", 0)], [1, 2, 3, 4, 5, 6, 8]),
        ([locked_at("D", "DEF", 8)], [0, 1, 2, 3, 4, 5, 6, 7]),
        ([player(starter_slot=3)], ALL_OPEN),
        ([player(locked=True, game_status="in_game")], ALL_OPEN),
    ],
    ids=[
        "no one locked",
        "locked QB",
        "locked QB and K",
        "player order irrelevant",
        "last slot locked",
        "unlocked starter frees nothing",
        "locked bench player holds no slot",
    ],
)
def test_open_slots(players, expected):
    assert open_slots(list(SLOTS), players) == expected


def test_open_slots_leaves_input_alone():
    slots = list(SLOTS)
    open_slots(slots, [locked_at("Q", "QB", 0)])
    assert slots == SLOTS


@pytest.mark.parametrize("bad_slot", [9, -1, 100])
def test_open_slots_rejects_a_locked_slot_outside_the_layout(bad_slot):
    with pytest.raises(ValueError, match="P99"):
        open_slots(list(SLOTS), [locked_at("P99", "RB", bad_slot)])


def test_open_slots_rejects_two_locked_players_in_one_slot():
    with pytest.raises(ValueError, match="P2"):
        open_slots(list(SLOTS), [locked_at("P1", "RB", 3), locked_at("P2", "RB", 3)])


# --- can_fill ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("eligible", "slot", "expected"),
    [
        ({"RB"}, "RB", True),
        ({"RB"}, "WRRB_FLEX", True),
        ({"WR"}, "WRRB_FLEX", True),
        ({"TE"}, "WRRB_FLEX", False),
        ({"TE"}, "FLEX", True),
        ({"QB"}, "SUPER_FLEX", True),
        ({"QB"}, "FLEX", False),
        ({"RB", "TE"}, "TE", True),
        ({"RB"}, "IDP_FLEX", False),
        (set(), "RB", False),
    ],
)
def test_can_fill(eligible, slot, expected):
    assert can_fill(player(eligible=frozenset(eligible)), slot) is expected


# --- fill_order -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("open_", "expected"),
    [
        (ALL_OPEN, [0, 1, 2, 3, 4, 5, 7, 8, 6]),
        ([1, 2, 3, 4, 5, 6, 8], [1, 2, 3, 4, 5, 8, 6]),
        ([6], [6]),
        ([], []),
    ],
)
def test_fill_order(open_, expected):
    assert fill_order(list(SLOTS), list(open_)) == expected


def test_fill_order_puts_wider_flex_slots_later():
    slots = ["SUPER_FLEX", "FLEX", "QB", "WRRB_FLEX", "RB"]
    assert fill_order(slots, [0, 1, 2, 3, 4]) == [2, 4, 3, 1, 0]


def test_fill_order_leaves_input_alone():
    open_ = list(ALL_OPEN)
    fill_order(list(SLOTS), open_)
    assert open_ == ALL_OPEN


# --- rank_key ---------------------------------------------------------------------------


def test_rank_key_prefers_more_points():
    better, worse = make("A", "RB", 12.0), make("B", "RB", 9.0, slot=1)
    assert min([worse, better], key=rank_key) is better


def test_rank_key_prefers_the_current_starter_on_equal_points():
    bench, starter = make("A", "RB", 10.0), make("B", "RB", 10.0, slot=2)
    assert min([bench, starter], key=rank_key) is starter


def test_rank_key_prefers_the_lower_id_as_a_string_when_all_else_is_equal():
    # As strings "1466" < "4046" < "96" < "KC", which is not numeric order.
    tied = [make(pid, "RB", 10.0) for pid in ["96", "KC", "4046", "1466"]]
    assert min(tied, key=rank_key).player_id == "1466"


def test_rank_key_handles_a_zero_point_tie_between_starter_and_bench():
    # Comparing a slot number with None would raise TypeError.
    bye_starter = make("A", "RB", 5.0, slot=1, status="bye")
    no_projection = make("B", "RB", None)
    assert min([no_projection, bye_starter], key=rank_key) is bye_starter


# --- greedy_fill ------------------------------------------------------------------------


def test_greedy_fill_example():
    chosen = greedy_fill(list(SLOTS), list(ALL_OPEN), list(EXAMPLE_POOL))
    assert ids(chosen) == {
        0: "QB20",
        1: "RB15",
        2: "RB12",
        3: "WR14",
        4: "WR8",
        5: "TE11",
        6: "RB9",
        7: "K7",
        8: "DEF6",
    }


def test_greedy_fill_never_puts_a_te_in_wrrb_flex():
    # TE10 outscores RB9 but WRRB_FLEX takes RB or WR only.
    chosen = greedy_fill(list(SLOTS), list(ALL_OPEN), list(EXAMPLE_POOL))
    assert "TE10" not in ids(chosen).values()


def test_greedy_fill_fills_dedicated_slots_before_the_flex():
    # Filling the flex first would take RB15 and leave an RB slot empty.
    pool = [make("RB15", "RB", 15.0), make("RB12", "RB", 12.0)] + [
        make(f"WR{n}", "WR", float(n)) for n in (14, 13, 8)
    ]
    chosen = ids(greedy_fill(list(SLOTS), list(ALL_OPEN), pool))
    assert chosen[1] == "RB15" and chosen[2] == "RB12"
    assert chosen[6] == "WR8"


def test_greedy_fill_leaves_a_slot_empty_when_nobody_fits():
    pool = [p for p in EXAMPLE_POOL if p.player_id != "K7"]
    chosen = greedy_fill(list(SLOTS), list(ALL_OPEN), pool)
    assert 7 not in chosen
    assert len(chosen) == 8


def test_greedy_fill_only_fills_open_slots():
    chosen = greedy_fill(list(SLOTS), [1, 2, 6], list(EXAMPLE_POOL))
    assert ids(chosen) == {1: "RB15", 2: "RB12", 6: "WR14"}


def test_greedy_fill_keeps_the_current_starter_on_a_tie():
    pool = [make("A", "K", 8.0), make("B", "K", 8.0, slot=7)]
    assert ids(greedy_fill(list(SLOTS), [7], pool)) == {7: "B"}


def test_greedy_fill_leaves_the_pool_alone():
    pool = list(EXAMPLE_POOL)
    greedy_fill(list(SLOTS), list(ALL_OPEN), pool)
    assert pool == EXAMPLE_POOL


def test_greedy_fill_does_not_depend_on_pool_order():
    reordered = list(reversed(EXAMPLE_POOL))
    assert ids(greedy_fill(list(SLOTS), list(ALL_OPEN), reordered)) == ids(
        greedy_fill(list(SLOTS), list(ALL_OPEN), list(EXAMPLE_POOL))
    )


# --- optimise_lineup --------------------------------------------------------------------


def worked_example_roster() -> list[LineupPlayer]:
    """The 4.6 example: locked QB (18.4 actual), better TE on the bench."""
    return [
        make("QB", "QB", 22.0, slot=0, locked=True, actual=18.4, status="complete"),
        make("QB2", "QB", 20.0),
        make("RB15", "RB", 15.0, slot=1),
        make("RB12", "RB", 12.0, slot=2),
        make("RB9", "RB", 9.0, slot=6),
        make("WR14", "WR", 14.0, slot=3),
        make("WR8", "WR", 8.0, slot=4),
        make("TE11", "TE", 11.0),
        make("TE10", "TE", 10.0, slot=5),
        make("K", "K", 7.0, slot=7),
        make("DEF", "DEF", 6.0, slot=8),
    ]


def test_optimise_lineup_worked_example():
    lineup = optimise_lineup(list(LAYOUT), worked_example_roster())
    assert lineup.starters == (
        "QB",
        "RB15",
        "RB12",
        "WR14",
        "WR8",
        "TE11",
        "RB9",
        "K",
        "DEF",
    )
    assert lineup.bench == ("QB2", "TE10")
    assert lineup.optimal_total == pytest.approx(100.4)
    assert lineup.current_total == pytest.approx(99.4)


def test_optimise_lineup_returns_tuples_and_floats():
    lineup = optimise_lineup(list(LAYOUT), worked_example_roster())
    assert type(lineup.starters) is tuple
    assert type(lineup.bench) is tuple
    assert type(lineup.optimal_total) is float
    assert type(lineup.current_total) is float


def test_lineup_is_frozen():
    lineup = optimise_lineup(list(LAYOUT), worked_example_roster())
    with pytest.raises(FrozenInstanceError):
        lineup.optimal_total = 0.0  # type: ignore[misc]


def test_optimise_lineup_keeps_a_locked_starter_and_counts_his_actual_points():
    lineup = optimise_lineup(list(LAYOUT), worked_example_roster())
    assert lineup.starters[0] == "QB"
    assert "QB2" in lineup.bench


def test_optimise_lineup_counts_in_game_points_so_far():
    roster = [
        make("QB", "QB", 25.0, slot=0, locked=True, actual=3.2, status="in_game"),
        make("K", "K", 7.0, slot=7),
    ]
    lineup = optimise_lineup(list(LAYOUT), roster)
    assert lineup.optimal_total == pytest.approx(10.2)
    assert lineup.current_total == pytest.approx(10.2)


def test_optimise_lineup_leaves_a_locked_bench_player_on_the_bench():
    roster = [
        make("RB_LOCKED", "RB", 30.0, locked=True, actual=25.0, status="complete"),
        make("RB1", "RB", 5.0, slot=1),
        make("RB2", "RB", 4.0, slot=2),
    ]
    lineup = optimise_lineup(list(LAYOUT), roster)
    assert "RB_LOCKED" not in lineup.starters
    assert "RB_LOCKED" in lineup.bench
    assert lineup.starters[1] == "RB1" and lineup.starters[2] == "RB2"


def test_optimise_lineup_never_starts_or_benches_an_ir_player():
    roster = [
        make("RB_IR", "RB", 30.0, reserve=True),
        make("RB1", "RB", 5.0),
    ]
    lineup = optimise_lineup(list(LAYOUT), roster)
    assert "RB_IR" not in lineup.starters
    assert "RB_IR" not in lineup.bench


def test_optimise_lineup_keeps_empty_slots_in_place():
    # No kicker: slot 7 is None and the DEF stays at index 8.
    roster = [p for p in EXAMPLE_POOL if p.player_id != "K7"]
    lineup = optimise_lineup(list(LAYOUT), roster)
    assert len(lineup.starters) == 9
    assert lineup.starters[7] is None
    assert lineup.starters[8] == "DEF6"


def test_optimise_lineup_starts_one_kicker_and_benches_the_backup():
    roster = list(EXAMPLE_POOL) + [make("K3", "K", 3.0)]
    lineup = optimise_lineup(list(LAYOUT), roster)
    assert lineup.starters[7] == "K7"
    assert "K3" in lineup.bench


@pytest.mark.parametrize("status", ["bye", "canceled"])
def test_optimise_lineup_benches_a_player_who_scores_nothing(status):
    roster = list(EXAMPLE_POOL) + [make("QB_OFF", "QB", 30.0, status=status)]
    lineup = optimise_lineup(list(LAYOUT), roster)
    assert lineup.starters[0] == "QB20"
    assert "QB_OFF" in lineup.bench


def test_optimise_lineup_leaves_an_unknown_slot_type_empty():
    layout = ["QB", "IDP_FLEX", "RB", "BN"]
    roster = [
        make("QB20", "QB", 20.0),
        make("RB15", "RB", 15.0),
        make("RB12", "RB", 12.0),
    ]
    lineup = optimise_lineup(layout, roster)
    assert lineup.starters == ("QB20", None, "RB15")
    assert lineup.bench == ("RB12",)


def test_optimise_lineup_with_no_players():
    lineup = optimise_lineup(list(LAYOUT), [])
    assert lineup.starters == (None,) * 9
    assert lineup.bench == ()
    assert lineup.optimal_total == 0.0
    assert type(lineup.optimal_total) is float
    assert lineup.current_total == 0.0
    assert type(lineup.current_total) is float


def test_optimise_lineup_raises_on_an_inconsistent_lock():
    roster = [locked_at("P1", "RB", 3), locked_at("P2", "RB", 3)]
    with pytest.raises(ValueError):
        optimise_lineup(list(LAYOUT), roster)


def test_optimise_lineup_does_not_depend_on_roster_order():
    roster = worked_example_roster()
    forwards = optimise_lineup(list(LAYOUT), roster)
    backwards = optimise_lineup(list(LAYOUT), list(reversed(roster)))
    assert backwards.starters == forwards.starters
    assert set(backwards.bench) == set(forwards.bench)


def test_optimise_lineup_leaves_its_inputs_alone():
    layout, roster = list(LAYOUT), worked_example_roster()
    optimise_lineup(layout, roster)
    assert layout == LAYOUT
    assert roster == worked_example_roster()


# --- Brute force: greedy is exact for single-position players --------------------------
#
# The exhaustive search below uses its own eligibility table and scoring, so it
# doesn't trust the module's. It only covers layouts whose flex slots are nested
# (WRRB_FLEX inside FLEX inside SUPER_FLEX); that's the condition for greedy to be
# exact, and both leagues' layouts meet it.

_ELIGIBLE = {
    "QB": {"QB"},
    "RB": {"RB"},
    "WR": {"WR"},
    "TE": {"TE"},
    "K": {"K"},
    "DEF": {"DEF"},
    "WRRB_FLEX": {"RB", "WR"},
    "FLEX": {"RB", "WR", "TE"},
    "SUPER_FLEX": {"QB", "RB", "WR", "TE"},
}
_POINTS = [None, 0.0, 3.0, 5.5, 8.0, 8.0, 10.0, 12.0, 15.5]
_STATUSES = ["pre_game"] * 4 + ["bye", "canceled", None]
_POSITIONS = ["QB", "RB", "RB", "RB", "WR", "WR", "WR", "TE", "TE", "K", "DEF"]


def _score(p: LineupPlayer) -> float:
    if p.proj_points is None or p.game_status in ("bye", "canceled"):
        return 0.0
    return p.proj_points


def _best_possible(
    slots: list[str], open_: list[int], pool: list[LineupPlayer]
) -> float:
    """Highest total over every way of putting distinct players in the open slots."""
    best = 0.0

    def place(k: int, used: frozenset[int], total: float) -> None:
        nonlocal best
        if k == len(open_):
            best = max(best, total)
            return
        place(k + 1, used, total)  # leave this slot empty
        for i, p in enumerate(pool):
            if i not in used and p.eligible & _ELIGIBLE[slots[open_[k]]]:
                place(k + 1, used | {i}, total + _score(p))

    place(0, frozenset(), 0.0)
    return best


def _random_pool(rng: random.Random) -> list[LineupPlayer]:
    return [
        make(
            str(rng.randint(1, 9999)) + f"_{n}",  # unique IDs, varied string order
            rng.choice(_POSITIONS),
            rng.choice(_POINTS),
            status=rng.choice(_STATUSES),
            slot=rng.choice([None, None, rng.randrange(9)]),
        )
        for n in range(rng.randint(5, 9))
    ]


@pytest.mark.parametrize(
    "slots",
    [
        SLOTS,
        ["QB", "RB", "WR", "TE", "WRRB_FLEX", "FLEX", "SUPER_FLEX", "K"],
    ],
    ids=["real layout", "nested flexes"],
)
def test_greedy_fill_matches_brute_force(slots):
    rng = random.Random(20261013)
    for _ in range(150):
        pool = _random_pool(rng)
        open_ = sorted(rng.sample(range(len(slots)), rng.randint(1, len(slots))))
        chosen = greedy_fill(list(slots), list(open_), list(pool))
        assert sum(_score(p) for p in chosen.values()) == pytest.approx(
            _best_possible(slots, open_, pool)
        ), f"open={open_} pool={pool}"


# --- Backlog: multi-position players -----------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason="Backlog: best_fill (try each position of multi-position players)",
)
def test_multi_position_player_plays_where_he_is_worth_most():
    # Greedy fills the RB slots first and uses RB/TE13 there (101.0). Playing him
    # at TE frees an RB slot for RB12 and the flex for RB9 (104.0).
    pool = [
        make("QB20", "QB", 20.0),
        make("RB15", "RB", 15.0),
        make("RB12", "RB", 12.0),
        make("RB9", "RB", 9.0),
        make("WR14", "WR", 14.0),
        make("WR8", "WR", 8.0),
        make("TE6", "TE", 6.0),
        make("RBTE13", {"RB", "TE"}, 13.0),
        make("K7", "K", 7.0),
        make("DEF6", "DEF", 6.0),
    ]
    lineup = optimise_lineup(list(LAYOUT), pool)
    assert lineup.starters[5] == "RBTE13"
    assert lineup.optimal_total == pytest.approx(104.0)
