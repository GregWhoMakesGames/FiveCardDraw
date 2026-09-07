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


def test_seats_1_6_only_co_never_sandbags():
    from fivecarddraw.validation.sandbag_v1 import (
        SANDBAG_WORLD_SEATS_1_6_ONLY,
        aces_sandbag_seats,
        sandbag_seats,
    )

    aa = classify_opener(parse_hand("As Ad 9c 8h 2d"))
    jj = classify_opener(parse_hand("Js Jd 9c 8h 2d"))
    tp = classify_opener(parse_hand("Ks Kd 9c 9h 2d"))
    world = SANDBAG_WORLD_SEATS_1_6_ONLY

    assert aces_sandbag_seats(world) == frozenset({SEAT_HJ})
    assert sandbag_seats(world) == tuple(range(1, 7))
    assert SEAT_CO not in sandbag_seats(world)

    # HJ still buries aces; CO opens them; LJ still opens them.
    assert is_sandbag_set(aa, SEAT_HJ, world)
    assert not is_voluntary_opener(aa, SEAT_HJ, world)
    assert not is_sandbag_set(aa, SEAT_CO, world)
    assert is_voluntary_opener(aa, SEAT_CO, world)
    assert is_voluntary_opener(aa, SEAT_LJ, world)

    # Two pair+: sandbag 1–6; CO opens (so CO monsters never sit folded-to-BN).
    for seat in range(1, 7):
        assert is_sandbag_set(tp, seat, world)
        assert not is_voluntary_opener(tp, seat, world)
    assert not is_sandbag_set(tp, SEAT_CO, world)
    assert is_voluntary_opener(tp, SEAT_CO, world)

    # JJ is voluntary everywhere in 1–7 (not in the sandbag-set).
    for seat in range(1, 8):
        assert is_voluntary_opener(jj, seat, world)
        assert not is_sandbag_set(jj, seat, world)

    # 7-seat default is unchanged: CO still sandbags two pair+ and aces.
    assert is_sandbag_set(tp, SEAT_CO)
    assert is_sandbag_set(aa, SEAT_CO)
    assert not is_voluntary_opener(tp, SEAT_CO)


def test_seats_1_6_inventory_and_independent_p_raise_lower():
    from fivecarddraw.validation.sandbag_v1 import (
        SANDBAG_WORLD_SEATS_1_6_ONLY,
        independent_p_raise_unconditional,
        sandbag_set_combo_count,
        voluntary_combo_count,
    )

    world = SANDBAG_WORLD_SEATS_1_6_ONLY
    sm = load_showdown_matrix()["opener_combo_counts"]
    two_pair_plus = sandbag_set_combo_count(SEAT_LJ, world)
    assert sandbag_set_combo_count(SEAT_CO, world) == 0
    assert voluntary_combo_count(SEAT_CO, world) == sum(sm.values())
    assert sandbag_set_combo_count(SEAT_HJ, world) == two_pair_plus + sm["pair_A"]

    seven = independent_p_raise_unconditional()
    six = independent_p_raise_unconditional(world)
    # One fewer sandbag seat (CO) ⇒ raise rate drops (~0.557 → ~0.482).
    assert 0.47 < six["p_raise"] < 0.50
    assert six["p_raise"] < seven["p_raise"] - 0.05
    assert six["p_neither_given_passed_seat_7"] == 1.0
    assert six["p_neither_given_passed_seat_6"] < six["p_neither_given_passed_seat_1"]
    assert six["p_neither_given_passed_seat_6"] == seven["p_neither_given_passed_seat_6"]
    # Closed form: drop CO from the 7-seat product.
    expected = 1.0 - seven["p_no_raise"] / seven["p_neither_given_passed_seat_7"]
    assert abs(six["p_raise"] - expected) < 1e-15


