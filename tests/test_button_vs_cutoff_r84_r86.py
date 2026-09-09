"""BN vs CO at chart thresholds r=84% and r=86% (interior rows only)."""

from __future__ import annotations

import json
import random
from pathlib import Path

from fivecarddraw.cards import BUG_ID, parse_hand
from fivecarddraw.hand_rank import HandCategory, evaluate_hand
from fivecarddraw.validation.button_vs_cutoff_r84_r86 import (
    CALL_INVEST,
    DEFAULT_N_HU,
    DEFAULT_SEED_R84,
    DEFAULT_SEED_R86,
    FOLD_EV,
    PAIR_J_ACE,
    PAIR_J_BARE,
    PAIR_J_JOKER,
    PAIR_K_ACE,
    PAIR_K_BARE,
    PAIR_K_JOKER,
    PAIR_Q_ACE,
    PAIR_Q_BARE,
    PAIR_Q_JOKER,
    RAISE_INVEST,
    RAISE_POT,
    RATE_R84,
    RATE_R86,
    generate_bn_vs_chart_co_deals,
    is_co_chart_open,
    pair_opens_under_policy,
    sample_chart_co_ids,
    spec_for,
)
from fivecarddraw.validation.button_vs_cutoff_tight import (
    ev_call_net,
    ev_raise_checkdown,
    recommend_action,
)
from fivecarddraw.validation.cutoff_open_chart import (
    POLICY_ACE_OR_JOKER,
    POLICY_JOKER_ONLY,
    POLICY_OPEN_ALWAYS,
)
from fivecarddraw.validation.cutoff_open_sandbag import has_physical_ace
from fivecarddraw.validation.postdraw_nonbluff_ev import LOCKED_BN_DRAW
from fivecarddraw.validation.showdown_matrix import classify_opener


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "validation"
FIXTURE_R84 = FIXTURE_DIR / "button_vs_cutoff_r84.json"
FIXTURE_R86 = FIXTURE_DIR / "button_vs_cutoff_r86.json"


def _ids(cards) -> tuple[int, ...]:
    return tuple(sorted(c.card_id for c in cards))


def test_owned_rates_only():
    assert spec_for(84) is RATE_R84
    assert spec_for(86) is RATE_R86
    assert RATE_R84.jj == POLICY_ACE_OR_JOKER
    assert RATE_R84.qq == POLICY_ACE_OR_JOKER
    assert RATE_R84.kk == POLICY_OPEN_ALWAYS
    assert RATE_R86.jj == POLICY_JOKER_ONLY
    assert RATE_R86.qq == POLICY_ACE_OR_JOKER
    assert RATE_R86.kk == POLICY_OPEN_ALWAYS
    assert RATE_R84.seed == DEFAULT_SEED_R84
    assert RATE_R86.seed == DEFAULT_SEED_R86
    assert DEFAULT_N_HU == 4000


def test_bug_is_ace_kicker_not_trips():
    for hand, cls, pair_rank in (
        (PAIR_J_JOKER, "pair_J", 11),
        (PAIR_Q_JOKER, "pair_Q", 12),
        (PAIR_K_JOKER, "pair_K", 13),
    ):
        assert classify_opener(hand) == cls
        assert evaluate_hand(hand).category == HandCategory.ONE_PAIR
        assert evaluate_hand(hand).tiebreak[0] == pair_rank


def test_r84_co_range_predicate():
    spec = RATE_R84
    aa = parse_hand("As Ad 9c 8h 2d")
    tp = parse_hand("Ks Kd 9c 9h 2d")
    aces_up = parse_hand("As Ad 9c 9h 2d")
    trips = parse_hand("7s 7d 7h 9c 2d")
    junk = parse_hand("9s 8h 7c 5d 2s")
    assert is_co_chart_open(classify_opener(aa), _ids(aa), spec) is True
    assert is_co_chart_open(classify_opener(tp), _ids(tp), spec) is True
    assert is_co_chart_open(classify_opener(aces_up), _ids(aces_up), spec) is True
    assert is_co_chart_open(classify_opener(trips), _ids(trips), spec) is True
    # JJ: ace or joker
    assert is_co_chart_open(classify_opener(PAIR_J_JOKER), _ids(PAIR_J_JOKER), spec) is True
    assert is_co_chart_open(classify_opener(PAIR_J_ACE), _ids(PAIR_J_ACE), spec) is True
    assert is_co_chart_open(classify_opener(PAIR_J_BARE), _ids(PAIR_J_BARE), spec) is False
    # QQ: ace or joker
    assert is_co_chart_open(classify_opener(PAIR_Q_JOKER), _ids(PAIR_Q_JOKER), spec) is True
    assert is_co_chart_open(classify_opener(PAIR_Q_ACE), _ids(PAIR_Q_ACE), spec) is True
    assert is_co_chart_open(classify_opener(PAIR_Q_BARE), _ids(PAIR_Q_BARE), spec) is False
    # KK: class average — all flavors
    assert is_co_chart_open(classify_opener(PAIR_K_JOKER), _ids(PAIR_K_JOKER), spec) is True
    assert is_co_chart_open(classify_opener(PAIR_K_ACE), _ids(PAIR_K_ACE), spec) is True
    assert is_co_chart_open(classify_opener(PAIR_K_BARE), _ids(PAIR_K_BARE), spec) is True
    assert is_co_chart_open(classify_opener(junk), _ids(junk), spec) is False
    assert is_co_chart_open(None, _ids(junk), spec) is False


