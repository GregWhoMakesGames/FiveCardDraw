"""BN fold/call/raise vs CO opening at chart r=79%."""

from __future__ import annotations

import json
from pathlib import Path

from fivecarddraw.cards import BUG_ID, parse_hand
from fivecarddraw.hand_rank import HandCategory, evaluate_hand
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
)
from fivecarddraw.validation.button_vs_cutoff_r79 import (
    DEFAULT_N_2TO1,
    DEFAULT_N_HU,
    DEFAULT_SEED,
    FRAME,
    PAIR_J_ACE,
    PAIR_J_BARE,
    PAIR_J_JOKER,
    PAIR_K_BARE,
    PAIR_K_JOKER,
    PAIR_Q_BARE,
    PAIR_Q_JOKER,
    SANDBAG_RATE_PCT,
    generate_bn_vs_co_r79_deals,
    is_co_r79_open,
    jj_has_ace_or_joker,
    sample_r79_co_ids,
)
from fivecarddraw.validation.button_vs_cutoff_tight import is_co_tight_open
from fivecarddraw.validation.postdraw_nonbluff_ev import LOCKED_BN_DRAW
from fivecarddraw.validation.showdown_matrix import classify_opener


FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "validation"
    / "button_vs_cutoff_r79.json"
)


def _ids(cards) -> tuple[int, ...]:
    return tuple(sorted(c.card_id for c in cards))


def test_accounting_pins():
    assert FOLD_EV == 0.0
    assert BN_CALL_INVEST == 2.0
    assert BN_RAISE_INVEST == 4.0
    assert CALL_POT == 6.0
    assert RAISE_POT == 10.0
    assert CO_P_FOLD_AIR == 0.0
    assert checkdown_ev_bn(won=True, tied=False, pot=RAISE_POT) - BN_RAISE_INVEST == 6.0
    assert checkdown_ev_bn(won=False, tied=True, pot=RAISE_POT) - BN_RAISE_INVEST == 1.0
    assert checkdown_ev_bn(won=False, tied=False, pot=RAISE_POT) - BN_RAISE_INVEST == -4.0
    assert 6.0 - BN_CALL_INVEST == 4.0


def test_kk_plus_joker_is_pair_k_not_trips():
    """Bug is an ace (or fill), not a third king — same pin as polar labs."""
    kk_joker = parse_hand("Ks Kh Bu 9c 2d")
    assert classify_opener(kk_joker) == "pair_K"
    trips_k = parse_hand("Ks Kh Kd 9c 2d")
    assert classify_opener(trips_k) == "trips_K"
    assert evaluate_hand(PAIR_J_JOKER).category == HandCategory.ONE_PAIR
    assert classify_opener(PAIR_J_JOKER) == "pair_J"


def test_r79_range_predicate_vs_polars():
    aa = parse_hand("As Ad 9c 8h 2d")
    tp = parse_hand("Ks Kd 9c 9h 2d")
    aces_up = parse_hand("As Ad 9c 9h 2d")
    trips = parse_hand("7s 7d 7h 9c 2d")
    junk = parse_hand("9s 8h 7c 5d 2s")
    assert is_co_r79_open(classify_opener(aa), _ids(aa)) is True
    assert is_co_r79_open(classify_opener(tp), _ids(tp)) is True
    assert is_co_r79_open(classify_opener(aces_up), _ids(aces_up)) is True
    assert is_co_r79_open(classify_opener(trips), _ids(trips)) is True
    assert is_co_r79_open(classify_opener(junk), _ids(junk)) is False
    assert is_co_r79_open(None, _ids(junk)) is False

    # JJ: ace or joker in; bare JJ out (the r=79% cut vs all-legal).
    assert jj_has_ace_or_joker(_ids(PAIR_J_JOKER)) is True
    assert jj_has_ace_or_joker(_ids(PAIR_J_ACE)) is True
    assert jj_has_ace_or_joker(_ids(PAIR_J_BARE)) is False
    assert is_co_r79_open(classify_opener(PAIR_J_JOKER), _ids(PAIR_J_JOKER)) is True
    assert is_co_r79_open(classify_opener(PAIR_J_ACE), _ids(PAIR_J_ACE)) is True
    assert is_co_r79_open(classify_opener(PAIR_J_BARE), _ids(PAIR_J_BARE)) is False

    # QQ / KK class average: open without the joker (unlike the tight polar).
    assert is_co_r79_open(classify_opener(PAIR_Q_BARE), _ids(PAIR_Q_BARE)) is True
    assert is_co_r79_open(classify_opener(PAIR_K_BARE), _ids(PAIR_K_BARE)) is True
    assert is_co_r79_open(classify_opener(PAIR_Q_JOKER), _ids(PAIR_Q_JOKER)) is True
    assert is_co_r79_open(classify_opener(PAIR_K_JOKER), _ids(PAIR_K_JOKER)) is True
    assert is_co_tight_open(classify_opener(PAIR_Q_BARE), _ids(PAIR_Q_BARE)) is False
    assert is_co_tight_open(classify_opener(PAIR_K_BARE), _ids(PAIR_K_BARE)) is False
    assert is_co_tight_open(classify_opener(PAIR_J_JOKER), _ids(PAIR_J_JOKER)) is False


