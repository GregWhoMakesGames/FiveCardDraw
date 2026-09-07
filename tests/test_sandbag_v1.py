"""Sandbag-set v1 predicates, planning mix, and fixture pins."""

from __future__ import annotations

import json
from math import comb
from pathlib import Path

from fivecarddraw.cards import parse_hand
from fivecarddraw.validation.cascade_odds import TOTAL_HANDS
from fivecarddraw.validation.sandbag_v1 import (
    ACES_SANDBAG_SEATS,
    FOLD_JJ_TO_RAISE_EV,
    P_ANY_2TO1_FOLDED_TO_BN_MC,
    PAIR_J_D3_EV_BN,
    PASS_EV,
    SEAT_BN,
    SEAT_CO,
    SEAT_HJ,
    SEAT_LJ,
    STEAL_EV,
    classify_cards,
    deal_mc_p_raise_given_passed_bn_pair_j,
    ev_jj_no_sandbag_open,
    ev_jj_open_100pct_sandbag,
    independent_p_raise_unconditional,
    is_sandbag_set,
    is_voluntary_opener,
    load_sandbag_v1,
    mix_findings,
    not_open_legal_count,
    sandbag_set_combo_count,
    voluntary_combo_count,
)
from fivecarddraw.validation.showdown_matrix import classify_opener, load_showdown_matrix


FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "validation"
    / "sandbag_v1.json"
)


def test_sandbag_set_hj_co_aces_not_lj():
    aa = classify_opener(parse_hand("As Ad 9c 8h 2d"))
    jj = classify_opener(parse_hand("Js Jd 9c 8h 2d"))
    tp = classify_opener(parse_hand("Ks Kd 9c 9h 2d"))
    junk = classify_opener(parse_hand("Ts Td 9c 8h 2d"))
    assert aa == "pair_A"
    assert jj == "pair_J"
    assert tp == "two_pair"
    assert junk is None

    assert ACES_SANDBAG_SEATS == frozenset({SEAT_HJ, SEAT_CO})
    assert SEAT_LJ not in ACES_SANDBAG_SEATS

    # LJ still opens aces; HJ/CO sandbag them.
    assert is_voluntary_opener(aa, SEAT_LJ)
    assert not is_sandbag_set(aa, SEAT_LJ)
    assert is_sandbag_set(aa, SEAT_HJ)
    assert is_sandbag_set(aa, SEAT_CO)
    assert not is_voluntary_opener(aa, SEAT_HJ)

    # Two pair+: sandbag every seat 1–7; always raise a BN open (not a voluntary open).
    for seat in range(1, 8):
        assert is_sandbag_set(tp, seat)
        assert not is_voluntary_opener(tp, seat)

    # JJ is a voluntary opener everywhere in 1–7 (not in the sandbag-set).
    for seat in range(1, 8):
        assert is_voluntary_opener(jj, seat)
        assert not is_sandbag_set(jj, seat)

    # Non-openers and BN never count as sandbag-set / voluntary for this frame.
    assert not is_sandbag_set(junk, SEAT_HJ)
    assert not is_voluntary_opener(junk, SEAT_HJ)
    assert not is_sandbag_set(tp, SEAT_BN)
    assert not is_voluntary_opener(aa, SEAT_BN)


def test_classify_cards_accepts_ids():
    cards = parse_hand("As Ad 9c 8h 2d")
    ids = [c.card_id for c in cards]
    assert classify_cards(cards) == "pair_A"
    assert classify_cards(ids) == "pair_A"


def test_inventory_matches_showdown_matrix():
    sm = load_showdown_matrix()["opener_combo_counts"]
    two_pair_plus = sandbag_set_combo_count(SEAT_LJ)
    hj = sandbag_set_combo_count(SEAT_HJ)
    assert two_pair_plus == sum(
        sm[c]
        for c in sm
        if c
        not in {"pair_J", "pair_Q", "pair_K", "pair_A"}
    )
    assert hj == two_pair_plus + sm["pair_A"]
    assert voluntary_combo_count(SEAT_LJ) == sm["pair_J"] + sm["pair_Q"] + sm["pair_K"] + sm["pair_A"]
    assert voluntary_combo_count(SEAT_CO) == sm["pair_J"] + sm["pair_Q"] + sm["pair_K"]
    assert not_open_legal_count() == TOTAL_HANDS - sum(sm.values())
    assert TOTAL_HANDS == comb(53, 5)


