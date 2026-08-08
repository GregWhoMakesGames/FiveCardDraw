"""Smoke checks for one-card draw pot-odds helpers."""

from fivecarddraw.cards import parse_hand
from fivecarddraw.hand_rank import can_open_jacks_or_better
from fivecarddraw.validation.draw_call_odds import (
    FIRST_CALL_MIN_OUTS,
    FIRST_CALL_REQUIRED,
    SECOND_CALL_MIN_OUTS,
    SECOND_CALL_REQUIRED,
    UNKNOWN_AFTER_HERO,
    build_keep4_outs_table,
    expand_keeps_to_hands,
    outs_set,
)


def test_pot_odds_thresholds():
    assert abs(FIRST_CALL_REQUIRED - 1 / 3) < 1e-12
    assert abs(SECOND_CALL_REQUIRED - 1 / 4) < 1e-12
    assert UNKNOWN_AFTER_HERO == 48
    assert FIRST_CALL_MIN_OUTS == 16
    assert SECOND_CALL_MIN_OUTS == 12  # 12/48 = 1/4, not outs/43


def test_bug_sf_draw_clears_2to1():
    cards = parse_hand("Bu 9h 8h 7h 2c")
    assert not can_open_jacks_or_better(cards)
    table = build_keep4_outs_table(
        list(range(53)), min_outs=SECOND_CALL_MIN_OUTS, progress=False
    )
    hands = expand_keeps_to_hands(
        table,
        min_outs=FIRST_CALL_MIN_OUTS,
        required_equity=FIRST_CALL_REQUIRED,
    )
    target = frozenset(c.card_id for c in cards)
    match = [h for h in hands if frozenset(c.card_id for c in h.cards) == target]
    assert match, "expected Bu 9h8h7h2c among 2:1 draws"
    assert match[0].outs >= 16
    assert match[0].undealt == 48
    assert match[0].hit_prob + 1e-15 >= FIRST_CALL_REQUIRED


def test_four_flush_straight_outs_use_denom_48():
    keep_ids = tuple(
        sorted(c.card_id for c in parse_hand("9h 8h 7h 6h 2c") if str(c) != "2c")
    )
    outs = outs_set(keep_ids, set(range(53)))
    assert len(outs) >= 15
    # Borderline 2:1 is 16/48; many four-flush straights land near there.
    assert len(outs) / 48 >= SECOND_CALL_REQUIRED  # at least clears 3:1 approx