def test_r79_sampler_never_emits_bare_jj():
    import random

    rng = random.Random(DEFAULT_SEED)
    n_qq_kk_no_bug = 0
    for _ in range(80):
        sampled = sample_r79_co_ids(rng, blocked=set())
        assert sampled is not None
        ids, cls = sampled
        assert is_co_r79_open(cls, ids)
        if cls == "pair_J":
            assert jj_has_ace_or_joker(ids)
        if cls in ("pair_Q", "pair_K") and BUG_ID not in ids:
            n_qq_kk_no_bug += 1
    # Unlike tight, class-average QQ/KK (no joker) are in this range.
    assert n_qq_kk_no_bug >= 1


def test_hu_generator_locked_draws_and_r79_co():
    from fivecarddraw.validation.postdraw_nonbluff_ev import play_honest_deal

    deals = generate_bn_vs_co_r79_deals("pair_J", n_deals=12, seed=7)
    assert len(deals) == 12
    assert all(d.caller_class == "pair_J" for d in deals)
    assert all(d.caller_d == LOCKED_BN_DRAW.pair_d for d in deals)
    assert all(d.d in (0, 1, 2, 3) for d in deals)
    assert all(d.opener_class is not None for d in deals)
    ev_co, ev_bn, _flags = play_honest_deal(deals[0])
    assert abs(ev_co + ev_bn - CALL_POT) < 1e-9


def test_trips_plus_sampler_stays_in_bucket():
    deals = generate_bn_vs_co_r79_deals("trips_plus", n_deals=8, seed=11)
    assert len(deals) == 8
    assert all(d.caller_class in TRIPS_PLUS_CLASSES for d in deals)


def test_decide_action_reused_from_all_legal_polar():
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
    raise_ = decide_action(
        ev_call_honest=0.3,
        se_call_honest=0.03,
        ev_call_cd=1.2,
        se_call_cd=0.03,
        ev_raise_cd=1.4,
        se_raise_cd=0.05,
        se_raise_minus_call_cd=0.04,
    )
    assert raise_["action"] == "raise"


def test_fixture_product_chart():
    assert FIXTURE.exists(), (
        "run python -m fivecarddraw.validation.button_vs_cutoff_r79 --write-fixture"
    )
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    meta = data["meta"]
    assert meta["frame"] == FRAME
    assert meta["sandbag_rate_pct"] == SANDBAG_RATE_PCT
    assert meta["seed"] == DEFAULT_SEED
    assert meta["n_hu"] == DEFAULT_N_HU
    assert meta["n_2to1"] == DEFAULT_N_2TO1
    assert meta["accounting"]["fold"] == 0.0
    assert meta["accounting"]["p_co_folds_air"] == 0.0
    assert meta["accounting"]["call_pot"] == 6.0
    assert meta["accounting"]["raise_pot"] == 10.0
    assert meta["locked_draws"]["name"] == "tp1_tr2_q1"
    assert meta["locked_draws"]["pair_d"] == 3
    assert meta["locked_draws"]["two_pair_d"] == 1
    assert meta["locked_draws"]["trips_d"] == 2
    assert meta["parent_frame"] == "cutoff_open_sandbag_v1"
    assert meta["co_range"]["jj"] == "ace or joker"
    assert meta["co_range"]["qq"] == "open (class average)"
    assert meta["co_range"]["kk"] == "open (class average)"
    assert "no air" in meta["matchup"].lower() or "always continues" in meta["matchup"]

    answers = data["answers"]
    assert answers["fold_equity_vs_air"] == 0.0
    assert answers["sandbag_rate_pct"] == 79
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
        assert row["se_call"] > 0.0
        assert row["se_raise_checkdown"] > 0.0

    assert answers["chart"] == {
        "pair_J": "fold",
        "pair_Q": "fold",
        "pair_K": "fold",
        "pair_A": "fold",
        "two_pair": "raise",
        "two_pair_aces_up": "raise",
        "trips_plus": "raise",
        "two_to_one": "call",
    }
    # One-pair: still not a value raise. AA already folds (inflection vs all-legal).
    assert by["pair_J"]["action"] == "fold"
    assert by["pair_J"]["ev_call"] < 0.0
    assert by["pair_Q"]["action"] == "fold"
    assert by["pair_K"]["action"] == "fold"
    assert by["pair_K"]["needs_later_tree"] is True
    assert answers["pair_A_action"] == "fold"
    assert answers["aa_still_raises"] is False
    assert by["pair_A"]["action"] == "fold"
    assert by["pair_A"]["ev_call"] < 0.0
    assert by["pair_A"]["p_bn_wins_final"] < 0.5
    assert by["pair_A"]["recommend_tight_rule"]["action"] == "fold"
    # Two pair has *not* flipped to the tight polar’s thin call.
    assert by["two_pair"]["action"] == "raise"
    assert by["two_pair"]["p_bn_wins_final"] > 0.5
    # Trips+ / aces-up stay value raises.
    assert by["trips_plus"]["action"] == "raise"
    assert by["trips_plus"]["p_bn_wins_final"] > 0.70
    assert by["two_pair_aces_up"]["action"] == "raise"
    assert by["two_to_one"]["action"] == "call"
    assert by["two_to_one"]["ev_call"] > 0.5
