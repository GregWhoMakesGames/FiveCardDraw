"""HJ slowplay mix vs open: CO pin, EV signs, r_tot / p_raise vs BN."""

from __future__ import annotations

import json
from pathlib import Path

from fivecarddraw.validation.hijack_slowplay import (
    BN_BREAK_EVEN_P_RAISE,
    CO_NEVER_SLOWPLAY_PIN,
    FOLD_JJ_TO_RAISE_EV,
    P_J_PLAN,
    P_S_15_PLAN,
    P_S_HJ_PLAN,
    PASS_EV,
    R_TOT_OPEN_EVERYTHING_LINE,
    deal_mc_p_raise_hj_mix,
    equity_vs_range,
    independent_p_raise_rates,
    load_fixture,
    mix_open_hyp_ev,
    mix_slowplay_ev,
    planning_p_raise_rates,
    planning_r_tot,
    raise_checkdown_ev,
    world0_open_leaves,
    _villain_two_pair_plus,
)
from fivecarddraw.validation.sandbag_v1 import (
    SANDBAG_WORLD_SEATS_1_6_ONLY,
    independent_p_raise_unconditional,
    load_seats_1_6_only,
)


FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "validation"
    / "hijack_slowplay.json"
)


def test_co_never_slowplay_pin_quotes_cutoff_lab():
    pin = CO_NEVER_SLOWPLAY_PIN
    assert pin["confirmed_never_slowplay"] is True
    assert pin["q2_co_should_sandbag"] is False
    assert pin["q1_open_every_legal"] is True
    assert pin["frame"] == "cutoff_open_no_sandbagging"
    assert pin["source_branch"] == "cursor/cutoff-open-no-sandbagging-6cf1"
    assert "Seats 1–6 unable" in pin["laboratory"]
    assert abs(pin["q1_jj_ev_open"] - 1.43502) < 1e-12
    assert abs(pin["pair_A_open_minus_best_pass"] - 1.39436) < 1e-12
    assert abs(pin["two_pair_open_minus_best_pass"] - 1.42289) < 1e-12
    assert pin["docs_round_jj_open"] == 1.44
    assert pin["docs_round_open_minus_best_pass_lo"] == 1.39
    assert pin["docs_round_open_minus_best_pass_hi"] == 1.42
    # Gap is a dollar-plus; this is the “never slowplay” pin, not a close mix.
    assert pin["pair_A_open_minus_best_pass"] > 1.3
    assert pin["two_pair_open_minus_best_pass"] > 1.3


def test_planning_p_raise_and_r_tot_match_1_6_writeup():
    all100 = planning_p_raise_rates(1.0, 1.0)
    r0 = planning_p_raise_rates(1.0, 0.0)
    # Independent all-100% ≈ 0.482 (MC in 1–6-only fixture is 0.496).
    assert abs(all100["p_raise"] - 0.4820870625134923) < 1e-12
    exact = independent_p_raise_unconditional(SANDBAG_WORLD_SEATS_1_6_ONLY)
    assert abs(independent_p_raise_rates(1.0, 1.0)["p_raise"] - exact["p_raise"]) < 1e-12
    assert 0.39 < r0["p_raise"] < 0.41
    rt100 = planning_r_tot(1.0, 1.0)
    rt0 = planning_r_tot(1.0, 0.0)
    assert abs(rt100["r_tot"] - 1.0) < 1e-12
    assert abs(rt0["r_tot"] - 0.7592010356944701) < 1e-12
    # 2% drop from 100% toward the 98% BN-open-everything line: r_HJ ≲ 0.92.
    assert abs(rt100["r_hj_for_r_tot_le_0_98"] - 0.9169431643625195) < 1e-12
    assert planning_r_tot(1.0, 0.92)["r_tot"] <= R_TOT_OPEN_EVERYTHING_LINE + 0.001
    assert planning_r_tot(1.0, 1.0)["drops_total_slowplay_by_at_least_2pct"] is False
    assert P_J_PLAN == 0.7760
    assert P_S_15_PLAN == 0.0821
    assert P_S_HJ_PLAN == 0.1302


def test_world0_leaves_and_hyp_mix_formula():
    leaves = world0_open_leaves(p_not_legal=P_J_PLAN, p_2to1=0.00641)
    s = leaves["p_steal"] + leaves["p_vs_2to1"] + leaves["p_vs_legal"]
    assert abs(s - 1.0) < 1e-12
    assert 0.55 < leaves["p_steal"] < 0.59
    assert 0.38 < leaves["p_vs_legal"] < 0.42
    # Fold-to-raise bound is below the no-raise leaf.
    world0 = 1.67
    hyp = mix_open_hyp_ev(0.40, world0, FOLD_JJ_TO_RAISE_EV)
    assert abs(hyp - (0.6 * 1.67 + 0.4 * (-2.0))) < 1e-12
    assert hyp < world0
    slow = mix_slowplay_ev(0.40, raise_checkdown_ev(p_win=0.55))
    assert abs(slow - 0.40 * 1.5) < 1e-12


def test_small_equity_mc_two_pair_is_a_dog_to_two_pair_plus():
    eq = equity_vs_range("two_pair", _villain_two_pair_plus, n=120, seed=20260907)
    assert eq["n"] == 120
    assert 0.10 < eq["p_win"] < 0.45
    trips = equity_vs_range("trips", _villain_two_pair_plus, n=80, seed=20260907)
    assert trips["p_win"] > eq["p_win"]


