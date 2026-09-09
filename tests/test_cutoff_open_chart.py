"""CO open chart: slowplay rate × blockers (reuse locked 0%/100% pins)."""

from __future__ import annotations

import json
from pathlib import Path

from fivecarddraw.validation.cutoff_open_chart import (
    POLICY_ACE_OR_JOKER,
    POLICY_JOKER_ONLY,
    POLICY_OPEN_ALWAYS,
    POLICY_PASS,
    build_open_chart,
    ev_at_rate,
    flavor_row,
    format_playable_table,
    opening_policy_at_rate,
    opening_policy_playable_pct,
    playable_pct,
)
from fivecarddraw.validation.cutoff_open_sandbag import load_fixture
from fivecarddraw.validation.sandbag_v1 import DEFAULT_MC_SEED, PASS_EV


FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "validation"
    / "cutoff_open_sandbag_v1.json"
)


def _chart() -> dict:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert "open_chart" in data, "run python -m fivecarddraw.validation.cutoff_open_sandbag --write-chart"
    return data["open_chart"]


def test_chart_rebuilds_from_locked_pins():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    live = load_fixture()
    assert data == live
    chart = data["open_chart"]
    assert build_open_chart(data) == chart
    assert chart["co_never_sandbags"] is True
    assert chart["mc_pins"]["class_avg_n"] == 40_000
    assert chart["mc_pins"]["flavor_n"] == 10_000
    assert chart["mc_pins"]["seed"] == DEFAULT_MC_SEED
    assert chart["world"] == "co_vs_seats_1_6"


def test_endpoint_leaves_and_r_star_match_signed_pins():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    chart = data["open_chart"]
    a = chart["answers"]
    # Class-average r* are the locked 40k Bayes pins (do not rebuild).
    by = {r["co_class"]: r for r in data["by_class"]}
    assert abs(a["jj_open_always_below"] - by["pair_J"]["r_calibrated"]) < 1e-12
    assert abs(a["qq_open_always_below"] - by["pair_Q"]["r_calibrated"]) < 1e-12
    assert abs(a["kk_open_always_below"] - by["pair_K"]["r_calibrated"]) < 1e-12
    jj_joker = data["blockers"]["pair_j_bug"]["reweighted_leaf_mix"]
    qq_joker = data["blockers"]["pair_q_bug"]["reweighted_leaf_mix"]
    kk_joker = data["blockers"]["pair_k_bug"]["reweighted_leaf_mix"]
    jj_ace = data["blockers"]["pair_j_ace_kicker"]["reweighted_leaf_mix"]
    qq_ace = data["blockers"]["pair_q_ace_kicker"]["reweighted_leaf_mix"]
    kk_ace = data["blockers"]["pair_k_ace_kicker"]["reweighted_leaf_mix"]
    assert abs(a["jj_joker_only_below"] - jj_joker["r_calibrated"]) < 1e-12
    assert abs(a["qq_joker_only_below"] - qq_joker["r_calibrated"]) < 1e-12
    assert abs(a["kk_joker_only_below"] - kk_joker["r_calibrated"]) < 1e-12
    assert abs(a["jj_ace_or_joker_below"] - jj_ace["r_calibrated"]) < 1e-12
    assert abs(a["qq_ace_or_joker_below"] - qq_ace["r_calibrated"]) < 1e-12
    assert abs(a["kk_ace_or_joker_below"] - kk_ace["r_calibrated"]) < 1e-12
    # Nested: joker > ace > class average for every face pair.
    for cls in ("pair_J", "pair_Q", "pair_K"):
        assert chart["by_class"][cls]["nested_r_star"] is True
        flavors = chart["by_class"][cls]["flavors"]
        assert (
            flavors["class_avg"]["r_star"]
            <= flavors["ace"]["r_star"]
            <= flavors["joker"]["r_star"]
        )


