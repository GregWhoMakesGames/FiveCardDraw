"""CO chart-range predicates for BN-vs-CO rows r=93% and r=96%."""

from __future__ import annotations

import pytest

from fivecarddraw.cards import BUG_ID, parse_hand
from fivecarddraw.hand_rank import HandCategory, evaluate_hand
from fivecarddraw.validation.button_vs_cutoff_r93_96 import (
    CHART_PAIR_POLICIES,
    DEFAULT_SEED,
    OWNED_R_PCTS,
    assert_owned_r,
    co_chart_bucket,
    generate_bn_vs_chart_co_deals,
    generate_bn_vs_chart_co_deals_tracked,
    is_co_chart_open,
    pair_policies_at,
    sample_chart_co_ids,
)
from fivecarddraw.validation.button_vs_cutoff_tight import (
    PAIR_J_JOKER,
    PAIR_K_JOKER,
    PAIR_K_NO_JOKER,
    PAIR_Q_JOKER,
    PAIR_Q_NO_JOKER,
    is_co_tight_open,
)
from fivecarddraw.validation.cutoff_open_chart import (
    POLICY_ACE_OR_JOKER,
    POLICY_JOKER_ONLY,
    POLICY_PASS,
    opening_policy_playable_pct,
)
from fivecarddraw.validation.cutoff_open_sandbag import (
    PAIR_K_ACE_IDS,
    PAIR_Q_ACE_IDS,
)
from fivecarddraw.validation.postdraw_nonbluff_ev import LOCKED_BN_DRAW
from fivecarddraw.validation.showdown_matrix import classify_opener


def _ids(cards) -> tuple[int, ...]:
    return tuple(sorted(c.card_id for c in cards))


PAIR_K_ACE = parse_hand("Kh Kd As 7h 4c")
PAIR_Q_ACE = parse_hand("Qh Qd As 7h 4c")
PAIR_J_ACE = parse_hand("Jh Jd As 7h 4c")
PAIR_J_BARE = parse_hand("Js Jh 9c 8h 2d")
PAIR_A = parse_hand("As Ad 9c 8h 2d")
TWO_PAIR = parse_hand("Ks Kd 9c 9h 2d")
ACES_UP = parse_hand("As Ad 9c 9h 2d")
TRIPS = parse_hand("7s 7d 7h 9c 2d")
BOAT = parse_hand("9s 9d 9h 2c 2d")
STRAIGHT = parse_hand("9s 8h 7c 6d 5s")
JUNK = parse_hand("9s 8h 7c 5d 2s")


def test_owned_rows_only():
    assert OWNED_R_PCTS == (93, 96)
    assert set(CHART_PAIR_POLICIES) == {93, 96}
    with pytest.raises(ValueError, match="owns r"):
        assert_owned_r(90)
    with pytest.raises(ValueError, match="79"):
        pair_policies_at(79)


def test_user_range_pins():
    p93 = pair_policies_at(93)
    p96 = pair_policies_at(96)
    assert p93["pair_J"] == POLICY_PASS
    assert p93["pair_Q"] == POLICY_JOKER_ONLY
    assert p93["pair_K"] == POLICY_ACE_OR_JOKER
    assert p96["pair_J"] == POLICY_PASS
    assert p96["pair_Q"] == POLICY_JOKER_ONLY
    assert p96["pair_K"] == POLICY_JOKER_ONLY


def test_policies_match_signed_chart_playable_pcts():
    """r=93 / 96 integer rules agree with cutoff_open_chart playable bands."""
    # Signed playable pcts from cutoff_open_sandbag_v1 (r* rounded).
    chart = {
        "pair_J": {
            "class_avg": 79,
            "ace": 86,
            "joker": 93,
            "joker_through_100": False,
        },
        "pair_Q": {
            "class_avg": 84,
            "ace": 90,
            "joker": 100,
            "joker_through_100": True,
        },
        "pair_K": {
            "class_avg": 87,
            "ace": 96,
            "joker": 100,
            "joker_through_100": True,
        },
    }
    for r_pct in OWNED_R_PCTS:
        for cls, spec in chart.items():
            got = opening_policy_playable_pct(
                r_pct,
                pct_class=spec["class_avg"],
                pct_ace=spec["ace"],
                pct_joker=spec["joker"],
                joker_through_100=spec["joker_through_100"],
            )
            assert got == pair_policies_at(r_pct)[cls], (r_pct, cls, got)


def test_bug_is_ace_kicker_not_trips():
    assert classify_opener(PAIR_Q_JOKER) == "pair_Q"
    assert classify_opener(PAIR_K_JOKER) == "pair_K"
    assert evaluate_hand(PAIR_Q_JOKER).category == HandCategory.ONE_PAIR
    assert evaluate_hand(PAIR_K_JOKER).category == HandCategory.ONE_PAIR
    assert classify_opener(PAIR_K_ACE) == "pair_K"
    assert tuple(sorted(c.card_id for c in PAIR_K_ACE)) == PAIR_K_ACE_IDS
    assert tuple(sorted(c.card_id for c in PAIR_Q_ACE)) == PAIR_Q_ACE_IDS


def test_always_open_made_at_both_rows():
    for r_pct in OWNED_R_PCTS:
        for hand in (PAIR_A, TWO_PAIR, ACES_UP, TRIPS, BOAT, STRAIGHT):
            assert is_co_chart_open(classify_opener(hand), _ids(hand), r_pct) is True
        assert is_co_chart_open(classify_opener(JUNK), _ids(JUNK), r_pct) is False
        assert is_co_chart_open(None, _ids(JUNK), r_pct) is False