def test_r86_co_range_predicate():
    spec = RATE_R86
    # JJ: joker only (ace kicker is out)
    assert is_co_chart_open(classify_opener(PAIR_J_JOKER), _ids(PAIR_J_JOKER), spec) is True
    assert is_co_chart_open(classify_opener(PAIR_J_ACE), _ids(PAIR_J_ACE), spec) is False
    assert is_co_chart_open(classify_opener(PAIR_J_BARE), _ids(PAIR_J_BARE), spec) is False
    # QQ still ace or joker; KK still all
    assert is_co_chart_open(classify_opener(PAIR_Q_JOKER), _ids(PAIR_Q_JOKER), spec) is True
    assert is_co_chart_open(classify_opener(PAIR_Q_ACE), _ids(PAIR_Q_ACE), spec) is True
    assert is_co_chart_open(classify_opener(PAIR_Q_BARE), _ids(PAIR_Q_BARE), spec) is False
    assert is_co_chart_open(classify_opener(PAIR_K_BARE), _ids(PAIR_K_BARE), spec) is True
    aa = parse_hand("As Ad 9c 8h 2d")
    assert is_co_chart_open(classify_opener(aa), _ids(aa), spec) is True


def test_pair_policy_helpers():
    assert pair_opens_under_policy(_ids(PAIR_J_BARE), POLICY_OPEN_ALWAYS) is True
    assert pair_opens_under_policy(_ids(PAIR_J_BARE), POLICY_ACE_OR_JOKER) is False
    assert pair_opens_under_policy(_ids(PAIR_J_ACE), POLICY_ACE_OR_JOKER) is True
    assert pair_opens_under_policy(_ids(PAIR_J_JOKER), POLICY_ACE_OR_JOKER) is True
    assert pair_opens_under_policy(_ids(PAIR_J_ACE), POLICY_JOKER_ONLY) is False
    assert pair_opens_under_policy(_ids(PAIR_J_JOKER), POLICY_JOKER_ONLY) is True


def test_accounting_pins():
    assert FOLD_EV == 0.0
    assert CALL_INVEST == 2.0
    assert RAISE_INVEST == 4.0
    assert RAISE_POT == 10.0
    assert ev_call_net(6.0) == 4.0
    assert ev_raise_checkdown(p_bn_win=1.0, p_tie=0.0) == 6.0
    assert ev_raise_checkdown(p_bn_win=0.0, p_tie=0.0) == -4.0
    fold = recommend_action(ev_call=-0.40, ev_raise=-1.10, p_bn_win=0.20)
    assert fold["action"] == "fold"
    raise_ = recommend_action(ev_call=4.0, ev_raise=3.0, p_bn_win=0.70)
    assert raise_["action"] == "raise"


def test_samplers_respect_range():
    rng = random.Random(20260909)
    for spec in (RATE_R84, RATE_R86):
        for _ in range(40):
            sampled = sample_chart_co_ids(rng, spec, blocked=set())
            assert sampled is not None
            ids, cls = sampled
            assert is_co_chart_open(cls, ids, spec)
            if cls == "pair_J":
                if spec is RATE_R86:
                    assert BUG_ID in ids
                else:
                    assert BUG_ID in ids or has_physical_ace(ids)
            if cls == "pair_Q":
                assert BUG_ID in ids or has_physical_ace(ids)
            if cls == "pair_K":
                pass  # all KK


def test_hu_generator_locked_draws():
    deals = generate_bn_vs_chart_co_deals(
        "pair_J", RATE_R84, n_deals=8, seed=3
    )
    assert len(deals) == 8
    assert all(d.caller_class == "pair_J" for d in deals)
    assert all(d.caller_d == LOCKED_BN_DRAW.pair_d for d in deals)
    assert all(d.d in (0, 1, 2, 3) for d in deals)
    deals86 = generate_bn_vs_chart_co_deals(
        "pair_A", RATE_R86, n_deals=8, seed=5
    )
    assert len(deals86) == 8
    assert all(d.caller_class == "pair_A" for d in deals86)
    assert all(d.caller_d == LOCKED_BN_DRAW.pair_d for d in deals86)


