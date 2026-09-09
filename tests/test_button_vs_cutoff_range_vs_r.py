"""BN-vs-CO range vs trap-rate decomposition (item 1; locked leaves)."""

from __future__ import annotations

import json
from pathlib import Path

from fivecarddraw.cards import parse_hand
from fivecarddraw.hand_rank import HandCategory, evaluate_hand
from fivecarddraw.validation.button_vs_cutoff_range_vs_r import (
    CALL_INVEST,
    CROSS_RANGES,
    FOLD_EV,
    FOLD_TO_THREEBET_EV,
    FRAME,
    PRIMARY_TRAP_LEAF,
    PROXY_TRAP_LEAF,
    RAISE_INVEST,
    RAISE_POT,
    TRAP_RATES_PCT,
    build_range_vs_r_payload,
    chart_kappa,
    extract_hu_cell,
    load_range_fixture,
    load_summary_fixture,
    p_trap_at_rate_pct,
)
from fivecarddraw.validation.button_vs_cutoff_tight import (
    FOLD_EV as TIGHT_FOLD_EV,
    recommend_action,
)
from fivecarddraw.validation.cutoff_open_sandbag import load_fixture as load_co_sandbag
from fivecarddraw.validation.sandbag_v1 import FOLD_JJ_TO_RAISE_EV, SANDBAG_WORLD_CO_VS_SEATS_1_6
from fivecarddraw.validation.showdown_matrix import classify_opener


FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "validation"
    / "button_vs_cutoff_range_vs_r.json"
)

POLAR_ALL_LEGAL = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "validation"
    / "button_vs_cutoff_all_legal.json"
)
POLAR_TIGHT = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "validation"
    / "button_vs_cutoff_tight.json"
)


def _cell(payload: dict, bn: str, rng: str, r: int, kind: str = PRIMARY_TRAP_LEAF) -> dict:
    for row in payload["cross"]:
        if (
            row["bn_class"] == bn
            and row["co_range"] == rng
            and row["trap_r_pct"] == r
            and row["trap_leaf_kind"] == kind
        ):
            return row
    raise KeyError((bn, rng, r, kind))


def test_accounting_and_world_pins():
    assert FOLD_EV == TIGHT_FOLD_EV == 0.0
    assert CALL_INVEST == 2.0
    assert RAISE_INVEST == 4.0
    assert RAISE_POT == 10.0
    assert FOLD_JJ_TO_RAISE_EV == -2.0
    assert FOLD_TO_THREEBET_EV == -4.0
    assert FRAME == "button_vs_cutoff_range_vs_r"
    assert CROSS_RANGES == ("all_legal", "r79", "r86", "r87", "tight")
    assert TRAP_RATES_PCT == (0, 79, 86, 87, 96, 100)


def test_bug_is_ace_kicker_not_trips():
    kk_joker = parse_hand("Ks Kh Bu 9c 2d")
    assert classify_opener(kk_joker) == "pair_K"
    assert evaluate_hand(kk_joker).category == HandCategory.ONE_PAIR
    trips_k = parse_hand("Ks Kh Kd 9c 2d")
    assert classify_opener(trips_k) == "trips_K"


def test_kappa_reuses_locked_jj_pin():
    sandbag = load_co_sandbag()
    info = chart_kappa(sandbag)
    assert info["world"] == SANDBAG_WORLD_CO_VS_SEATS_1_6
    p_ind_1 = float(sandbag["independent_p_raise_at_r1"])
    jj = next(r for r in sandbag["by_class"] if r["co_class"] == "pair_J")
    assert abs(info["p_ind_1"] - p_ind_1) < 1e-12
    assert abs(info["p_mc_1_jj"] - float(jj["p_raise"])) < 1e-12
    assert abs(info["kappa"] - float(jj["p_raise"]) / p_ind_1) < 1e-12
    z = p_trap_at_rate_pct(0, kappa=info["kappa"], world=info["world"])
    assert z["p_trap"] == 0.0
    one = p_trap_at_rate_pct(100, kappa=info["kappa"], world=info["world"])
    assert abs(one["p_trap"] - float(jj["p_raise"])) < 5e-4


def test_signed_hu_leaves_not_restarted():
    """Polar + interior HU actions stay the published lookup inputs."""
    all_legal = load_range_fixture("all_legal")
    r79 = load_range_fixture("r79")
    r86 = load_range_fixture("r86")
    r87 = load_range_fixture("r87")
    tight = load_range_fixture("tight")
    assert extract_hu_cell(all_legal, "pair_A")["hu_action"] == "raise"
    assert extract_hu_cell(r79, "pair_A")["hu_action"] == "fold"
    assert extract_hu_cell(r86, "two_pair")["hu_action"] == "raise"
    assert extract_hu_cell(r87, "two_pair")["hu_action"] == "call"
    assert extract_hu_cell(tight, "pair_A")["hu_action"] == "fold"
    assert extract_hu_cell(tight, "two_pair")["hu_action"] == "call"
    live_all = json.loads(POLAR_ALL_LEGAL.read_text(encoding="utf-8"))
    live_tight = json.loads(POLAR_TIGHT.read_text(encoding="utf-8"))
    assert live_all["answers"]["pair_A_action"] == "raise"
    assert live_all["answers"]["two_pair_action"] == "raise"
    assert live_tight["answers"]["aa_action"] == "fold"
    assert live_tight["answers"]["two_pair_action"] == "call"


