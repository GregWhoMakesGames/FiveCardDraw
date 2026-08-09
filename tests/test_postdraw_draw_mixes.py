"""Tests for opener draw mixes + checking-range protection."""

from __future__ import annotations

import json
import random
from pathlib import Path

from fivecarddraw.cards import parse_hand
from fivecarddraw.hand_rank import HandCategory, HandValue, evaluate_hand
from fivecarddraw.validation.postdraw_betting_m2 import Policy as M2Policy
from fivecarddraw.validation.postdraw_draw_mixes import (
    B_QUADS_D1,
    M2_DRAW,
    CheckMix,
    LEGAL_DRAW_COUNTS,
    MixDeal,
    MixPolicy,
    opener_draw_plan_for_action,
    play_mix_deal,
    _face_pair_counterfactual_ev,
)


FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "validation"
    / "postdraw_draw_mixes_summary.json"
)


def _hv(cat: int, *tb: int) -> HandValue:
    return HandValue(category=cat, tiebreak=tuple(tb))


def _deal(
    *,
    bucket: str = "one_pair",
    o_final: HandValue | None = None,
    d_final: HandValue | None = None,
    d: int = 3,
    cls: str = "pair_A",
    o_pair: int | None = 14,
    d_face: int | None = None,
    d_sp: bool = False,
    o_strong: bool = False,
) -> MixDeal:
    if o_final is None:
        o_final = _hv(HandCategory.ONE_PAIR, 14, 9, 8, 2)
    if d_final is None:
        d_final = _hv(HandCategory.HIGH_CARD, 13, 12, 9, 8, 2)
    return MixDeal(
        opener_class=cls,
        opener_start_pair=14 if cls.startswith("pair_") else None,
        d=d,
        opener_final=o_final,
        drawer_final=d_final,
        opener_final_pair=o_pair,
        drawer_final_pair=d_face,
        drawer_straight_plus=d_sp,
        opener_two_pair_plus=o_strong,
        opener_bucket=bucket,
    )


def test_legal_actions_pinned():
    assert LEGAL_DRAW_COUNTS["pair_A"] == (0, 1, 2, 3)
    assert LEGAL_DRAW_COUNTS["two_pair"] == (0, 1)
    assert LEGAL_DRAW_COUNTS["trips"] == (0, 1, 2)
    assert LEGAL_DRAW_COUNTS["four_of_a_kind"] == (0, 1)
    assert LEGAL_DRAW_COUNTS["straight"] == (0,)
    assert LEGAL_DRAW_COUNTS["full_house"] == (0,)
    assert LEGAL_DRAW_COUNTS["five_aces"] == (0,)


def test_pair_keep_rules():
    cards = parse_hand("As Ad 9c 8h 2d")
    p3 = opener_draw_plan_for_action(cards, "pair_A", 3)
    assert p3.n_draw == 3
    assert {str(c) for c in p3.keep} == {"As", "Ad"}

    p2 = opener_draw_plan_for_action(cards, "pair_A", 2)
    assert p2.n_draw == 2
    assert len(p2.keep) == 3
    assert {str(c) for c in p2.keep} >= {"As", "Ad", "9c"}

    p1 = opener_draw_plan_for_action(cards, "pair_A", 1)
    assert p1.n_draw == 1
    assert len(p1.keep) == 4
    assert {str(c) for c in p1.keep} == {"As", "Ad", "9c", "8h"}

    p0 = opener_draw_plan_for_action(cards, "pair_A", 0)
    assert p0.n_draw == 0
    assert len(p0.keep) == 5