def test_locked_leaves_match_section_34_and_69pct_call():
    from fivecarddraw.validation.sandbag_v1 import (
        LOCKED_DRAW_EV_BN,
        locked_leaf_ev,
    )

    nb = json.loads(
        (Path(__file__).resolve().parent / "fixtures" / "validation" / "postdraw_nonbluff_ev_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert nb["findings"]["pair_J_ev_by_d"]["3"] == LOCKED_DRAW_EV_BN["pair_J"]
    assert nb["findings"]["two_pair_ev_by_d"]["1"] == LOCKED_DRAW_EV_BN["two_pair"]
    assert nb["findings"]["trips_ev_by_d"]["2"] == LOCKED_DRAW_EV_BN["trips"]
    grid = { (r["opener_class"], r["bn_d"]): r["ev_bn"] for r in nb["bn_grid"] if r["caller_class"] == "all_2to1" }
    assert grid[("pair_Q", 3)] == LOCKED_DRAW_EV_BN["pair_Q"]
    assert grid[("pair_K", 3)] == LOCKED_DRAW_EV_BN["pair_K"]
    assert grid[("pair_A", 3)] == LOCKED_DRAW_EV_BN["pair_A"]

    jj = locked_leaf_ev("pair_J")
    assert abs(jj - 1.9362095) < 1e-9
    assert abs(jj - ev_jj_no_sandbag_open()) < 1e-12


def test_small_deal_mc_seats_1_6_lower_than_seven_seat():
    from fivecarddraw.validation.sandbag_v1 import (
        SANDBAG_WORLD_SEATS_1_6_ONLY,
        deal_mc_p_raise_given_passed,
    )

    seven = deal_mc_p_raise_given_passed_bn_pair_j(n=400, seed=20260907)
    six = deal_mc_p_raise_given_passed(
        n=400, seed=20260907, bn_class="pair_J", world=SANDBAG_WORLD_SEATS_1_6_ONLY
    )
    assert six.n_conditioned == 400
    assert six.world == SANDBAG_WORLD_SEATS_1_6_ONLY
    assert 0.30 < six.p_raise < 0.62
    # Same seed, one fewer sandbag seat ⇒ raise rate should drop.
    assert six.p_raise < seven.p_raise
    assert six.sandbag_seats_hist["0"] == six.n_conditioned - six.n_raise


FIXTURE_1_6 = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "validation"
    / "sandbag_v1_seats_1_6_only.json"
)


def test_seats_1_6_fixture_pins_q1_and_q2():
    from fivecarddraw.validation.sandbag_v1 import (
        FOLD_JJ_TO_RAISE_EV,
        PASS_EV,
        load_seats_1_6_only,
        locked_leaf_ev,
        mix_findings_for_class,
    )

    assert FIXTURE_1_6.exists(), (
        "run python -m fivecarddraw.validation.sandbag_v1 "
        "--world seats_1_6_only --walk --write-fixture"
    )
    data = json.loads(FIXTURE_1_6.read_text(encoding="utf-8"))
    live = load_seats_1_6_only()
    assert data == live
    meta = data["meta"]
    assert meta["world"] == "seats_1_6_only"
    assert meta["sandbag_set"]["aces_sandbag_seats"] == [6]
    assert meta["sandbag_set"]["seat_7_co"] == "never_sandbags_opens_all_legal"
    assert meta["no_raise_leaf"]["ev_open_jj_p_call_mc"] == locked_leaf_ev("pair_J")
    assert meta["mc"]["n"] == 40_000
    assert meta["mc"]["seed"] == 20260907

    q1 = data["q1"]
    mc = data["deal_mc_pair_j"]
    assert mc["n"] == 40_000
    assert mc["seed"] == 20260907
    assert mc["n_conditioned"] == 40_000
    assert mc["bn_class"] == "pair_J"
    assert abs(q1["p_raise"] - mc["p_raise"]) < 1e-15
    assert abs(q1["ev_no_raise_leaf"] - locked_leaf_ev("pair_J")) < 1e-12
    # Lower than Agent A's 0.573; still just above JJ break-even ⇒ −EV.
    assert q1["p_raise"] < q1["agent_a_seven_seat_p_raise"] - 0.05
    assert 0.48 < q1["p_raise"] < 0.52
    assert q1["opening_is_negative_ev"] is True
    assert q1["ev_open"] < PASS_EV
    recon = (1.0 - q1["p_raise"]) * q1["ev_no_raise_leaf"] + q1["p_raise"] * FOLD_JJ_TO_RAISE_EV
    assert abs(q1["ev_open"] - recon) < 1e-12
    assert abs(q1["p_raise"] - 0.495925) < 1e-12
    assert abs(q1["ev_open"] - (-0.015855196287499984)) < 1e-12

    q2 = data["q2"]
    assert q2["n"] == 40_000
    assert q2["seed"] == 20260907
    by_cls = {row["bn_class"]: row for row in q2["rows"]}
    assert set(by_cls) == {"pair_J", "pair_Q", "pair_K", "pair_A"}
    for cls in ("pair_J", "pair_Q", "pair_K"):
        row = by_cls[cls]
        assert row["raise_policy"] == "fold"
        assert row["opening_is_negative_ev"] is True
        assert abs(row["ev_no_raise_leaf"] - locked_leaf_ev(cls)) < 1e-12
        assert abs(row["ev_open"] - mix_findings_for_class(row["p_raise"], cls)["ev_open"]) < 1e-12
        assert row["deal_mc"]["n"] == 40_000
        assert row["deal_mc"]["seed"] == 20260907
    aa = by_cls["pair_A"]
    assert aa["raise_policy"] == "fold_bound"
    assert aa["opening_is_positive_ev"] is True
    assert aa["p_raise"] < by_cls["pair_J"]["p_raise"] - 0.03
    assert abs(aa["p_raise"] - 0.44135) < 1e-12
    assert abs(aa["ev_open"] - 0.18090423794999988) < 1e-12
    assert q2["lowest_plus_ev_class"] == "pair_A"
    assert q2["none_of_jj_kk_plus_ev"] is True
    assert q2["q3_aces_sandbag_pin_should_be_revisited"] is True
    # 7-seat pin must still live in the original fixture.
    seven = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert seven["findings"]["opening_jj_is_negative_ev"] is True
    assert abs(seven["findings"]["p_raise"] - 0.573025) < 1e-12

