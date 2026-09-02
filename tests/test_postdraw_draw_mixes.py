"""Tests for opener draw mixes + checking-range protection."""

from __future__ import annotations

import inspect
import json
import random
from pathlib import Path

import pytest

from fivecarddraw.cards import card_from_id, parse_hand
from fivecarddraw.hand_rank import HandCategory, HandValue, evaluate_hand
from fivecarddraw.validation.postdraw_betting_m2 import Policy as M2Policy
from fivecarddraw.validation.postdraw_draw_mixes import (
    B_QUADS_D1,
    B_TP_D1_QUADS_D1,
    B_TP_TRIPS_QUADS_D1,
    LEGAL_DRAW_COUNTS,
    M2_DRAW,
    STAGE_B_DRAW_POLICIES,
    CheckMix,
    MixDeal,
    MixPolicy,
    evaluate_mix_policy,
    legal_actions_for_class,
    opener_draw_plan_for_action,
    play_mix_deal,
    run_ladder,
    run_stage_c,
    stage_b_draw_policy,
    _face_pair_counterfactual_ev,
)
from fivecarddraw.validation.showdown_matrix import OPENER_CLASSES


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
    for cls in ("pair_J", "pair_Q", "pair_K", "pair_A"):
        assert LEGAL_DRAW_COUNTS[cls] == (0, 1, 2, 3)
        assert legal_actions_for_class(cls) == (0, 1, 2, 3)
    for cls in ("two_pair", "two_pair_aces_up"):
        assert LEGAL_DRAW_COUNTS[cls] == (0, 1)
    for cls in ("trips", "trips_K", "trips_A"):
        assert LEGAL_DRAW_COUNTS[cls] == (0, 1, 2)
    assert LEGAL_DRAW_COUNTS["four_of_a_kind"] == (0, 1)
    for cls in ("straight", "flush", "full_house", "straight_flush", "five_aces"):
        assert LEGAL_DRAW_COUNTS[cls] == (0,)
        assert legal_actions_for_class(cls) == (0,)
    assert set(LEGAL_DRAW_COUNTS) == set(OPENER_CLASSES)


@pytest.mark.parametrize(
    "hand,cls,n_draw",
    [
        ("As Ad 9c 8h 2d", "pair_A", 4),
        ("As Ad 9c 9h 2d", "two_pair_aces_up", 2),
        ("As Ad 9c 9h 2d", "two_pair_aces_up", 3),
        ("9s 9d 9c 8h 2d", "trips", 3),
        ("As Ad Ac Ah 9c", "four_of_a_kind", 2),
        ("As Kd Qc Jh Td", "straight", 1),
        ("As Ks 9s 8s 2s", "flush", 1),
        ("As Ad Ac 9h 9s", "full_house", 1),
        ("As Ks Qs Js Ts", "straight_flush", 1),
        ("Bu As Ad Ac Ah", "five_aces", 1),
    ],
)
def test_illegal_draw_counts_raise(hand: str, cls: str, n_draw: int):
    cards = parse_hand(hand)
    with pytest.raises(ValueError, match="illegal draw action"):
        opener_draw_plan_for_action(cards, cls, n_draw)


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
    blocked = {c.card_id for c in quads}
    # Quads redraw never breaks the hand vs this caller (cannot make quads).
    for cid in range(53):
        if cid in blocked:
            continue
        final = evaluate_hand((*q1.keep, card_from_id(cid)))
        assert final.category >= HandCategory.FOUR_OF_A_KIND

    tp0 = opener_draw_plan_for_action(tp, "two_pair_aces_up", 0)
    assert tp0.n_draw == 0 and len(tp0.keep) == 5


def test_bug_is_highest_kicker_on_pair_and_trips():
    # Bug is an ace, so it cannot be a kicker to a pair of aces (that is trips).
    pair = parse_hand("Ks Kd Bu 8h 2d")
    p2 = opener_draw_plan_for_action(pair, "pair_K", 2)
    assert {str(c) for c in p2.keep} == {"Ks", "Kd", "Bu"}
    p1 = opener_draw_plan_for_action(pair, "pair_K", 1)
    assert {str(c) for c in p1.keep} == {"Ks", "Kd", "Bu", "8h"}

    trips = parse_hand("9s 9d 9c Bu 2d")
    d1 = opener_draw_plan_for_action(trips, "trips", 1)
    keep = {str(c) for c in d1.keep}
    assert keep == {"9s", "9d", "9c", "Bu"}


