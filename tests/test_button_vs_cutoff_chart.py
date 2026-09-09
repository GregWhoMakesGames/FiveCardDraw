"""BN fold/call/raise vs CO at chart r=87% and r=90% (owned grid rows)."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from fivecarddraw.cards import BUG_ID, parse_hand
from fivecarddraw.hand_rank import HandCategory, evaluate_hand
from fivecarddraw.validation.button_vs_cutoff_chart import (
    DEFAULT_N_HU,
    DEFAULT_SEED,
    OWNED_RATES,
    PAIR_J_ACE,
    PAIR_J_BARE,
    PAIR_J_JOKER,
    PAIR_K_ACE,
    PAIR_K_BARE,
    PAIR_K_JOKER,
    PAIR_Q_ACE,
    PAIR_Q_BARE,
    PAIR_Q_JOKER,
    POLICY_ACE_OR_JOKER,
    POLICY_JOKER_ONLY,
    RANGE_R87,
    RANGE_R90,
    generate_bn_vs_chart_co_deals,
    is_co_chart_open,
    sample_chart_co_ids,
    spec_for,
)
from fivecarddraw.validation.button_vs_cutoff_tight import (
    CALL_INVEST,
    FOLD_EV,
    RAISE_INVEST,
    RAISE_POT,
    recommend_action,
)
from fivecarddraw.validation.postdraw_nonbluff_ev import LOCKED_BN_DRAW
from fivecarddraw.validation.showdown_matrix import classify_opener


def _ids(cards) -> tuple[int, ...]:
    return tuple(sorted(c.card_id for c in cards))


def test_owned_rates_only():
    assert OWNED_RATES == (87, 90)
    assert spec_for(87) is RANGE_R87
    assert spec_for(90) is RANGE_R90
    assert RANGE_R87.pair_J == POLICY_JOKER_ONLY
    assert RANGE_R87.pair_Q == POLICY_ACE_OR_JOKER
    assert RANGE_R87.pair_K == POLICY_ACE_OR_JOKER
    assert RANGE_R90.pair_J == POLICY_JOKER_ONLY
    assert RANGE_R90.pair_Q == POLICY_JOKER_ONLY
    assert RANGE_R90.pair_K == POLICY_ACE_OR_JOKER
    with pytest.raises(ValueError, match="not owned"):
        spec_for(79)
    with pytest.raises(ValueError, match="not owned"):
        spec_for(96)


def test_bug_is_ace_kicker_not_trips():
    assert classify_opener(PAIR_J_JOKER) == "pair_J"
    assert classify_opener(PAIR_Q_JOKER) == "pair_Q"
    assert classify_opener(PAIR_K_JOKER) == "pair_K"
    assert evaluate_hand(PAIR_Q_JOKER).category == HandCategory.ONE_PAIR
    assert evaluate_hand(PAIR_K_JOKER).tiebreak[0] == 13
    trips_k = parse_hand("Ks Kh Kd 9c 2d")
    assert classify_opener(trips_k) == "trips_K"


def test_r87_range_predicate():
    spec = RANGE_R87
    aa = parse_hand("As Ad 9c 8h 2d")
    tp = parse_hand("Ks Kd 9c 9h 2d")
    aces_up = parse_hand("As Ad 9c 9h 2d")
    trips = parse_hand("7s 7d 7h 9c 2d")
    boat = parse_hand("9s 9d 9h 2c 2d")
    straight = parse_hand("9s 8h 7c 6d 5s")
    junk = parse_hand("9s 8h 7c 5d 2s")
    assert is_co_chart_open(classify_opener(aa), _ids(aa), spec) is True
    assert is_co_chart_open(classify_opener(tp), _ids(tp), spec) is True
    assert is_co_chart_open(classify_opener(aces_up), _ids(aces_up), spec) is True
    assert is_co_chart_open(classify_opener(trips), _ids(trips), spec) is True
    assert is_co_chart_open(classify_opener(boat), _ids(boat), spec) is True
    assert is_co_chart_open(classify_opener(straight), _ids(straight), spec) is True
    # JJ: joker only.
    assert is_co_chart_open(classify_opener(PAIR_J_JOKER), _ids(PAIR_J_JOKER), spec) is True
    assert is_co_chart_open(classify_opener(PAIR_J_ACE), _ids(PAIR_J_ACE), spec) is False
    assert is_co_chart_open(classify_opener(PAIR_J_BARE), _ids(PAIR_J_BARE), spec) is False
    # QQ: ace or joker.
    assert is_co_chart_open(classify_opener(PAIR_Q_JOKER), _ids(PAIR_Q_JOKER), spec) is True
    assert is_co_chart_open(classify_opener(PAIR_Q_ACE), _ids(PAIR_Q_ACE), spec) is True
    assert is_co_chart_open(classify_opener(PAIR_Q_BARE), _ids(PAIR_Q_BARE), spec) is False
    # KK: ace or joker.
    assert is_co_chart_open(classify_opener(PAIR_K_JOKER), _ids(PAIR_K_JOKER), spec) is True
    assert is_co_chart_open(classify_opener(PAIR_K_ACE), _ids(PAIR_K_ACE), spec) is True
    assert is_co_chart_open(classify_opener(PAIR_K_BARE), _ids(PAIR_K_BARE), spec) is False
    assert is_co_chart_open(classify_opener(junk), _ids(junk), spec) is False
    assert is_co_chart_open(None, _ids(junk), spec) is False


def test_r90_range_predicate():
    spec = RANGE_R90
    # JJ still joker only; QQ drops to joker only; KK still ace or joker.
    assert is_co_chart_open(classify_opener(PAIR_J_JOKER), _ids(PAIR_J_JOKER), spec) is True
    assert is_co_chart_open(classify_opener(PAIR_J_ACE), _ids(PAIR_J_ACE), spec) is False
    assert is_co_chart_open(classify_opener(PAIR_Q_JOKER), _ids(PAIR_Q_JOKER), spec) is True
    assert is_co_chart_open(classify_opener(PAIR_Q_ACE), _ids(PAIR_Q_ACE), spec) is False
    assert is_co_chart_open(classify_opener(PAIR_Q_BARE), _ids(PAIR_Q_BARE), spec) is False
    assert is_co_chart_open(classify_opener(PAIR_K_JOKER), _ids(PAIR_K_JOKER), spec) is True
    assert is_co_chart_open(classify_opener(PAIR_K_ACE), _ids(PAIR_K_ACE), spec) is True
    assert is_co_chart_open(classify_opener(PAIR_K_BARE), _ids(PAIR_K_BARE), spec) is False
    aa = parse_hand("As Ad 9c 8h 2d")
    assert is_co_chart_open(classify_opener(aa), _ids(aa), spec) is True


def test_r90_is_stricter_than_r87_on_qq_ace():
    """The 87 → 90 step is QQ ace-kicker leaving the CO range."""
    qq_ace_ids = _ids(PAIR_Q_ACE)
    cls = classify_opener(PAIR_Q_ACE)
    assert is_co_chart_open(cls, qq_ace_ids, RANGE_R87) is True
    assert is_co_chart_open(cls, qq_ace_ids, RANGE_R90) is False


def test_accounting_and_action_rule_match_tight_polar():
    assert FOLD_EV == 0.0
    assert CALL_INVEST == 2.0
    assert RAISE_INVEST == 4.0
    assert RAISE_POT == 10.0
    # Same action rule as the tight polar: dog with +EV call → call, not raise.
    call = recommend_action(ev_call=0.30, ev_raise=0.10, p_bn_win=0.40)
    assert call["action"] == "call"
    raise_ = recommend_action(ev_call=4.0, ev_raise=3.0, p_bn_win=0.70)
    assert raise_["action"] == "raise"
    fold = recommend_action(ev_call=-0.40, ev_raise=-1.10, p_bn_win=0.32)
    assert fold["action"] == "fold"


def test_sampler_respects_r87_and_r90():
    rng = random.Random(DEFAULT_SEED)
    for spec in (RANGE_R87, RANGE_R90):
        for _ in range(40):
            sampled = sample_chart_co_ids(rng, spec, blocked=set())
            assert sampled is not None
            ids, cls = sampled
            assert is_co_chart_open(cls, ids, spec)
            if cls == "pair_J":
                assert BUG_ID in ids
            if cls == "pair_Q":
                if spec is RANGE_R90:
                    assert BUG_ID in ids
                else:
                    assert BUG_ID in ids or any(
                        i in ids for i in range(48, 52)
                    )
            if cls == "pair_K":
                assert BUG_ID in ids or any(i in ids for i in range(48, 52))
            assert cls != "pair_J" or BUG_ID in ids


def test_hu_generator_locked_draws():
    deals = generate_bn_vs_chart_co_deals(
        "pair_A", RANGE_R87, n_deals=8, seed=11
    )
    assert len(deals) == 8
    assert all(d.caller_class == "pair_A" for d in deals)
    assert all(d.caller_d == LOCKED_BN_DRAW.pair_d for d in deals)
    assert all(d.d in (0, 1, 2, 3) for d in deals)
    for d in deals:
        assert d.opener_class is not None


def test_pins_n_and_seed():
    assert DEFAULT_N_HU == 4_000
    assert DEFAULT_SEED == 20260909
    assert DEFAULT_SEED not in {20260907, 20260908}


def test_fixture_paths_named_for_owned_frames():
    root = Path(__file__).resolve().parent / "fixtures" / "validation"
    assert (root / "button_vs_cutoff_r87.json").name.endswith("r87.json")
    assert (root / "button_vs_cutoff_r90.json").name.endswith("r90.json")