def test_playable_opening_rules():
    chart = _chart()
    a = chart["answers"]
    assert a["playable_jj_pcts"] == [79, 86, 93]
    assert a["playable_qq_pcts"] == [84, 90, 100]
    assert a["playable_kk_pcts"] == [87, 96, 100]
    assert a["jj_policy_at_100pct"] == POLICY_PASS
    assert a["qq_policy_at_100pct"] == POLICY_JOKER_ONLY
    assert a["kk_policy_at_100pct"] == POLICY_JOKER_ONLY
    for cls in ("pair_J", "pair_Q", "pair_K"):
        assert chart["by_class"][cls]["policy_at_0pct"] == POLICY_OPEN_ALWAYS
    jj_rules = chart["by_class"]["pair_J"]["playable_rules"]
    qq_rules = chart["by_class"]["pair_Q"]["playable_rules"]
    kk_rules = chart["by_class"]["pair_K"]["playable_rules"]
    assert "don't open JJ unless you have an ace" in jj_rules[0]
    assert "79%" in jj_rules[0]
    assert "don't open JJ at all unless you have a joker" in jj_rules[1]
    assert "86%" in jj_rules[1]
    assert "93%" in jj_rules[2]
    assert "pass JJ even with the joker" in jj_rules[2]
    assert "don't open QQ unless you have an ace" in qq_rules[0]
    assert "84%" in qq_rules[0]
    assert "90%" in qq_rules[1]
    assert "coin-flip" in qq_rules[2]
    assert "don't open KK unless you have an ace" in kk_rules[0]
    assert "87%" in kk_rules[0]
    assert "96%" in kk_rules[1]
    assert "KK+joker stays +EV" in kk_rules[2]


def test_playable_lookup_table():
    chart = _chart()
    rows = chart["lookup_playable"]
    assert rows[0]["r_lo_pct"] == 0
    assert rows[0]["r_hi_pct"] == 79
    assert rows[0]["JJ"] == POLICY_OPEN_ALWAYS
    assert rows[0]["QQ"] == POLICY_OPEN_ALWAYS
    assert rows[0]["KK"] == POLICY_OPEN_ALWAYS
    # 79%: JJ needs ace; QQ/KK still open.
    r79 = next(r for r in rows if r["r_lo_pct"] == 79)
    assert r79["JJ"] == POLICY_ACE_OR_JOKER
    assert r79["QQ"] == POLICY_OPEN_ALWAYS
    assert r79["KK"] == POLICY_OPEN_ALWAYS
    # 90%: JJ joker, QQ joker, KK ace.
    r90 = next(r for r in rows if r["r_lo_pct"] == 90)
    assert r90["JJ"] == POLICY_JOKER_ONLY
    assert r90["QQ"] == POLICY_JOKER_ONLY
    assert r90["KK"] == POLICY_ACE_OR_JOKER
    last = rows[-1]
    assert last["r_lo_pct"] == 96
    assert last["JJ"] == POLICY_PASS
    assert last["QQ"] == POLICY_JOKER_ONLY
    assert last["KK"] == POLICY_JOKER_ONLY
    table = format_playable_table(chart)
    assert "| r < 79% | open | open | open |" in table
    assert "| r ≥ 96% | pass | joker only | joker only |" in table
    assert "| 93–96% | pass | joker only | ace or joker |" in table


def test_opening_policy_helpers():
    assert (
        opening_policy_at_rate(0.0, r_class=0.79, r_ace=0.86, r_joker=0.93)
        == POLICY_OPEN_ALWAYS
    )
    assert (
        opening_policy_at_rate(0.79, r_class=0.79, r_ace=0.86, r_joker=0.93)
        == POLICY_ACE_OR_JOKER
    )
    assert (
        opening_policy_at_rate(1.0, r_class=0.79, r_ace=0.86, r_joker=0.93)
        == POLICY_PASS
    )
    assert (
        opening_policy_at_rate(1.0, r_class=0.87, r_ace=0.96, r_joker=1.04)
        == POLICY_JOKER_ONLY
    )
    assert playable_pct(0.78716) == 79
    assert playable_pct(1.042) == 100
    assert (
        opening_policy_playable_pct(
            79,
            pct_class=79,
            pct_ace=86,
            pct_joker=93,
            joker_through_100=False,
        )
        == POLICY_ACE_OR_JOKER
    )


