"""BN fold/call/raise vs CO opening every legal hand (range 1)."""

from __future__ import annotations

import json
from pathlib import Path

from fivecarddraw.cards import parse_hand
from fivecarddraw.hand_rank import HandCategory, HandValue
from fivecarddraw.validation.button_vs_cutoff import (
    BN_CALL_INVEST,
    BN_RAISE_INVEST,
    CALL_POT,
    CO_P_FOLD_AIR,
    FOLD_EV,
    RAISE_POT,
    TRIPS_PLUS_CLASSES,
    checkdown_ev_bn,
    decide_action,
    generate_bn_vs_co_legal_deals,
    mean_se,
)
from fivecarddraw.validation.cutoff_open import bn_value_continue_as_m2_drawer
from fivecarddraw.validation.postdraw_nonbluff_ev import LOCKED_BN_DRAW, play_honest_deal
from fivecarddraw.validation.showdown_matrix import classify_opener


FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "validation"
    / "button_vs_cutoff_all_legal.json"
)


def test_accounting_pins():
    assert FOLD_EV == 0.0
    assert BN_CALL_INVEST == 2.0
    assert BN_RAISE_INVEST == 4.0
    assert CALL_POT == 6.0
    assert RAISE_POT == 10.0
    assert CO_P_FOLD_AIR == 0.0
    # Steal if BN folds = CO takes the $2 antes; BN's decision EV is 0.
    assert checkdown_ev_bn(won=True, tied=False, pot=RAISE_POT) - BN_RAISE_INVEST == 6.0
    assert checkdown_ev_bn(won=False, tied=True, pot=RAISE_POT) - BN_RAISE_INVEST == 1.0
    assert checkdown_ev_bn(won=False, tied=False, pot=RAISE_POT) - BN_RAISE_INVEST == -4.0
    # Call net = street − $2. Winning the $6 checkdown → +$4 vs fold.
    assert 6.0 - BN_CALL_INVEST == 4.0


def test_kk_plus_joker_is_pair_k_not_trips():
    """Bug is an ace (or fill), not a third king."""
    kk_joker = parse_hand("Ks Kh Bu 9c 2d")
    assert classify_opener(kk_joker) == "pair_K"
    trips_k = parse_hand("Ks Kh Kd 9c 2d")
    assert classify_opener(trips_k) == "trips_K"


def test_mean_se_and_decide_action():
    m, se = mean_se([1.0, 1.0, 1.0, 1.0])
    assert abs(m - 1.0) < 1e-12
    assert se == 0.0
    fold = decide_action(
        ev_call_honest=-0.5,
        se_call_honest=0.02,
        ev_call_cd=-0.4,
        se_call_cd=0.02,
        ev_raise_cd=-1.0,
        se_raise_cd=0.04,
        se_raise_minus_call_cd=0.03,
    )
    assert fold["action"] == "fold"
    assert fold["needs_later_tree"] is False
    call = decide_action(
        ev_call_honest=0.4,
        se_call_honest=0.03,
        ev_call_cd=0.5,
        se_call_cd=0.03,
        ev_raise_cd=0.1,
        se_raise_cd=0.05,
        se_raise_minus_call_cd=0.04,
    )
    assert call["action"] == "call"
    raise_ = decide_action(
        ev_call_honest=5.0,
        se_call_honest=0.03,
        ev_call_cd=3.3,
        se_call_cd=0.03,
        ev_raise_cd=4.8,
        se_raise_cd=0.05,
        se_raise_minus_call_cd=0.04,
    )
    assert raise_["action"] == "raise"
    close_fold = decide_action(
        ev_call_honest=-0.02,
        se_call_honest=0.03,
        ev_call_cd=0.01,
        se_call_cd=0.03,
        ev_raise_cd=-0.1,
        se_raise_cd=0.05,
        se_raise_minus_call_cd=0.04,
    )
    assert close_fold["action"] == "fold"
    assert close_fold["needs_later_tree"] is True


def test_generator_locked_draws_and_co_is_legal():
    deals = generate_bn_vs_co_legal_deals("pair_J", n_deals=12, seed=7)
    assert len(deals) == 12
    # d is CO's draw (varies by CO class); BN pair_J is locked d=3.
    assert all(d.caller_d == LOCKED_BN_DRAW.pair_d for d in deals)
    assert all(d.opener_class is not None for d in deals)
    # CO is some open-legal class; BN is the pair_J caller in the M2 mapping.
    assert all(d.caller_class == "pair_J" for d in deals)
    assert all(d.d in (0, 1, 2, 3) for d in deals)
    ev_co, ev_bn, _flags = play_honest_deal(deals[0])
    assert abs(ev_co + ev_bn - CALL_POT) < 1e-9