def test_independent_unconditional_p_raise_pinned():
    rates = independent_p_raise_unconditional()
    # Closed form from showdown_matrix combo counts: ~0.5566
    assert 0.55 < rates["p_raise"] < 0.57
    assert abs(rates["p_raise"] + rates["p_no_raise"] - 1.0) < 1e-15
    # HJ/CO P(neither | passed) is lower than UTG–LJ (they also bury aces).
    assert rates["p_neither_given_passed_seat_6"] < rates["p_neither_given_passed_seat_1"]
    assert rates["p_neither_given_passed_seat_6"] == rates["p_neither_given_passed_seat_7"]
    assert rates["p_neither_given_passed_seat_1"] == rates["p_neither_given_passed_seat_5"]


def test_reused_no_raise_leaf_is_section_34_plus_steal():
    ev = ev_jj_no_sandbag_open()
    expected = STEAL_EV + P_ANY_2TO1_FOLDED_TO_BN_MC * (PAIR_J_D3_EV_BN - 4.0)
    assert abs(ev - expected) < 1e-12
    assert abs(ev - 1.9362095) < 1e-9
    # Even p_call=1 stays +EV on the no-sandbag leaf (EV_bn d=3 > $2).
    assert ev_jj_no_sandbag_open(p_call=1.0) > PASS_EV


def test_mix_sign_formula():
    leaf = ev_jj_no_sandbag_open()
    # p=0 recovers the reused leaf; p=1 is fold JJ.
    assert abs(ev_jj_open_100pct_sandbag(0.0) - leaf) < 1e-12
    assert abs(ev_jj_open_100pct_sandbag(1.0) - FOLD_JJ_TO_RAISE_EV) < 1e-12
    mix = mix_findings(0.5)
    assert abs(mix["ev_open_jj"] - (0.5 * leaf + 0.5 * FOLD_JJ_TO_RAISE_EV)) < 1e-12
    assert mix["opening_jj_is_negative_ev"] is True  # 0.5 is above the ~0.49 break-even


def test_small_deal_mc_runs_and_is_in_band():
    """Smoke: 8-way deals with BN pair_J and no voluntary in 1–7 produce a raise rate."""
    mc = deal_mc_p_raise_given_passed_bn_pair_j(n=400, seed=20260907)
    assert mc.n_conditioned == 400
    assert mc.n_bn_pair_j >= 400
    assert 0.35 < mc.p_raise < 0.75
    assert mc.sandbag_seats_hist["0"] == mc.n_conditioned - mc.n_raise
    assert sum(mc.sandbag_seats_hist.values()) == 400


def test_fixture_pins_product_answer():
    assert FIXTURE.exists(), "run python -m fivecarddraw.validation.sandbag_v1 --write-fixture"
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    live = load_sandbag_v1()
    assert data == live
    meta = data["meta"]
    assert meta["sandbag_set"]["aces_sandbag_seats"] == [6, 7]
    assert meta["sandbag_set"]["lj_opens_aces"] is True
    assert meta["no_raise_leaf"]["source"] == "button_open_no_sandbagging JJ open"
    assert meta["no_raise_leaf"]["ev_bn_pair_j_d3"] == PAIR_J_D3_EV_BN
    assert meta["mc"]["n"] == 40_000
    assert meta["mc"]["seed"] == 20260907

    f = data["findings"]
    mc = data["deal_mc"]
    assert mc["n"] == 40_000
    assert mc["seed"] == 20260907
    assert mc["n_conditioned"] == 40_000
    assert abs(f["p_raise"] - mc["p_raise"]) < 1e-15
    assert abs(f["ev_jj_no_sandbag_open"] - ev_jj_no_sandbag_open()) < 1e-12
    # Product pin: opening JJ is −EV; p_raise sits above the ~0.49 break-even.
    assert f["opening_jj_is_negative_ev"] is True
    assert f["ev_open_jj"] < PASS_EV
    assert 0.50 < f["p_raise"] < 0.62
    assert f["piece_raise"] < 0.0
    assert f["piece_no_raise"] > 0.0
    # Mix reconstructs.
    recon = (1.0 - f["p_raise"]) * f["ev_jj_no_sandbag_open"] + f["p_raise"] * FOLD_JJ_TO_RAISE_EV
    assert abs(f["ev_open_jj"] - recon) < 1e-12
    assert abs(f["p_raise"] - 0.573025) < 1e-12
    assert abs(f["ev_open_jj"] - (-0.31933694873750007)) < 1e-12
    assert f["sensitivity_p_call_independent_6pct"]["p_call_reused"] == 0.06

    nb = json.loads(
        (Path(__file__).resolve().parent / "fixtures" / "validation" / "postdraw_nonbluff_ev_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert nb["findings"]["pair_J_ev_by_d"]["3"] == PAIR_J_D3_EV_BN