def test_grid_locates_jj_class_sign_change():
    chart = _chart()
    g = chart["by_class"]["pair_J"]["flavors"]["class_avg"]
    assert abs(g["ev_open_0pct"] - g["leaf"]) < 1e-12
    assert abs(g["ev_open_100pct_calibrated"] - g["ev_open_100pct"]) < 1e-12
    assert g["last_plus_ev_grid_r"] == 0.78
    assert g["first_minus_ev_grid_r"] == 0.79
    assert g["last_plus_ev_grid_r"] < g["r_star"] < g["first_minus_ev_grid_r"]
    by_r = {pt["r"]: pt for pt in g["grid"]}
    assert by_r[0.78]["opening_is_positive_ev"] is True
    assert by_r[0.79]["opening_is_negative_ev"] is True
    # Ace / joker flip later; at 100% class avg is −EV, joker still −EV for JJ.
    assert chart["by_class"]["pair_J"]["flavors"]["joker"]["opening_is_positive_ev_100pct"] is False
    assert chart["by_class"]["pair_Q"]["flavors"]["joker"]["opening_is_positive_ev_100pct"] is True
    assert chart["by_class"]["pair_K"]["flavors"]["joker"]["opening_is_positive_ev_100pct"] is True


def test_calibrated_ev_reuses_leaf_and_p_mc():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    p_ind_1 = float(data["independent_p_raise_at_r1"])
    row = flavor_row(data, "pair_J", "class_avg")
    at0 = ev_at_rate(
        0.0,
        p_mc_1=row["p_raise"],
        p_ind_1=p_ind_1,
        leaf=row["ev_no_raise_leaf"],
        se_p_mc_1=row["se_p_raise"],
    )
    at1 = ev_at_rate(
        1.0,
        p_mc_1=row["p_raise"],
        p_ind_1=p_ind_1,
        leaf=row["ev_no_raise_leaf"],
        se_p_mc_1=row["se_p_raise"],
    )
    assert abs(at0["ev_open"] - 1.43502) < 1e-12
    assert at0["p_raise"] == 0.0
    assert abs(at1["p_raise"] - row["p_raise"]) < 1e-12
    assert abs(at1["ev_open"] - row["ev_open_100pct"]) < 1e-12
    assert at0["ev_open"] > PASS_EV
    assert at1["ev_open"] < PASS_EV


def test_interior_mc_r_half_sits_between_endpoints():
    """Seeded card-removal MC at r=0.5; Bayes interpolation is the chart."""
    from fivecarddraw.validation.cutoff_open_chart import ev_at_rate
    from fivecarddraw.validation.cutoff_open_sandbag import (
        deal_mc_p_raise_co_flavor,
        deal_mc_p_raise_given_passed_co,
    )

    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    p_ind_1 = float(data["independent_p_raise_at_r1"])
    row = flavor_row(data, "pair_J", "class_avg")
    bayes = ev_at_rate(
        0.5,
        p_mc_1=row["p_raise"],
        p_ind_1=p_ind_1,
        leaf=row["ev_no_raise_leaf"],
        se_p_mc_1=row["se_p_raise"],
    )
    mc = deal_mc_p_raise_given_passed_co(
        n=400, seed=DEFAULT_MC_SEED, co_class="pair_J", sandbag_rate=0.5
    )
    assert mc.n_conditioned == 400
    assert mc.sandbag_rate == 0.5
    assert 0.0 < mc.p_raise < row["p_raise"]
    # n=400 SE ≈ 0.025; stay within a loose band of the calibrated curve.
    assert abs(mc.p_raise - bayes["p_raise"]) < 0.12
    bug = deal_mc_p_raise_co_flavor(
        n=400,
        seed=DEFAULT_MC_SEED,
        co_class="pair_J",
        require_bug=True,
        sandbag_rate=0.5,
    )
    assert bug.p_co_has_bug == 1.0
    assert bug.sandbag_rate == 0.5
    assert 0.0 < bug.p_raise < data["blockers"]["pair_j_bug"]["reweighted_leaf_mix"]["p_raise"]


def test_r0_flavor_mc_never_raises():
    from fivecarddraw.validation.cutoff_open_sandbag import deal_mc_p_raise_co_flavor

    mc = deal_mc_p_raise_co_flavor(
        n=200,
        seed=DEFAULT_MC_SEED,
        co_class="pair_K",
        require_bug=True,
        sandbag_rate=0.0,
    )
    assert mc.n_conditioned == 200
    assert mc.p_raise == 0.0
    assert mc.n_raise == 0
    assert mc.sandbag_seats_hist["0"] == 200
