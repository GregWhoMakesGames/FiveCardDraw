"""BN fold/call/raise vs CO chart range at r=93%."""

from __future__ import annotations

import json
from pathlib import Path

from fivecarddraw.validation.button_vs_cutoff_r93_96 import FRAME_BY_R
from fivecarddraw.validation.cutoff_open_chart import (
    POLICY_ACE_OR_JOKER,
    POLICY_JOKER_ONLY,
    POLICY_PASS,
)


FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "validation"
    / "button_vs_cutoff_r93.json"
)
R_PCT = 93


def test_fixture_product_answers():
    assert FIXTURE.exists(), "run analyze-button-vs-cutoff-r93 --write-fixture"
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
    assert policies["pair_K"] == POLICY_ACE_OR_JOKER
    assert meta["co_range"]["matches_tight_polar"] is False

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
    assert answers["jj_dominated_raise"] is True
    # KK+ace is in this range; not in r=96 / tight polar.
    assert answers["pair_K_ace_share_on_aa_row"] > 0.02
    assert answers["pair_K_joker_share_on_aa_row"] > 0.0

    by = {r["key"]: r for r in data["by_row"]}
    for key in ("pair_J", "pair_Q", "pair_K", "pair_A"):
        row = by[key]
        assert row["recommend"]["action"] == "fold"
        assert row["ev_call"] < 0.0
        assert row["n"] == 4000.0
        assert row["se_call"] > 0.0
        assert row["p_bn_wins_final"] < 0.5
        assert row["co_mix"]["pair_Q_ace"] == 0.0
        assert row["co_mix"]["pair_K_ace"] > 0.0
    jj = by["pair_J"]
    assert 0.04 < jj["co_mix"]["pair_K_ace"] < 0.10
    two_pair = by["two_pair"]
    assert two_pair["recommend"]["action"] == "call"
    assert two_pair["p_bn_wins_final"] < 0.5
    assert two_pair["ev_call"] > 0.0
    trips = by["trips"]
    assert trips["recommend"]["action"] == "raise"
    assert trips["p_bn_wins_final"] > 0.5
    for key in ("pair_J_joker", "pair_J_ace", "pair_Q_joker", "pair_K_joker", "pair_K_ace"):
        assert by[key]["recommend"]["action"] == "fold"
        assert by[key]["ev_call"] < 0.0