def test_jj_never_opens():
    for r_pct in OWNED_R_PCTS:
        for hand in (PAIR_J_BARE, PAIR_J_JOKER, PAIR_J_ACE):
            assert is_co_chart_open(classify_opener(hand), _ids(hand), r_pct) is False


def test_qq_joker_only_at_both_rows():
    for r_pct in OWNED_R_PCTS:
        assert is_co_chart_open(classify_opener(PAIR_Q_JOKER), _ids(PAIR_Q_JOKER), r_pct)
        assert not is_co_chart_open(
            classify_opener(PAIR_Q_NO_JOKER), _ids(PAIR_Q_NO_JOKER), r_pct
        )
        assert not is_co_chart_open(
            classify_opener(PAIR_Q_ACE), _ids(PAIR_Q_ACE), r_pct
        )


def test_kk_ace_or_joker_only_at_93():
    assert is_co_chart_open(classify_opener(PAIR_K_JOKER), _ids(PAIR_K_JOKER), 93)
    assert is_co_chart_open(classify_opener(PAIR_K_ACE), _ids(PAIR_K_ACE), 93)
    assert not is_co_chart_open(
        classify_opener(PAIR_K_NO_JOKER), _ids(PAIR_K_NO_JOKER), 93
    )


def test_kk_joker_only_at_96():
    assert is_co_chart_open(classify_opener(PAIR_K_JOKER), _ids(PAIR_K_JOKER), 96)
    assert not is_co_chart_open(classify_opener(PAIR_K_ACE), _ids(PAIR_K_ACE), 96)
    assert not is_co_chart_open(
        classify_opener(PAIR_K_NO_JOKER), _ids(PAIR_K_NO_JOKER), 96
    )


def test_r96_predicate_matches_tight_polar():
    hands = (
        PAIR_A,
        TWO_PAIR,
        ACES_UP,
        TRIPS,
        BOAT,
        STRAIGHT,
        PAIR_Q_JOKER,
        PAIR_K_JOKER,
        PAIR_Q_NO_JOKER,
        PAIR_K_NO_JOKER,
        PAIR_Q_ACE,
        PAIR_K_ACE,
        PAIR_J_BARE,
        PAIR_J_JOKER,
        PAIR_J_ACE,
        JUNK,
    )
    for hand in hands:
        ids = _ids(hand)
        cls = classify_opener(hand)
        assert is_co_chart_open(cls, ids, 96) is is_co_tight_open(cls, ids), hand


def test_sampler_respects_range():
    import random

    rng = random.Random(DEFAULT_SEED)
    for r_pct in OWNED_R_PCTS:
        saw_kk_ace = False
        saw_kk_joker = False
        for _ in range(80):
            sampled = sample_chart_co_ids(rng, r_pct, blocked=set())
            assert sampled is not None
            ids, cls = sampled
            assert is_co_chart_open(cls, ids, r_pct)
            assert cls != "pair_J"
            if cls == "pair_Q":
                assert BUG_ID in ids
            if cls == "pair_K":
                if BUG_ID in ids:
                    saw_kk_joker = True
                else:
                    saw_kk_ace = True
                    assert r_pct == 93
        if r_pct == 96:
            assert saw_kk_ace is False
        # 80 draws of a ~1–4% slice may miss KK+joker; do not require it.


def test_hu_generator_locked_draws():
    deals = generate_bn_vs_chart_co_deals(
        "pair_J", 96, n_deals=8, seed=3
    )
    assert len(deals) == 8
    assert all(d.caller_class == "pair_J" for d in deals)
    assert all(d.caller_d == LOCKED_BN_DRAW.pair_d for d in deals)
    for d in deals:
        assert d.opener_class != "pair_J"
        assert d.opener_class in {
            "pair_A",
            "pair_Q",
            "pair_K",
            "two_pair",
            "two_pair_aces_up",
            "trips",
            "trips_K",
            "trips_A",
            "straight",
            "flush",
            "full_house",
            "four_of_a_kind",
            "straight_flush",
            "five_aces",
        }


def test_r93_sampler_emits_kk_ace_and_r96_does_not():
    import random

    rng93 = random.Random(DEFAULT_SEED)
    rng96 = random.Random(DEFAULT_SEED)
    n93_ace = n96_ace = 0
    for _ in range(400):
        s93 = sample_chart_co_ids(rng93, 93, blocked=set())
        s96 = sample_chart_co_ids(rng96, 96, blocked=set())
        assert s93 is not None and s96 is not None
        if co_chart_bucket(s93[1], s93[0]) == "pair_K_ace":
            n93_ace += 1
        if co_chart_bucket(s96[1], s96[0]) == "pair_K_ace":
            n96_ace += 1
    assert n93_ace > 0
    assert n96_ace == 0


def test_r93_hu_tracks_kk_ace_bucket():
    deals, co_rows = generate_bn_vs_chart_co_deals_tracked(
        "pair_A", 93, n_deals=120, seed=11
    )
    assert len(deals) == 120
    buckets = [co_chart_bucket(d.opener_class, ids) for d, ids in zip(deals, co_rows)]
    assert "pair_Q_ace" not in buckets
    assert "pair_J" not in buckets
    assert "pair_J_joker" not in buckets