def test_trips_plus_sampler_stays_in_bucket():
    deals = generate_bn_vs_co_legal_deals("trips_plus", n_deals=8, seed=11)
    assert len(deals) == 8
    assert all(d.caller_class in TRIPS_PLUS_CLASSES for d in deals)


def test_two_pair_bn_continues_vs_co_value_bet():
    sp, face = bn_value_continue_as_m2_drawer(
        HandValue(category=HandCategory.TWO_PAIR, tiebreak=(13, 12, 9))
    )
    assert sp is False
    assert face == 14


def test_fixture_product_chart():
    assert FIXTURE.exists(), (
        "run python -m fivecarddraw.validation.button_vs_cutoff --write-fixture"
    )
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    meta = data["meta"]
    assert meta["frame"] == "button_vs_cutoff_all_legal"
    assert meta["parent_frame"] == "cutoff_open_no_sandbagging"
    assert meta["accounting"]["fold"] == 0.0
    assert meta["accounting"]["p_co_folds_air"] == 0.0
    assert meta["accounting"]["call_pot"] == 6.0
    assert meta["accounting"]["raise_pot"] == 10.0
    assert meta["locked_draws"]["pair_d"] == 3
    assert meta["locked_draws"]["two_pair_d"] == 1
    assert meta["seed"] == 20260908
    assert meta["n_hu"] == 4000
    assert meta["n_2to1"] == 2000
    assert "no air" in meta["matchup"].lower() or "always continues" in meta["matchup"]

    answers = data["answers"]
    assert answers["fold_equity_vs_air"] == 0.0
    assert "no fold equity vs air" in answers["fold_equity_note"].lower()
    assert answers["chart"] == {
        "pair_J": "fold",
        "pair_Q": "fold",
        "pair_K": "fold",
        "pair_A": "raise",
        "two_pair": "raise",
        "two_pair_aces_up": "raise",
        "trips_plus": "raise",
        "two_to_one": "call",
    }
    by = {r["bn_spec"]: r for r in data["by_spec"]}
    for spec in (
        "pair_J",
        "pair_Q",
        "pair_K",
        "pair_A",
        "two_pair",
        "two_pair_aces_up",
        "trips_plus",
        "two_to_one",
    ):
        assert spec in by, spec
        row = by[spec]
        assert row["p_co_folds_air"] == 0.0
        assert row["ev_fold"] == 0.0
        assert row["n"] >= 1500
        assert row["action"] in {"fold", "call", "raise"}
        assert 0.0 <= row["p_bn_wins_final"] <= 1.0

    # Vs a 100% jacks+ CO range, a BN pair of jacks is not a raise for value.
    assert by["pair_J"]["action"] == "fold"
    assert by["pair_J"]["ev_call"] < -2.0
    assert by["pair_J"]["ev_raise_checkdown"] <= by["pair_J"]["ev_call_checkdown"] + 0.05
    # KK: honest call is −EV (pays off two pair+); checkdown call is slightly +EV.
    assert by["pair_K"]["action"] == "fold"
    assert by["pair_K"]["ev_call"] < -0.5
    assert by["pair_K"]["ev_call_checkdown"] > 0.0
    # Two pair / trips+ have showdown equity vs a pair-heavy legal range.
    assert by["two_pair"]["p_bn_wins_final"] > by["pair_J"]["p_bn_wins_final"]
    assert by["trips_plus"]["p_bn_wins_final"] > by["two_pair"]["p_bn_wins_final"]
    assert by["pair_A"]["action"] == "raise"
    assert by["two_pair"]["action"] == "raise"
    assert by["trips_plus"]["action"] == "raise"
    assert by["trips_plus"]["p_bn_wins_final"] > 0.80
    # 2:1 drawers: no air to fold out, so they should not raise this bound.
    assert by["two_to_one"]["action"] == "call"
    assert by["two_to_one"]["ev_call"] > 1.0
    assert (
        by["two_to_one"]["ev_raise_checkdown"]
        <= by["two_to_one"]["ev_call_checkdown"] + 0.15
    )
