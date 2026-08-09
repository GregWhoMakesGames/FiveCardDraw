"""Unit tests for showdown matrix helpers + fixture pins."""

from __future__ import annotations

import random

from fivecarddraw.cards import parse_hand
from fivecarddraw.hand_rank import HandCategory, evaluate_hand
from fivecarddraw.validation.draw_call_odds import DrawHandResult, classify_draw
from fivecarddraw.validation.showdown_matrix import (
    CASE_DESCRIPTIONS,
    OPENER_CLASSES,
    OutcomeAccum,
    classify_opener,
    dealer_draw_plan,
    load_showdown_matrix,
    showdown_pair_exact_caller_draw,
    _case_hits,
)


def test_classify_opener_fine_splits():
    assert classify_opener(parse_hand("As Ad 9c 8h 2d")) == "pair_A"
    assert classify_opener(parse_hand("Ks Kd 9c 8h 2d")) == "pair_K"
    assert classify_opener(parse_hand("As Kd Ac Kh 2d")) == "two_pair_aces_up"
    assert classify_opener(parse_hand("Ks Kd 9c 9h 2d")) == "two_pair"
    assert classify_opener(parse_hand("As Ad Ac 8h 2d")) == "trips_A"
    assert classify_opener(parse_hand("9s 9d 9c 8h 2d")) == "trips"
    assert classify_opener(parse_hand("As Kd Qc Jh Td")) == "straight"
    assert classify_opener(parse_hand("As Ks 9s 8s 2s")) == "flush"
    # Non-opener
    assert classify_opener(parse_hand("Ts Td 9c 8h 2d")) is None


def test_dealer_draw_policies_pinned():
    aa = parse_hand("As Ad 9c 8h 2d")
    plan = dealer_draw_plan(aa, "pair_A")
    assert plan.n_draw == 3
    assert {str(c) for c in plan.keep} == {"As", "Ad"}

    tp = parse_hand("As Ad 9c 9h 2d")
    plan = dealer_draw_plan(tp, "two_pair_aces_up")
    assert plan.n_draw == 0
    assert len(plan.keep) == 5

    trips = parse_hand("9s 9d 9c 8h 2d")
    plan = dealer_draw_plan(trips, "trips")
    assert plan.n_draw == 2
    assert len(plan.keep) == 3
    assert all(c.rank == 9 for c in plan.keep)

    straight = parse_hand("As Kd Qc Jh Td")
    plan = dealer_draw_plan(straight, "straight")
    assert plan.n_draw == 0


def test_case_1_and_2_pat_straight_vs_flush_draw():
    """Pat wheel straight vs flush-completing caller."""
    dealer = parse_hand("Ah 2d 3c 4h 5s")
    assert classify_opener(dealer) == "straight"
    # Bug SF/flush-ish keep — use an explicit caller keep of 4 hearts + discard
    caller_cards = parse_hand("Kh Qh Jh 9h 2c")
    keep = tuple(c for c in caller_cards if str(c) != "2c")
    caller = DrawHandResult(
        cards=caller_cards,
        discard=next(c for c in caller_cards if str(c) == "2c"),
        keep=keep,
        outs=16,
        undealt=48,
        has_bug=False,
        draw_class=classify_draw(keep),
    )
    accum = OutcomeAccum()
    plan = dealer_draw_plan(dealer, "straight")
    showdown_pair_exact_caller_draw(
        dealer_cards=dealer,
        dealer_plan=plan,
        caller=caller,
        opener_class="straight",
        accum=accum,
    )
    assert accum.weight > 0
    # Some hearts make a flush (beat straight → case 2); non-flush miss/pair → not 2
    assert accum.cases["2"] > 0
    assert accum.caller_wins > 0
    assert accum.dealer_wins > 0


def test_case_1b_pat_beats_face_pair():
    dealer = parse_hand("Ah 2d 3c 4h 5s")
    dealer_v = evaluate_hand(dealer)
    # Synthetic: caller ends as AA one pair
    caller_final = evaluate_hand(parse_hand("As Ad 9c 8h 2d"))
    assert caller_final.category == HandCategory.ONE_PAIR
    hits = _case_hits(
        opener_class="straight",
        dealer_started_straight_plus=True,
        dealer_started_two_pair_or_trips=False,
        dealer_pair_rank=None,
        dealer_final=dealer_v,
        caller_final=caller_final,
        cmp=1,
    )
    assert hits == ["1b"]


