"""BN fold/call/raise vs a tight CO open (range 2)."""

from __future__ import annotations

import json
from pathlib import Path

from fivecarddraw.cards import BUG_ID, parse_hand
from fivecarddraw.hand_rank import HandCategory, evaluate_hand
from fivecarddraw.validation.button_vs_cutoff_tight import (
    CALL_INVEST,
    FOLD_EV,
    FRAME,
    PAIR_J_JOKER,
    PAIR_K_JOKER,
    PAIR_K_NO_JOKER,
    PAIR_Q_JOKER,
    PAIR_Q_NO_JOKER,
    RAISE_INVEST,
    RAISE_POT,
    ev_call_net,
    ev_raise_checkdown,
    generate_bn_vs_tight_co_deals,
    is_co_tight_open,
    recommend_action,
    sample_tight_co_ids,
)
from fivecarddraw.validation.postdraw_nonbluff_ev import LOCKED_BN_DRAW
from fivecarddraw.validation.showdown_matrix import classify_opener


FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "validation"
    / "button_vs_cutoff_tight.json"
)


def _ids(cards) -> tuple[int, ...]:
    return tuple(sorted(c.card_id for c in cards))


def test_bug_is_ace_kicker_not_trips():
    qq_j = PAIR_Q_JOKER
    kk_j = PAIR_K_JOKER
    assert classify_opener(qq_j) == "pair_Q"
    assert classify_opener(kk_j) == "pair_K"
    assert evaluate_hand(qq_j).category == HandCategory.ONE_PAIR
    assert evaluate_hand(kk_j).category == HandCategory.ONE_PAIR
    # Two queens + bug as ace ≠ three queens.
    assert evaluate_hand(qq_j).tiebreak[0] == 12
    assert evaluate_hand(kk_j).tiebreak[0] == 13
    jj_j = PAIR_J_JOKER
    assert classify_opener(jj_j) == "pair_J"
    assert evaluate_hand(jj_j).category == HandCategory.ONE_PAIR


def test_tight_range_predicate():
    aa = parse_hand("As Ad 9c 8h 2d")
    tp = parse_hand("Ks Kd 9c 9h 2d")
    aces_up = parse_hand("As Ad 9c 9h 2d")
    trips = parse_hand("7s 7d 7h 9c 2d")
    boat = parse_hand("9s 9d 9h 2c 2d")
    straight = parse_hand("9s 8h 7c 6d 5s")
    jj = parse_hand("Js Jh 9c 8h 2d")
    assert is_co_tight_open(classify_opener(aa), _ids(aa)) is True
    assert is_co_tight_open(classify_opener(tp), _ids(tp)) is True
    assert is_co_tight_open(classify_opener(aces_up), _ids(aces_up)) is True
    assert is_co_tight_open(classify_opener(trips), _ids(trips)) is True
    assert is_co_tight_open(classify_opener(boat), _ids(boat)) is True
    assert is_co_tight_open(classify_opener(straight), _ids(straight)) is True
    # Joker-pairs are in; the same ranks without the bug are not.
    assert is_co_tight_open(classify_opener(PAIR_Q_JOKER), _ids(PAIR_Q_JOKER)) is True
    assert is_co_tight_open(classify_opener(PAIR_K_JOKER), _ids(PAIR_K_JOKER)) is True
    assert is_co_tight_open(classify_opener(PAIR_Q_NO_JOKER), _ids(PAIR_Q_NO_JOKER)) is False
    assert is_co_tight_open(classify_opener(PAIR_K_NO_JOKER), _ids(PAIR_K_NO_JOKER)) is False
    # JJ is never in, including with the joker.
    assert is_co_tight_open(classify_opener(jj), _ids(jj)) is False
    assert is_co_tight_open(classify_opener(PAIR_J_JOKER), _ids(PAIR_J_JOKER)) is False
    assert is_co_tight_open(None, _ids(jj)) is False
    junk = parse_hand("9s 8h 7c 5d 2s")
    assert is_co_tight_open(classify_opener(junk), _ids(junk)) is False


def test_accounting_pins():
    assert FOLD_EV == 0.0
    assert CALL_INVEST == 2.0
    assert RAISE_INVEST == 4.0
    assert RAISE_POT == 10.0
    assert ev_call_net(6.0) == 4.0
    assert ev_call_net(0.0) == -2.0
    # Lock: raise-checkdown +$6; bust: −$4.
    assert ev_raise_checkdown(p_bn_win=1.0, p_tie=0.0) == 6.0
    assert ev_raise_checkdown(p_bn_win=0.0, p_tie=0.0) == -4.0
    assert ev_raise_checkdown(p_bn_win=0.0, p_tie=1.0) == 1.0


