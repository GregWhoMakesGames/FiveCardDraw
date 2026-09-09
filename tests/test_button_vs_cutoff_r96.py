"""BN fold/call/raise vs CO chart range at r=96% (tight polar range)."""

from __future__ import annotations

import json
from pathlib import Path

from fivecarddraw.validation.button_vs_cutoff_chart import FRAME_BY_R
from fivecarddraw.validation.button_vs_cutoff_tight import FRAME as TIGHT_FRAME
from fivecarddraw.validation.cutoff_open_chart import (
    POLICY_JOKER_ONLY,
    POLICY_PASS,
)


FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "validation"
    / "button_vs_cutoff_r96.json"
)
TIGHT = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "validation"
    / "button_vs_cutoff_tight.json"
)
R_PCT = 96


def test_fixture_product_answers():
    assert FIXTURE.exists(), "run analyze-button-vs-cutoff-r96 --write-fixture"
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    meta = data["meta"]
    assert meta["frame"] == FRAME_BY_R[R_PCT]
    assert meta["seed"] == 20260909
    assert meta["n_hu"] == 4000
    assert meta["r_pct"] == R_PCT
    assert meta["locked_draws"]["pair_d"] == 3
    assert meta["locked_draws"]["two_pair_d"] == 1
    assert meta["accounting"]["fold"] == 0.0
    policies = meta["co_range"]["pair_policies"]
    assert policies["pair_J"] == POLICY_PASS
    assert policies["pair_Q"] == POLICY_JOKER_ONLY
    assert policies["pair_K"] == POLICY_JOKER_ONLY
    assert meta["co_range"]["matches_tight_polar"] is True

    answers = data["answers"]
    assert answers["jj_action"] == "fold"
    assert answers["qq_action"] == "fold"
    assert answers["kk_action"] == "fold"
    assert answers["aa_action"] == "fold"
    assert answers["aa_closer_to_fold"] is True
    assert answers["aa_ev_call"] < 0.0
    assert answers["aa_vs_fold_se"] > 10.0
    assert answers["two_pair_action"] == "call"
    assert answers["two_pair_thin_call"] is True
    assert answers["two_pair_ev_call"] > 0.0
    assert answers["two_pair_p_win"] < 0.5
    assert answers["aces_up_action"] == "raise"
    assert answers["trips_action"] == "raise"
    assert answers["trips_A_action"] == "raise"
    assert answers["flavor_action_flips"] == []
    assert answers["pair_K_ace_share_on_aa_row"] == 0.0
    assert answers["vs_tight"]["actions_match_tight"] is True
    assert answers["vs_tight"]["action_mismatches"] == []

    by = {r["key"]: r for r in data["by_row"]}
    for key in ("pair_J", "pair_Q", "pair_K", "pair_A"):
        row = by[key]
        assert row["recommend"]["action"] == "fold"
        assert row["ev_call"] < 0.0
        assert row["n"] == 4000.0
        assert row["se_call"] > 0.0
        assert row["co_mix"]["pair_K_ace"] == 0.0
        assert row["co_mix"]["pair_Q_ace"] == 0.0
    jj = by["pair_J"]
    assert jj["co_mix"]["pair_Q_joker"] > 0.0
    assert jj["co_mix"]["pair_K_joker"] > 0.0
    two_pair = by["two_pair"]
    assert two_pair["recommend"]["action"] == "call"
    assert two_pair["p_bn_wins_final"] < 0.5
    trips = by["trips"]
    assert trips["recommend"]["action"] == "raise"
    assert trips["p_bn_wins_final"] > 0.5
    for key in ("pair_J_joker", "pair_Q_joker", "pair_K_joker"):
        assert by[key]["recommend"]["action"] == "fold"


def test_actions_match_tight_polar_fixture():
    """Same constructed range as tight; do not edit the polar file."""
    ours = json.loads(FIXTURE.read_text(encoding="utf-8"))
    tight = json.loads(TIGHT.read_text(encoding="utf-8"))
    assert tight["meta"]["frame"] == TIGHT_FRAME
    assert ours["meta"]["seed"] != tight["meta"]["seed"]
    by = {r["key"]: r["recommend"]["action"] for r in ours["by_row"]}
    tby = {r["key"]: r["recommend"]["action"] for r in tight["by_row"]}
    assert set(by) == set(tby)
    for key, act in by.items():
        assert act == tby[key], key
    assert ours["vs_tight"]["tight_frame"] == TIGHT_FRAME
    assert ours["vs_tight"]["actions_match_tight"] is True