def test_pair_draw1_cannot_make_boat():
    """Stage A mechanical fact: keep pair + two kickers, one card in → no boat+."""
    cards = parse_hand("As Ad 9c 8h 2d")
    plan = opener_draw_plan_for_action(cards, "pair_A", 1)
    blocked = {c.card_id for c in cards}
    for cid in range(53):
        if cid in blocked:
            continue
        final = evaluate_hand((*plan.keep, card_from_id(cid)))
        assert final.category < HandCategory.FULL_HOUSE


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


def test_check_mix_two_pair_on_d1_lets_aa_stab():
    """Locked C public line: two pair lives on d=1, not the old pat d=0 stand."""
    deal = _deal(
        bucket="two_pair",
        o_final=_hv(HandCategory.TWO_PAIR, 14, 9, 2),
        d_final=_hv(HandCategory.ONE_PAIR, 14, 9, 8, 2),
        o_pair=None,
        d_face=14,
        o_strong=True,
        d=1,
        cls="two_pair",
    )
    pol = MixPolicy(
        m2=M2Policy(None, 14, None),
        check_mix=CheckMix(1.0, 0.0, 0.0),
    )
    ev, flags = play_mix_deal(deal, pol, random.Random(0))
    assert flags["opener_strong_check"]
    assert flags["drawer_stab"]
    assert flags["opener_call_stab"]
    assert ev == 10.0
    cf = _face_pair_counterfactual_ev(deal, pol)
    assert cf is not None
    ev_stab, ev_check = cf
    assert ev_stab < ev_check


def test_one_pair_still_checks_when_strong_check_mix_is_on():
    deal = _deal(d=3, o_strong=False, o_pair=14, d_face=14)
    pol = MixPolicy(
        m2=M2Policy(None, 14, None),
        check_mix=CheckMix(1.0, 1.0, 1.0),
    )
    _ev, flags = play_mix_deal(deal, pol, random.Random(0))
    assert flags["opener_pair_check"]
    assert not flags["opener_strong_check"]
    assert flags["drawer_stab"]
    assert flags["opener_call_stab"]  # AA calls AA stab


def test_boat_plus_check_mix_on_pat_straight():
    deal = _deal(
        bucket="boat_plus",
        o_final=_hv(HandCategory.FLUSH, 14, 12, 9, 8, 3),
        d_final=_hv(HandCategory.ONE_PAIR, 14, 9, 8, 2),
        o_pair=None,
        d_face=14,
        o_strong=True,
        d=0,
        cls="flush",
    )
    always = MixPolicy(m2=M2Policy(None, 14, None), check_mix=CheckMix(0, 0, 1.0))
    _ev, flags = play_mix_deal(deal, always, random.Random(0))
    assert flags["opener_strong_check"]
    never = MixPolicy(m2=M2Policy(None, 14, None), check_mix=CheckMix())
    _ev, flags = play_mix_deal(deal, never, random.Random(0))
    # Zero mix delegates to M2, which always bets two pair+ (no strong_* flags).
    assert not flags.get("opener_strong_check")
    assert flags["showdown"]


def test_partial_trips_check_mix_is_not_pure():
    deal = _deal(
        bucket="trips",
        o_final=_hv(HandCategory.THREE_OF_A_KIND, 9, 8, 2),
        d_final=_hv(HandCategory.HIGH_CARD, 13, 12, 9, 8, 2),
        o_pair=None,
        d_face=None,
        o_strong=True,
        d=2,
        cls="trips",
    )
    pol = MixPolicy(m2=M2Policy(None, 14, None), check_mix=CheckMix(0.0, 0.5, 0.0))
    checks = 0
    bets = 0
    for seed in range(200):
        _ev, flags = play_mix_deal(deal, pol, random.Random(seed))
        checks += int(flags["opener_strong_check"])
        bets += int(flags["opener_strong_bet"])
    assert 50 < checks < 150
    assert checks + bets == 200


def test_check_mix_is_global_not_conditional_on_d():
    """Current CheckMix ignores public d; C-primary two pair (d=1) and trips (d=2)
    share one fraction. Stage C wants mixes reported/applied per d."""
    two_pair = _deal(
        bucket="two_pair",
        o_final=_hv(HandCategory.TWO_PAIR, 14, 9, 2),
        o_pair=None,
        o_strong=True,
        d=1,
        cls="two_pair",
    )
    two_pair_pat = _deal(
        bucket="two_pair",
        o_final=_hv(HandCategory.TWO_PAIR, 14, 9, 2),
        o_pair=None,
        o_strong=True,
        d=0,
        cls="two_pair",
    )
    pol = MixPolicy(m2=M2Policy(None, 14, None), check_mix=CheckMix(1.0, 0.0, 0.0))
    _, f1 = play_mix_deal(two_pair, pol, random.Random(0))
    _, f0 = play_mix_deal(two_pair_pat, pol, random.Random(0))
    assert f1["opener_strong_check"] and f0["opener_strong_check"]