def test_recommend_fold_call_raise():
    fold = recommend_action(ev_call=-0.40, ev_raise=-1.10, p_bn_win=0.20)
    assert fold["action"] == "fold"
    assert fold["call_plus_ev_vs_fold"] is False
    assert fold["value_raise"] is False
    # Call +EV as a dog → call, not a value raise.
    call = recommend_action(ev_call=0.30, ev_raise=0.10, p_bn_win=0.40)
    assert call["action"] == "call"
    assert call["value_raise"] is False
    # Favorite with +EV raise-cd → raise for value (even if $6 call number is higher).
    raise_ = recommend_action(ev_call=4.0, ev_raise=3.0, p_bn_win=0.70)
    assert raise_["action"] == "raise"
    assert raise_["value_raise"] is True
    # JJ-style: both −EV vs fold; checkdown may lose *less* than stacking a call.
    dominated = recommend_action(ev_call=-3.2, ev_raise=-2.5, p_bn_win=0.15)
    assert dominated["action"] == "fold"
    assert dominated["value_raise"] is False
    assert dominated["raise_beats_call"] is True


def test_tight_co_sampler_never_emits_excluded():
    import random

    rng = random.Random(20260907)
    for _ in range(40):
        sampled = sample_tight_co_ids(rng, blocked=set())
        assert sampled is not None
        ids, cls = sampled
        assert is_co_tight_open(cls, ids)
        assert cls != "pair_J"
        if cls == "pair_Q":
            assert BUG_ID in ids
        if cls == "pair_K":
            assert BUG_ID in ids


def test_hu_generator_locked_draws_and_tight_co():
    deals = generate_bn_vs_tight_co_deals("pair_J", n_deals=8, seed=3)
    assert len(deals) == 8
    assert all(d.caller_class == "pair_J" for d in deals)
    assert all(d.caller_d == LOCKED_BN_DRAW.pair_d for d in deals)
    assert all(d.d in (0, 1, 2, 3) for d in deals)
    for d in deals:
        assert d.opener_class != "pair_J"
        if d.opener_class in ("pair_Q", "pair_K"):
            # Generator stores class only; those classes are in-range iff joker.
            pass
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


def test_fixture_product_answers():
    assert FIXTURE.exists(), "run analyze-button-vs-cutoff-tight --write-fixture"
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    meta = data["meta"]
    assert meta["frame"] == FRAME
    assert meta["accounting"]["fold"] == 0.0
    assert meta["locked_draws"]["pair_d"] == 3
    assert meta["locked_draws"]["two_pair_d"] == 1
    assert "not all-legal" in meta["matchup"]
    assert "pair_A" in meta["co_range"]["include"]
    assert "pair_Q with joker" in meta["co_range"]["include"]
    assert "pair_J" in meta["co_range"]["exclude"]

    answers = data["answers"]
    # Tight CO is much stronger than all-legal: low pairs fold.
    assert answers["jj_action"] == "fold"
    assert answers["jj_ev_call"] < 0.0
    assert answers["jj_dominated_raise"] is True
    assert "pair_J" in answers["low_pairs_fold"]
    assert answers["qq_action"] == "fold"
    assert answers["kk_action"] == "fold"
    assert answers["aa_action"] == "fold"
    assert answers["two_pair_action"] == "call"
    # Value: trips / aces-up raise vs this AA+ range (p_win > 0.5, raise-cd +EV).
    assert answers["trips_action"] == "raise"
    assert answers["trips_A_action"] == "raise"
    assert answers["aces_up_action"] == "raise"
    assert "trips" in answers["value_raise_classes"]
    assert "trips_A" in answers["value_raise_classes"]
    assert "two_pair_aces_up" in answers["value_raise_classes"]
    by = {r["key"]: r for r in data["by_row"]}
    for key in ("pair_J", "pair_Q", "pair_K", "pair_A"):
        row = by[key]
        assert row["recommend"]["action"] == "fold"
        assert row["ev_call"] < 0.0
        assert row["n"] == 4000.0
        assert row["se_call"] > 0.0
        assert row["p_bn_wins_final"] < 0.5
    # Street pieces exist. JJ is a dog and does not value-raise.
    jj = by["pair_J"]
    assert 0.0 <= jj["p_bn_wins_final"] < 0.35
    assert jj["recommend"]["value_raise"] is False
    trips = by["trips"]
    assert trips["ev_call"] > 0.0
    assert trips["ev_raise_checkdown"] > 0.0
    assert trips["p_bn_wins_final"] > 0.5
    assert trips["recommend"]["action"] == "raise"
    aces_up = by["two_pair_aces_up"]
    assert aces_up["ev_call"] > 0.0
    assert aces_up["recommend"]["action"] == "raise"
    two_pair = by["two_pair"]
    assert two_pair["ev_call"] > 0.0
    assert two_pair["recommend"]["action"] == "call"
    assert two_pair["p_bn_wins_final"] < 0.5
    # Joker / ace flavors do not flip low pairs off fold.
    for key in ("pair_J_joker", "pair_J_ace", "pair_Q_joker", "pair_K_joker"):
        assert by[key]["recommend"]["action"] == "fold"
        assert by[key]["ev_call"] < 0.0
    assert data["answers"]["flavor_action_flips"] == []