def test_case_4b_two_pair_loses_to_straight():
    dealer_v = evaluate_hand(parse_hand("As Ad 9c 9h 2d"))
    caller_v = evaluate_hand(parse_hand("Ah 2c 3d 4h 5s"))
    hits = _case_hits(
        opener_class="two_pair_aces_up",
        dealer_started_straight_plus=False,
        dealer_started_two_pair_or_trips=True,
        dealer_pair_rank=None,
        dealer_final=dealer_v,
        caller_final=caller_v,
        cmp=-1,
    )
    assert "4b" in hits


def test_case_8_jj_tie_and_8b_loss():
    jj = evaluate_hand(parse_hand("Js Jd 9c 8h 2d"))
    hits = _case_hits(
        opener_class="pair_J",
        dealer_started_straight_plus=False,
        dealer_started_two_pair_or_trips=False,
        dealer_pair_rank=11,
        dealer_final=jj,
        caller_final=jj,
        cmp=0,
    )
    assert hits == ["8"]
    aa = evaluate_hand(parse_hand("As Ad 9c 8h 2d"))
    hits = _case_hits(
        opener_class="pair_J",
        dealer_started_straight_plus=False,
        dealer_started_two_pair_or_trips=False,
        dealer_pair_rank=11,
        dealer_final=jj,
        caller_final=aa,
        cmp=-1,
    )
    assert hits == ["8b"]


def test_fixture_pins_main_cells():
    data = load_showdown_matrix()
    assert data["meta"]["discard_policies"]["dealer_two_pair"] == "stand_pat"
    assert data["meta"]["discard_policies"]["dealer_trips"] == "keep_trips_draw2"
    assert data["meta"]["discard_policies"]["dealer_one_pair"] == "keep_pair_draw3"
    assert set(data["opener_combo_counts"]) == set(OPENER_CLASSES)
    assert data["opener_combo_counts"]["five_aces"] == 1
    assert data["opener_combo_counts"]["pair_A"] == 137_904
    assert data["opener_combo_counts"]["straight"] == 20_532

    by = {r["opener_class"]: r for r in data["rows"]}
    assert set(by) == set(OPENER_CLASSES)

    # Pat made hands beat drawing callers most of the time.
    # Wheel-heavy straights lose more often to flush completions than flushes do.
    assert by["straight"]["outcomes"]["dealer_wins"] > 0.70
    assert by["straight"]["cases"]["1b"] > 0.04
    assert by["straight"]["cases"]["2"] < 0.30
    for cls in ("flush", "full_house", "four_of_a_kind", "straight_flush"):
        assert by[cls]["outcomes"]["dealer_wins"] > 0.90
        assert by[cls]["cases"]["1b"] > 0.03
        assert by[cls]["cases"]["2"] < 0.10

    # five_aces never loses
    assert by["five_aces"]["outcomes"]["dealer_wins"] == 1.0
    assert by["five_aces"]["cases"]["2"] == 0.0

    # Two pair / trips: meaningful 4b (lose to completed draws)
    for cls in ("two_pair", "two_pair_aces_up", "trips", "trips_K", "trips_A"):
        assert by[cls]["cases"]["4b"] > 0.15
        assert by[cls]["cases"]["4"] > 0.05
        assert by[cls]["outcomes"]["dealer_wins"] > 0.55

    # Face pairs: lose to straight+ at ~caller's hit rate scale; hierarchy
    assert by["pair_A"]["cases"]["5c"] > 0.15
    assert by["pair_K"]["cases"]["6c"] > 0.15
    assert by["pair_Q"]["cases"]["7c"] > 0.15
    assert by["pair_J"]["cases"]["8c"] > 0.15
    # AA beats/ties face pairs more often than JJ merely ties
    assert by["pair_A"]["cases"]["5"] > by["pair_J"]["cases"]["8"]
    # KK/QQ/JJ sometimes lose to higher face pairs via bug→AA etc.
    assert by["pair_K"]["cases"]["6b"] > 0.0
    assert by["pair_Q"]["cases"]["7b"] > 0.0
    assert by["pair_J"]["cases"]["8b"] > 0.0

    for cid in CASE_DESCRIPTIONS:
        assert cid in by["straight"]["cases"]
