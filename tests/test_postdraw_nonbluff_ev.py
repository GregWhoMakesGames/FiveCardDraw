"""Tests for non-bluff max-EV by class × draw count."""

from __future__ import annotations

import json
from pathlib import Path

from fivecarddraw.cards import parse_hand
from fivecarddraw.hand_rank import HandCategory, HandValue, evaluate_hand
from fivecarddraw.validation.draw_call_odds import DrawHandResult, classify_draw
from fivecarddraw.validation.postdraw_betting_m2 import PREDRAW_POT, Policy as M2Policy
from fivecarddraw.validation.postdraw_draw_mixes import (
    LEGAL_DRAW_COUNTS,
    opener_draw_plan_for_action,
)
from fivecarddraw.validation.postdraw_nonbluff_ev import (
    CALLER_ALL,
    HONEST_POLICY,
    LOCKED_BN_DRAW,
    NonbluffDeal,
    caller_ev_from_bn,
    case_ids_for_deal,
    generate_nonbluff_deals,
    play_honest_deal,
)
from fivecarddraw.validation.showdown_matrix import classify_opener


FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "validation"
    / "postdraw_nonbluff_ev_summary.json"
)


def _hv(cat: int, *tb: int) -> HandValue:
    return HandValue(category=cat, tiebreak=tuple(tb))


def _deal(
    *,
    cls: str = "pair_A",
    caller_class: str = CALLER_ALL,
    d: int = 3,
    caller_d: int = 1,
    o_final: HandValue | None = None,
    d_final: HandValue | None = None,
    o_pair: int | None = 14,
    d_face: int | None = None,
    d_sp: bool = False,
    o_strong: bool = False,
) -> NonbluffDeal:
    if o_final is None:
        o_final = _hv(HandCategory.ONE_PAIR, 14, 9, 8, 2)
    if d_final is None:
        d_final = _hv(HandCategory.HIGH_CARD, 13, 12, 9, 8, 2)
    return NonbluffDeal(
        opener_class=cls,
        caller_class=caller_class,
        d=d,
        caller_d=caller_d,
        opener_start_pair=14 if cls.startswith("pair_") else None,
        opener_final=o_final,
        drawer_final=d_final,
        opener_final_pair=o_pair,
        drawer_final_pair=d_face,
        drawer_straight_plus=d_sp,
        opener_two_pair_plus=o_strong,
    )


def test_honest_policy_is_not_a_bluff_mix():
    assert HONEST_POLICY.opener_lead_min is None
    assert HONEST_POLICY.drawer_stab_min == 14
    assert HONEST_POLICY.drawer_raise_min is None
    assert LOCKED_BN_DRAW.pair_d == 3
    assert LOCKED_BN_DRAW.two_pair_d == 1
    assert LOCKED_BN_DRAW.trips_d == 2
    assert LOCKED_BN_DRAW.quads_d == 1


def test_legal_draw_counts_match_locked_policies():
    assert LEGAL_DRAW_COUNTS["pair_A"] == (0, 1, 2, 3)
    assert LEGAL_DRAW_COUNTS["two_pair"] == (0, 1)
    assert LEGAL_DRAW_COUNTS["trips"] == (0, 1, 2)
    assert LEGAL_DRAW_COUNTS["four_of_a_kind"] == (0, 1)
    assert LEGAL_DRAW_COUNTS["straight"] == (0,)


def test_zero_sum_check_check_when_bn_wins():
    deal = _deal()
    ev_bn, ev_caller, flags = play_honest_deal(deal, HONEST_POLICY)
    assert flags["opener_pair_check"]
    assert flags["showdown"]
    assert ev_bn == PREDRAW_POT
    assert ev_caller == 0.0
    assert ev_bn + ev_caller == PREDRAW_POT


def test_zero_sum_when_caller_hits_straight_and_bn_folds_pair():
    """JJ is below the AA call-down, so it folds a straight+ stab. AA would call."""
    deal = _deal(
        cls="pair_J",
        o_final=_hv(HandCategory.ONE_PAIR, 11, 9, 8, 2),
        d_final=_hv(HandCategory.STRAIGHT, 14, 13, 12, 11, 10),
        o_pair=11,
        d_face=None,
        d_sp=True,
        o_strong=False,
    )
    ev_bn, ev_caller, flags = play_honest_deal(deal, HONEST_POLICY)
    assert flags["drawer_stab"]
    assert flags["opener_fold_to_stab"]
    assert ev_bn == 0.0
    assert ev_caller == PREDRAW_POT
    assert abs(ev_bn + ev_caller - PREDRAW_POT) < 1e-9

    aa = _deal(
        o_final=_hv(HandCategory.ONE_PAIR, 14, 9, 8, 2),
        d_final=_hv(HandCategory.STRAIGHT, 14, 13, 12, 11, 10),
        o_pair=14,
        d_face=None,
        d_sp=True,
        o_strong=False,
    )
    ev_bn, ev_caller, flags = play_honest_deal(aa, HONEST_POLICY)
    assert flags["opener_call_stab"]
    assert ev_bn == -4.0
    assert ev_caller == 10.0
    assert abs(ev_bn + ev_caller - PREDRAW_POT) < 1e-9