def test_evaluate_mix_policy_stratifies_by_public_d():
    deals = [
        _deal(d=1, bucket="two_pair", o_strong=True, o_pair=None, cls="two_pair"),
        _deal(d=3, bucket="one_pair", o_strong=False, o_pair=14, cls="pair_A"),
    ]
    pol = MixPolicy(m2=M2Policy(None, 14, None), check_mix=CheckMix())
    d1 = evaluate_mix_policy(deals, pol, seed=1, subset="d:1")
    d3 = evaluate_mix_policy(deals, pol, seed=1, subset="d:3")
    assert d1.n == 1.0
    assert d3.n == 1.0


def test_draw_policy_defaults():
    assert M2_DRAW.quads_d == 0
    assert B_QUADS_D1.quads_d == 1
    assert B_QUADS_D1.n_draw_for("four_of_a_kind") == 1
    assert B_QUADS_D1.n_draw_for("straight") == 0
    assert B_QUADS_D1.n_draw_for("pair_K") == 3
    # Unified public d=1: two pair, trips, and quads all draw one.
    assert B_TP_TRIPS_QUADS_D1.two_pair_d == 1
    assert B_TP_TRIPS_QUADS_D1.trips_d == 1
    assert B_TP_TRIPS_QUADS_D1.quads_d == 1
    assert B_TP_TRIPS_QUADS_D1.pair_d == 3
    assert B_TP_TRIPS_QUADS_D1.n_draw_for("trips") == 1
    assert B_TP_TRIPS_QUADS_D1.n_draw_for("two_pair") == 1
    assert B_TP_TRIPS_QUADS_D1.n_draw_for("four_of_a_kind") == 1
    assert B_TP_TRIPS_QUADS_D1.n_draw_for("pair_A") == 3
    # Full Stage B factorial grid
    assert len(STAGE_B_DRAW_POLICIES) == 12
    dims = {(p.two_pair_d, p.trips_d, p.quads_d) for p in STAGE_B_DRAW_POLICIES}
    assert dims == {(tp, tr, q) for tp in (0, 1) for tr in (0, 1, 2) for q in (0, 1)}
    assert stage_b_draw_policy(1, 1, 1).name == "tp1_tr1_q1"


def test_c_primary_and_unified_forks_lock_pairs_d3():
    """Post-B locks for Stage C: two pair d=1, quads d=1, pairs d=3; trips fork."""
    primary = stage_b_draw_policy(1, 2, 1)
    unified = stage_b_draw_policy(1, 1, 1)
    assert primary.name == "tp1_tr2_q1"
    assert unified.name == "tp1_tr1_q1"
    for pol in (primary, unified):
        assert pol.pair_d == 3
        assert pol.two_pair_d == 1
        assert pol.quads_d == 1
        for cls in ("pair_J", "pair_Q", "pair_K", "pair_A"):
            assert pol.n_draw_for(cls) == 3
        assert pol.n_draw_for("two_pair") == 1
        assert pol.n_draw_for("two_pair_aces_up") == 1
        assert pol.n_draw_for("four_of_a_kind") == 1
        for cls in ("straight", "flush", "full_house", "straight_flush", "five_aces"):
            assert pol.n_draw_for(cls) == 0
    assert primary.n_draw_for("trips") == 2
    assert primary.n_draw_for("trips_A") == 2
    assert unified.n_draw_for("trips") == 1
    assert unified.n_draw_for("trips_K") == 1
    # Stale C default alias still stands two pair — not either live fork.
    assert B_QUADS_D1.two_pair_d == 0
    assert B_QUADS_D1.two_pair_d != primary.two_pair_d
    assert B_TP_D1_QUADS_D1.two_pair_d == 1
    assert B_TP_D1_QUADS_D1.trips_d == 2
    assert B_TP_TRIPS_QUADS_D1.trips_d == 1


@pytest.mark.xfail(
    strict=True,
    reason=(
        "run_stage_c still defaults to B_QUADS_D1 (two pair stand). "
        "Stage C should default to C-primary tp1_tr2_q1 and also run C-unified."
    ),
)
def test_run_stage_c_default_is_not_stale_two_pair_stand():
    src = inspect.getsource(run_stage_c)
    assert "B_QUADS_D1" not in src
    assert "stage_b_draw_policy(1, 2, 1)" in src or "tp1_tr2_q1" in src


