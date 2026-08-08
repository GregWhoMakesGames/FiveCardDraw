"""Pin draw-call inventory from checked-in fixture (no full re-enum)."""

import json
from pathlib import Path

from fivecarddraw.validation.cascade_odds import (
    BUG_2TO1_COMBOS,
    CALL_2TO1_COMBOS,
    FFS13_COMBOS,
    FFS16_COMBOS,
)
from fivecarddraw.validation.draw_call_odds import (
    FIRST_CALL_MIN_OUTS,
    SECOND_CALL_MIN_OUTS,
    UNKNOWN_AFTER_HERO,
)


FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "validation" / "draw_call_odds.json"
)


def test_draw_call_odds_fixture_matches_constants():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert data["meta"]["outs_denominator"] == UNKNOWN_AFTER_HERO == 48
    assert data["meta"]["first_call"]["min_outs"] == FIRST_CALL_MIN_OUTS == 16
    assert data["meta"]["second_call"]["min_outs"] == SECOND_CALL_MIN_OUTS == 12

    c = data["call_2to1"]
    assert c["total_combos"] == CALL_2TO1_COMBOS == 18_396
    assert c["with_bug"] == BUG_2TO1_COMBOS == 17_280
    assert c["without_bug"] == FFS16_COMBOS == 1_116
    assert sum(c["outs_histogram"].values()) == 18_396
    assert sum(row["combos"] for row in c["by_class"]) == 18_396

    s = data["call_3to1_candidates"]
    assert s["ffs13_combos"] == FFS13_COMBOS == 4_224
    assert s["ffs16_combos"] == FFS16_COMBOS
    assert s["without_bug"] == FFS13_COMBOS + FFS16_COMBOS