def test_two_pair_value_bets_and_caller_ev_complements():
    deal = _deal(
        cls="two_pair",
        d=1,
        o_final=_hv(HandCategory.TWO_PAIR, 14, 9, 2),
        d_final=_hv(HandCategory.HIGH_CARD, 13, 12, 9, 8, 2),
        o_pair=None,
        d_face=None,
        d_sp=False,
        o_strong=True,
    )
    ev_bn, ev_caller, flags = play_honest_deal(deal, HONEST_POLICY)
    assert not flags["opener_pair_check"]
    assert not flags["showdown"]  # miss folds to the value bet
    assert ev_bn == PREDRAW_POT
    assert caller_ev_from_bn(ev_bn) == ev_caller


def test_no_check_mix_on_strong_vs_aa_stab_policy():
    """Honest line still bets two pair+; AA stab never sees a strong check."""
    deal = _deal(
        cls="trips",
        d=2,
        o_final=_hv(HandCategory.THREE_OF_A_KIND, 9, 8, 2),
        d_final=_hv(HandCategory.ONE_PAIR, 14, 9, 8, 2),
        o_pair=None,
        d_face=14,
        d_sp=False,
        o_strong=True,
    )
    _ev_bn, _ev_caller, flags = play_honest_deal(deal, HONEST_POLICY)
    assert flags["drawer_raise"] or flags["showdown"]
    assert not flags["opener_pair_check"]
    # Face pair calls the value bet (M2 street); BN trips wins.
    assert flags["showdown"]
    assert flags["opener_wins_sd"]


def test_case_ids_link_pat_straight_vs_drawer_straight():
    deal = _deal(
        cls="straight",
        d=0,
        o_final=_hv(HandCategory.STRAIGHT, 14, 5, 4, 3, 2),
        d_final=_hv(HandCategory.FLUSH, 13, 12, 9, 8, 2),
        o_pair=None,
        d_face=None,
        d_sp=True,
        o_strong=True,
    )
    hits = case_ids_for_deal(deal)
    assert "2" in hits  # BN straight+ loses to drawer straight+


def test_generator_keep_rules_and_caller_stand():
    aa = parse_hand("As Ad 9c 8h 2d")
    assert classify_opener(aa) == "pair_A"
    ids = tuple(sorted(c.card_id for c in aa))
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
    inventory = {"pair_A": [ids]}
    deals_d3 = generate_nonbluff_deals(
        inventory,
        [caller],
        "pair_A",
        3,
        caller_d=1,
        n_deals=8,
        seed=1,
    )
    assert len(deals_d3) == 8
    assert all(d.d == 3 and d.caller_d == 1 for d in deals_d3)

    plan = opener_draw_plan_for_action(aa, "pair_A", 3)
    assert plan.n_draw == 3

    stand = generate_nonbluff_deals(
        inventory,
        [caller],
        "pair_A",
        3,
        caller_d=0,
        n_deals=4,
        seed=2,
    )
    assert len(stand) == 4
    # Standing caller keeps the original 5 — not a made straight+ here.
    for d in stand:
        assert d.caller_d == 0
        assert d.drawer_final == evaluate_hand(caller_cards)
        assert not d.drawer_straight_plus


def test_fixture_summary_patterns():
    assert FIXTURE.exists(), "run analyze-postdraw-nonbluff-ev --write-fixture"
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    meta = data["meta"]
    assert meta["predraw_pot"] == 6.0
    assert meta["big_bet"] == 4.0
    assert meta["seed"] == 20260901
    assert "deferred" in meta["bluffing"].lower()
    assert meta["honest_policy"] == M2Policy(None, 14, None).key
    assert data["findings"]["bluff_deferred"] is True

    findings = data["findings"]
    # Pair d=3 is the max-EV non-bluff improvement line (MC tolerance).
    assert findings["pair_A_d3_beats_d2"] is True
    assert findings["pair_J_d3_beats_d2"] is True
    assert findings["pair_A_best_d"] == 3
    assert findings["two_pair_d1_beats_stand"] is True
    assert findings["trips_d2_beats_stand"] is True
    # Quads d=1 is EV-neutral vs stand (signal only).
    assert findings["quads_d1_vs_stand_delta"] is not None
    assert abs(findings["quads_d1_vs_stand_delta"]) < 0.35

    best = {r["opener_class"]: r for r in data["best_bn_draw"]}
    assert best["pair_A"]["best_bn_d"] == 3
    assert best["pair_J"]["best_bn_d"] == 3
    assert best["two_pair"]["best_bn_d"] == 1
    assert best["trips"]["best_bn_d"] in (1, 2)
    assert best["straight"]["best_bn_d"] == 0
    assert best["four_of_a_kind"]["best_bn_d"] in (0, 1)

    # Both sides labeled; they sum to the sunk pot within rounding.
    for r in data["bn_grid"]:
        assert abs(r["ev_bn"] + r["ev_caller"] - 6.0) < 0.02
        assert r["caller_class"] == CALLER_ALL
        assert r["caller_d"] == 1

    assert findings["caller_keep4_beats_stand"] is True
    fork = data["caller_d_fork"]
    assert {r["caller_d"] for r in fork} == {0, 1}

    recs = data["recommendations"]
    assert any("Bluff" in r["notes"] or "bluff" in r["notes"] for r in recs)
    assert any(r["side"] == "caller" for r in recs)
    assert any(r["side"] == "BN" and "pair" in r["class"] for r in recs)