def test_fixture_rebuilds_from_locked_leaves():
    live = build_range_vs_r_payload()
    stored = load_summary_fixture()
    assert live["answers"] == stored["answers"]
    assert live["p_trap_by_r"] == stored["p_trap_by_r"]
    assert live["hu_by_range"] == stored["hu_by_range"]
    assert live["cross"] == stored["cross"]
    assert stored["meta"]["frame"] == FRAME
    assert stored["meta"]["co_never_sandbags"] is True
    assert stored["answers"]["lookup_row_added"] is False


def test_aa_switch_is_range_not_trap():
    payload = load_summary_fixture()
    a = payload["answers"]
    assert a["aa_signed_from"] == "raise"
    assert a["aa_signed_to"] == "fold"
    assert a["aa_range_only_r79_at_trap0"] == "fold"
    assert a["aa_trap_only_all_legal_at_r79"] == "raise"
    assert a["aa_switch_is_range"] is True
    assert a["aa_switch_is_trap"] is False
    # Chart-range at the wrong r: r79 CO still folds AA with no trap.
    assert _cell(payload, "pair_A", "r79", 0)["action"] == "fold"
    # Non-chart range at a known r: all-legal CO at 79% still raises AA.
    loose = _cell(payload, "pair_A", "all_legal", 79)
    assert loose["action"] == "raise"
    assert loose["ev_call_mixed"] < 0.0
    assert loose["ev_raise_hu"] > 0.0
    assert loose["p_bn_wins_final"] > 0.5
    # Tighter than the chart under 79% is also range (tight polar at trap 0).
    assert a["aa_tight_co_at_r0"] == "fold"


def test_two_pair_switch_is_range_not_trap():
    payload = load_summary_fixture()
    a = payload["answers"]
    assert a["two_pair_signed_from"] == "raise"
    assert a["two_pair_signed_to"] == "call"
    assert a["two_pair_range_only_r87_at_trap0"] == "call"
    assert a["two_pair_trap_only_r86_at_r87"] == "raise"
    assert a["two_pair_switch_is_range"] is True
    assert a["two_pair_switch_is_trap"] is False
    assert _cell(payload, "two_pair", "r87", 0)["action"] == "call"
    trap_only = _cell(payload, "two_pair", "r86", 87)
    assert trap_only["action"] == "raise"
    assert trap_only["p_bn_wins_final"] > 0.5
    assert a["two_pair_loose_co_all_legal_at_r87"] == "raise"
    assert a["two_pair_tight_co_at_r0"] == "call"


def test_fold_bound_on_matching_two_pair_is_not_a_lookup_row():
    """Even-folding the 1–6 raise eats the thin +EV call; that is not the line.

    sandbag_v1 does not assume two pair folds a trap raise. tight_proxy keeps
    the signed call. Do not add a lookup row.
    """
    payload = load_summary_fixture()
    a = payload["answers"]
    bound = _cell(payload, "two_pair", "r87", 87, PRIMARY_TRAP_LEAF)
    proxy = _cell(payload, "two_pair", "r87", 87, PROXY_TRAP_LEAF)
    assert bound["action"] == "fold"
    assert bound["ev_call_mixed"] < 0.0
    assert proxy["action"] == "call"
    assert proxy["ev_call_mixed"] > 0.0
    assert a["two_pair_coupled_r87_range_at_r87_fold_bound"] == "fold"
    assert a["two_pair_coupled_r87_range_at_r87_tight_proxy"] == "call"
    assert a["lookup_row_added"] is False


def test_value_raise_rule_unchanged():
    """Same tight-polar helper: dog with +EV call is a call, not a raise."""
    call = recommend_action(ev_call=0.30, ev_raise=0.10, p_bn_win=0.40)
    assert call["action"] == "call"
    raise_ = recommend_action(ev_call=4.0, ev_raise=3.0, p_bn_win=0.70)
    assert raise_["action"] == "raise"
    fold = recommend_action(ev_call=-0.40, ev_raise=-1.10, p_bn_win=0.32)
    assert fold["action"] == "fold"


def test_fold_threebet_is_sensitivity_not_product():
    payload = load_summary_fixture()
    aa_trap = _cell(payload, "pair_A", "all_legal", 79)
    assert aa_trap["action"] == "raise"
    assert aa_trap["fold_threebet_action"] == "fold"
    assert aa_trap["fold_threebet"]["raise_line"] == "fold_to_threebet_out_of_scope"
    tp_trap = _cell(payload, "two_pair", "r86", 87)
    assert tp_trap["action"] == "raise"
    assert tp_trap["fold_threebet_action"] == "fold"