def _load(path: Path) -> dict:
    assert path.exists(), (
        "run python -m fivecarddraw.validation.button_vs_cutoff_r84_r86 "
        "--rate {84|86} --n-hu 4000 --write-fixture"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_common_fixture(data: dict, *, rate_pct: int, seed: int, frame: str) -> dict:
    meta = data["meta"]
    assert meta["frame"] == frame
    assert meta["rate_pct"] == rate_pct
    assert meta["seed"] == seed
    assert meta["n_hu"] == 4000
    assert meta["accounting"]["fold"] == 0.0
    assert meta["locked_draws"]["pair_d"] == 3
    assert meta["locked_draws"]["two_pair_d"] == 1
    assert meta["co_range"]["kk"] == POLICY_OPEN_ALWAYS
    answers = data["answers"]
    assert answers["jj_action"] == "fold"
    assert answers["qq_action"] == "fold"
    assert answers["kk_action"] == "fold"
    # Inflection vs all-legal polar (AA raise): both interior rows fold AA.
    assert answers["aa_action"] == "fold"
    assert answers["aa_ev_call"] < 0.0
    assert answers["aa_p_win"] < 0.5
    assert answers["aa_raise_plus_ev_vs_fold"] is True
    assert answers["aa_ev_raise_checkdown"] > 0.0
    assert answers["two_pair_action"] == "raise"
    assert answers["aces_up_action"] == "raise"
    assert answers["trips_action"] == "raise"
    assert answers["trips_A_action"] == "raise"
    assert answers["flavor_action_flips"] == []
    by = {r["key"]: r for r in data["by_row"]}
    for key in ("pair_J", "pair_Q", "pair_K", "pair_A"):
        row = by[key]
        assert row["recommend"]["action"] == "fold"
        assert row["ev_call"] < 0.0
        assert row["n"] == 4000.0
        assert row["se_call"] > 0.0
        assert row["p_bn_wins_final"] < 0.5
    aa = by["pair_A"]
    assert aa["recommend"]["value_raise"] is False
    assert aa["recommend"]["raise_plus_ev_vs_fold"] is True
    two_pair = by["two_pair"]
    assert two_pair["ev_call"] > 0.0
    assert two_pair["recommend"]["action"] == "raise"
    assert two_pair["recommend"]["value_raise"] is True
    trips = by["trips"]
    assert trips["p_bn_wins_final"] > 0.5
    assert trips["recommend"]["action"] == "raise"
    for key in ("pair_J_joker", "pair_J_ace", "pair_Q_joker", "pair_K_joker"):
        assert by[key]["recommend"]["action"] == "fold"
        assert by[key]["ev_call"] < 0.0
    return by


def test_fixture_r84_product():
    data = _load(FIXTURE_R84)
    by = _assert_common_fixture(
        data, rate_pct=84, seed=DEFAULT_SEED_R84, frame="button_vs_cutoff_r84"
    )
    meta = data["meta"]
    assert meta["co_range"]["jj"] == POLICY_ACE_OR_JOKER
    assert meta["co_range"]["qq"] == POLICY_ACE_OR_JOKER
    # Bare JJ/QQ are out; JJ+ace is in; all KK (including bare) is in.
    jj = by["pair_J"]
    assert jj["co_mix"]["pair_J_bare"] == 0.0
    assert jj["co_mix"]["pair_Q_bare"] == 0.0
    assert jj["co_mix"]["pair_J_ace"] > 0.0
    assert jj["co_mix"]["pair_K_bare"] > 0.05
    aa = by["pair_A"]
    assert aa["ev_call"] == -0.44525
    assert aa["ev_raise_checkdown"] == 0.54625
    assert aa["p_bn_wins_final"] == 0.4545
    assert aa["se_call"] > 0.0
    assert aa["se_raise_checkdown"] > 0.0


def test_fixture_r86_product():
    data = _load(FIXTURE_R86)
    by = _assert_common_fixture(
        data, rate_pct=86, seed=DEFAULT_SEED_R86, frame="button_vs_cutoff_r86"
    )
    meta = data["meta"]
    assert meta["co_range"]["jj"] == POLICY_JOKER_ONLY
    assert meta["co_range"]["qq"] == POLICY_ACE_OR_JOKER
    # JJ ace/bare are out of CO's range at 86%; joker JJ and all KK remain.
    for row in by.values():
        assert row["co_mix"]["pair_J_ace"] == 0.0
        assert row["co_mix"]["pair_J_bare"] == 0.0
        assert row["co_mix"]["pair_Q_bare"] == 0.0
    jj = by["pair_J"]
    assert jj["co_mix"]["pair_J_joker"] > 0.0
    assert jj["co_mix"]["pair_K_bare"] > 0.05
    aa = by["pair_A"]
    assert aa["ev_call"] == -0.70725
    assert aa["ev_raise_checkdown"] == 0.28125
    assert aa["p_bn_wins_final"] == 0.428
    # AA is a worse dog than at 84% (JJ+ace dropped).
    r84 = _load(FIXTURE_R84)
    aa84 = next(r for r in r84["by_row"] if r["key"] == "pair_A")
    assert aa["p_bn_wins_final"] < aa84["p_bn_wins_final"]
    assert aa["ev_call"] < aa84["ev_call"]