@pytest.mark.xfail(
    strict=True,
    reason=(
        "run_ladder still generates Stage C under B_QUADS_D1. "
        "Need both C-primary (tp1_tr2_q1) and C-unified (tp1_tr1_q1)."
    ),
)
def test_run_ladder_should_run_both_c_forks():
    src = inspect.getsource(run_ladder)
    assert "B_QUADS_D1" not in src
    assert "tp1_tr2_q1" in src or "stage_b_draw_policy(1, 2, 1)" in src
    assert "tp1_tr1_q1" in src or "stage_b_draw_policy(1, 1, 1)" in src


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

    # Stage B: full 12-cell grid under AA stab
    b_comps = data["stage_b"]["comparisons_vs_m2"]
    aa = [c for c in b_comps if "stab=AA|" in c["bet_policy"]]
    assert len(aa) == 12
    assert findings["stage_b_grid_n"] == 12
    for c in aa:
        assert "quads_d" in c and "trips_d" in c and "two_pair_d" in c
        assert "d1_rate" in c and "d2_rate" in c
    dims = {(c["two_pair_d"], c["trips_d"], c["quads_d"]) for c in aa}
    assert dims == {(tp, tr, q) for tp in (0, 1) for tr in (0, 1, 2) for q in (0, 1)}

    unified = next(c for c in aa if c["draw_policy"] == "tp1_tr1_q1")
    tp_d1 = next(c for c in aa if c["draw_policy"] == "tp1_tr2_q1")
    trips_stand = next(c for c in aa if c["draw_policy"] == "tp0_tr0_q1")
    baseline = next(c for c in aa if c["draw_policy"] == "tp0_tr2_q0")
    assert baseline["delta_vs_m2"] == 0.0
    assert trips_stand["delta_vs_m2"] < unified["delta_vs_m2"] < tp_d1["delta_vs_m2"]
    assert findings["tp_trips_quads_d1_delta_ev_vs_m2_aa_stab"] == unified["delta_vs_m2"]

    assert "recommendations" in data and len(data["recommendations"]) >= 5
    quads_rec = next(r for r in data["recommendations"] if r["class"] == "four_of_a_kind")
    assert "d=1" in quads_rec["draw_action"]
    trips_rec = next(r for r in data["recommendations"] if r["class"] == "trips")
    assert "d=2" in trips_rec["draw_action"] and "d=1" in trips_rec["draw_action"]
    tp_rec = next(r for r in data["recommendations"] if r["class"] == "two_pair")
    assert "d=1" in tp_rec["draw_action"]
    pair_rec = next(r for r in data["recommendations"] if r["class"].startswith("pair"))
    assert "d=3" in pair_rec["draw_action"]
    other_rec = next(r for r in data["recommendations"] if r["class"] == "other straight+")
    assert "stand" in other_rec["draw_action"]

    # Stage A: pair d=3 wins more than d=2; pair d=1 cannot make boat+.
    boats = data["stage_a"]["highlights"]["pair_A_draw_mix_boat"]
    wins = data["stage_a"]["highlights"]["pair_A_draw_mix_win"]
    assert boats["d1"] == 0.0
    assert boats["d3"] > boats["d2"] > 0.0
    assert wins["d3"] > wins["d2"]
    assert findings["trips_d2_boat_plus"] > findings["trips_d1_boat_plus"]

    # Stage C structure (magnitudes are stale until C is re-run under two_pair d=1)
    c_meta = data["stage_c"]["meta"]
    assert c_meta["draw"]["pair_d"] == 3
    assert set(c_meta["draw"]) >= {"pair_d", "two_pair_d", "trips_d", "quads_d"}
    aa_c = next(s for s in data["stage_c"]["summaries"] if "stab=AA|" in s["stab"])
    assert "best_check_mix" in aa_c
    assert aa_c["baseline_stab_delta"] is not None
    key_rows = data["stage_c"]["key_rows"]
    assert key_rows
    for row in key_rows:
        assert "drawer_face_stab_delta" in row
        assert "strong_check_rate" in row
    stabs = {s["stab"] for s in data["stage_c"]["summaries"]}
    assert any("stab=AA|" in s and "raise=never" in s for s in stabs)
    assert any("AA+KK" in s for s in stabs)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Checked-in Stage C fixture used two_pair stand (draw_policy=quads_d1). "
        "Re-run C-primary tp1_tr2_q1 and C-unified tp1_tr1_q1; do not trust old "
        "check-mix magnitudes."
    ),
)
def test_stage_c_fixture_uses_post_b_two_pair_d1():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    draw = data["stage_c"]["meta"]["draw"]
    assert draw["two_pair_d"] == 1
    assert draw["quads_d"] == 1
    assert draw["pair_d"] == 3
    assert draw["trips_d"] in (1, 2)
    assert data["stage_c"]["meta"]["draw_policy"] in ("tp1_tr2_q1", "tp1_tr1_q1")