def test_two_pair_and_trips_and_quads_keeps():
    tp = parse_hand("As Ad 9c 9h 2d")
    plan = opener_draw_plan_for_action(tp, "two_pair_aces_up", 1)
    assert plan.n_draw == 1
    assert len(plan.keep) == 4
    assert "2d" not in {str(c) for c in plan.keep}

    trips = parse_hand("9s 9d 9c 8h 2d")
    d2 = opener_draw_plan_for_action(trips, "trips", 2)
    assert d2.n_draw == 2 and len(d2.keep) == 3
    d1 = opener_draw_plan_for_action(trips, "trips", 1)
    assert d1.n_draw == 1 and len(d1.keep) == 4
    assert "8h" in {str(c) for c in d1.keep}

    quads = parse_hand("As Ad Ac Ah 9c")
    q1 = opener_draw_plan_for_action(quads, "four_of_a_kind", 1)
    assert q1.n_draw == 1
    assert len(q1.keep) == 4
    assert all(c.rank == 14 for c in q1.keep)
    # Quads redraw does not break the hand category for any replacement
    for cid in range(52):
        if cid in {c.card_id for c in quads}:
            continue
        from fivecarddraw.cards import card_from_id

        final = evaluate_hand((*q1.keep, card_from_id(cid)))
        assert final.category >= HandCategory.FOUR_OF_A_KIND
        break


def test_check_mix_lets_strong_hand_check():
    deal = _deal(
        bucket="trips",
        o_final=_hv(HandCategory.THREE_OF_A_KIND, 9, 8, 2),
        d_final=_hv(HandCategory.ONE_PAIR, 14, 9, 8, 2),
        o_pair=None,
        d_face=14,
        o_strong=True,
        d=2,
        cls="trips",
    )
    pol = MixPolicy(
        m2=M2Policy(None, 14, None),
        check_mix=CheckMix(0.0, 1.0, 0.0),  # always check trips
    )
    rng = random.Random(0)
    ev, flags = play_mix_deal(deal, pol, rng)
    assert flags["opener_strong_check"]
    assert flags["drawer_stab"]  # AA face pair stabs
    assert flags["opener_call_stab"]  # strong calls
    # Call 4 into pot 6 → pot 14; opener trips beats AA → +10 net? 
    # invested 4, win 14 → +10
    assert ev == 10.0


def test_face_pair_stab_delta_negative_when_always_calling_strong():
    """If check range is pure trips, AA stab into a calling strong hand is bad."""
    deal = _deal(
        bucket="trips",
        o_final=_hv(HandCategory.THREE_OF_A_KIND, 9, 8, 2),
        d_final=_hv(HandCategory.ONE_PAIR, 14, 9, 8, 2),
        o_pair=None,
        d_face=14,
        o_strong=True,
        d=2,
        cls="trips",
    )
    pol = MixPolicy(m2=M2Policy(None, 14, None), check_mix=CheckMix(0, 1, 0))
    cf = _face_pair_counterfactual_ev(deal, pol)
    assert cf is not None
    ev_stab, ev_check = cf
    assert ev_stab < ev_check  # stabbing into trips loses chips vs check-down


def test_draw_policy_defaults():
    assert M2_DRAW.quads_d == 0
    assert B_QUADS_D1.quads_d == 1
    assert B_QUADS_D1.n_draw_for("four_of_a_kind") == 1
    assert B_QUADS_D1.n_draw_for("straight") == 0
    assert B_QUADS_D1.n_draw_for("pair_K") == 3


def test_fixture_summary_patterns():
    assert FIXTURE.exists(), "run analyze-postdraw-draw-mixes --write-fixture"
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert data["meta"]["predraw_pot"] == 6.0
    assert data["meta"]["big_bet"] == 4.0
    assert data["meta"]["seed"] == 20260809

    findings = data["findings"]
    assert findings["quads_prefer_d1"] is True
    # Quads d=1 should not hurt showdown vs this caller
    assert findings["quads_d1_win"] + 0.01 >= findings["quads_stand_win"]
    # Trips drawing two should improve boat+ vs standing
    assert findings["trips_d2_boat_plus"] > findings["trips_stand_boat_plus"]
    # Two pair d=1 should create some boat+ vs zero when standing
    assert findings["two_pair_d1_boat_plus"] > findings["two_pair_stand_boat_plus"]

    assert "recommendations" in data and len(data["recommendations"]) >= 5
    quads_rec = next(r for r in data["recommendations"] if r["class"] == "four_of_a_kind")
    assert "d=1" in quads_rec["draw_action"]

    # Stage C structure
    assert data["stage_c"]["summaries"]
    aa = next(s for s in data["stage_c"]["summaries"] if "stab=AA|" in s["stab"])
    assert "best_check_mix" in aa
    assert aa["baseline_stab_delta"] is not None