def test_small_deal_mc_mix_is_below_all_100():
    slow_all = deal_mc_p_raise_hj_mix(
        {c: 1.0 for c in ("pair_A", "two_pair", "two_pair_aces_up", "trips", "straight_plus")},
        n=300,
        seed=20260907,
    )
    open_strong = deal_mc_p_raise_hj_mix(
        {
            "pair_A": 1.0,
            "two_pair": 1.0,
            "two_pair_aces_up": 0.0,
            "trips": 0.0,
            "straight_plus": 0.0,
        },
        n=300,
        seed=20260907,
    )
    assert slow_all["n_conditioned"] == 300
    assert open_strong["p_raise"] <= slow_all["p_raise"] + 0.02
    assert 0.25 < open_strong["p_raise"] < 0.70


def test_fixture_pins_product_answer():
    assert FIXTURE.exists(), (
        "run python -m fivecarddraw.validation.hijack_slowplay --write-fixture"
    )
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    live = load_fixture()
    assert data == live
    a = data["answers"]
    pin = data["meta"]["co_pin"]
    assert pin["confirmed_never_slowplay"] is True
    assert pin["q2_co_should_sandbag"] is False
    assert abs(pin["q1_jj_ev_open"] - 1.43502) < 1e-12

    by = {r["hj_class"]: r for r in data["by_class"]}
    assert set(by) == {
        "pair_A",
        "two_pair",
        "two_pair_aces_up",
        "trips",
        "straight_plus",
    }
    # Hypothesis stack: 1–5 raise. AA / two pair slowplay; aces-up+ open.
    assert by["pair_A"]["action"] == "slowplay"
    assert by["two_pair"]["action"] == "slowplay"
    assert by["two_pair_aces_up"]["action"] == "open"
    assert by["trips"]["action"] == "open"
    assert by["straight_plus"]["action"] == "open"
    assert by["pair_A"]["r_star"] == 1.0
    assert by["two_pair"]["r_star"] == 1.0
    assert by["two_pair_aces_up"]["r_star"] == 0.0
    assert by["trips"]["r_star"] == 0.0
    assert by["straight_plus"]["r_star"] == 0.0
    # World-0 (1–5 unable) overstates EV(open) — that is why AA/two pair slowplay.
    assert by["pair_A"]["ev_open_world0"] > 1.2
    assert by["pair_A"]["ev_open_hyp"] < by["pair_A"]["ev_slowplay"]
    assert by["two_pair"]["ev_open_world0"] > 1.4
    assert by["two_pair"]["ev_open_hyp"] < by["two_pair"]["ev_slowplay"]
    # Mix reconstructs.
    for row in data["by_class"]:
        recon = mix_open_hyp_ev(
            row["p_raise_15"], row["ev_open_world0"], row["ev_vs_raise"]
        )
        assert abs(row["ev_open_hyp"] - recon) < 1e-5
        assert row["ev_open_hyp"] > PASS_EV or row["action"] == "slowplay"

    assert abs(by["pair_A"]["ev_open_hyp"] - 0.305762) < 1e-12
    assert abs(by["pair_A"]["ev_slowplay"] - 0.508501) < 1e-12
    assert abs(by["two_pair"]["ev_open_hyp"] - 0.424788) < 1e-12
    assert abs(by["two_pair"]["ev_slowplay"] - 0.631145) < 1e-12

    assert a["hundred_pct_hj_slowplay_is_optimal"] is False
    assert a["co_never_slowplay_confirmed"] is True
    assert 0.64 < a["r_hj_star_mass_weighted"] < 0.67
    assert abs(a["r_hj_star_mass_weighted"] - 0.6553087384669741) < 1e-12
    # 2% test: r_tot drops from 100% to ~91.7% (need ≤ 98%).
    assert a["drops_total_slowplay_by_at_least_2pct"] is True
    assert a["r_tot"] <= R_TOT_OPEN_EVERYTHING_LINE
    assert abs(a["r_tot"] - 0.9169987012176808) < 1e-12
    assert a["slowplay_rate_drop"] > 0.02
    # BN fold-to-raise break-even ≈ 0.492. Independent 0.455; MC 0.4629.
    assert a["p_raise_independent_at_r_star"] < BN_BREAK_EVEN_P_RAISE
    assert a["p_raise_mc_at_r_star"] < BN_BREAK_EVEN_P_RAISE
    assert abs(a["p_raise_mc_at_r_star"] - 0.4629) < 1e-12
    assert a["supports_bn_open_everything"] is True
    mc = data["deal_mc_r_star"]
    assert mc["n"] == 40_000
    assert mc["seed"] == 20260907
    assert mc["bn_class"] == "pair_J"
    assert abs(mc["p_raise"] - 0.4629) < 1e-12
    # 1–6-only 100% MC pin is unchanged and sits just over the line.
    six = load_seats_1_6_only()
    assert abs(six["q1"]["p_raise"] - 0.495925) < 1e-12
    assert abs(a["p_raise_mc_at_all_100"] - 0.495925) < 1e-12
    assert a["p_raise_mc_at_r_star"] < a["p_raise_mc_at_all_100"] - 0.02
