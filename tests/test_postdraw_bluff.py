"""Ring 1 post-draw bluff 3-bet: pot odds, steal EV, indifference, fixture pins."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from fivecarddraw.hand_rank import HandCategory, HandValue
from fivecarddraw.rules import pot_odds_to_call as rules_pot_odds
from fivecarddraw.validation import bluff_indifference as bluff_mod
from fivecarddraw.validation.bluff_indifference import (
    AIR_SHARE_OF_THREE_BETS,
    BEST_RESPONSE,
    BLUFF_TWO_PAIR_TRIPS,
    BN_POLAR_MIX,
    CALL_3BET,
    CATCHER_FLUSH,
    COMPUTE_STRATEGY_EV,
    FOLD_RAISE_EV_BN,
    INDIFFERENCE_ROOT,
    POT_AFTER_3BET,
    POT_ODDS_CALL_3BET,
    POT_ODDS_TO_CALL,
    PRECOMPUTE_RAISE_NODE_PAYOFFS,
    RING1_CALLER_FOLD_CATCHERS,
    VALUE_BOAT_PLUS,
    VALUE_FLUSH_PLUS,
)
from fivecarddraw.validation.postdraw_betting_m2 import (
    CAP_POT,
    PREDRAW_POT,
    Deal,
    play_deal,
    play_raise_node,
    street_after_bet_and_raise,
)
from fivecarddraw.validation.postdraw_cap import family_bucket, on_raise_node
from fivecarddraw.validation.postdraw_nonbluff_ev import (
    HONEST_POLICY,
    caller_ev_from_bn,
)


FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "validation"
    / "postdraw_bluff_summary.json"
)


def _hv(cat: int, *tb: int) -> HandValue:
    return HandValue(category=cat, tiebreak=tuple(tb))


def _deal(
    *,
    cls: str = "two_pair",
    d: int = 1,
    o_final: HandValue | None = None,
    d_final: HandValue | None = None,
    o_strong: bool = True,
    d_sp: bool = True,
) -> Deal:
    if o_final is None:
        o_final = _hv(HandCategory.TWO_PAIR, 14, 9, 2)
    if d_final is None:
        d_final = _hv(HandCategory.FLUSH, 14, 13, 9, 6, 3)
    return Deal(
        opener_class=cls,
        opener_start_pair=None,
        d=d,
        opener_final=o_final,
        drawer_final=d_final,
        opener_final_pair=None,
        drawer_final_pair=None,
        drawer_straight_plus=d_sp,
        opener_two_pair_plus=o_strong,
    )


def test_pot_odds_to_call_4_over_30():
    """After BN 3-bet: pot $26, $4 to call. Break-even 4/30."""
    assert POT_AFTER_3BET == 26.0
    assert CALL_3BET == 4.0
    assert POT_ODDS_TO_CALL(26, 4) == 4 / 30
    assert POT_ODDS_CALL_3BET == 4 / 30
    assert POT_ODDS_TO_CALL is rules_pot_odds
    assert bluff_mod.__all__ == [
        "AIR_SHARE_OF_THREE_BETS",
        "BEST_RESPONSE",
        "BIG",
        "BISECT_ROOT",
        "BLUFF_TWO_PAIR_TRIPS",
        "BN_POLAR_MIX",
        "CALL_3BET",
        "CALLER_EVS",
        "CALLER_MIX",
        "CATCHER_EVS",
        "CATCHER_FLUSH",
        "COMPUTE_STRATEGY_EV",
        "FOLD_RAISE_EV_BN",
        "INDIFFERENCE_RESULT",
        "INDIFFERENCE_ROOT",
        "NODE_PAYOFF",
        "POT_AFTER_3BET",
        "POT_ODDS_CALL_3BET",
        "POT_ODDS_TO_CALL",
        "PRECOMPUTE_RAISE_NODE_PAYOFFS",
        "RING1_CALLER_CALL_FLUSH",
        "RING1_CALLER_FOLD_CATCHERS",
        "STRATEGY_EV",
        "VALUE_BOAT_PLUS",
        "VALUE_FLUSH_PLUS",
    ]
    assert all(name.isupper() for name in bluff_mod.__all__)
    st = street_after_bet_and_raise(max_raises=3).after_raise()
    assert st.pot == POT_AFTER_3BET
    assert st.amount_to_call == CALL_3BET


def test_steal_ev_when_caller_folds():
    """Bluff 3-bet that gets a fold: EV_bn +14 / EV_caller −8."""
    deal = _deal(
        o_final=_hv(HandCategory.TWO_PAIR, 14, 9, 2),
        d_final=_hv(HandCategory.STRAIGHT, 7),
    )
    ev, flags = play_raise_node(
        deal, bn_vs_raise="three_bet", caller_vs_3bet="fold"
    )
    assert flags["opener_3bet"]
    assert flags["drawer_fold_to_3bet"]
    assert ev == 14.0
    assert caller_ev_from_bn(ev) == -8.0
    assert abs(ev + caller_ev_from_bn(ev) - PREDRAW_POT) < 1e-9


def test_fold_raise_is_minus_four_not_call():
    """Two pair vs a straight+ raise: fold −4, call −8 (drawing dead)."""
    deal = _deal(
        o_final=_hv(HandCategory.TWO_PAIR, 14, 9, 2),
        d_final=_hv(HandCategory.STRAIGHT, 7),
    )
    ev_fold, flags = play_raise_node(deal, bn_vs_raise="fold")
    ev_call, _ = play_raise_node(deal, bn_vs_raise="call")
    assert flags["opener_fold_to_raise"]
    assert ev_fold == FOLD_RAISE_EV_BN == -4.0
    assert ev_call == -8.0
    pay = PRECOMPUTE_RAISE_NODE_PAYOFFS([deal])
    assert pay[0].ev_bn_fold_raise == -4.0
    mix_fold = BN_POLAR_MIX(beta=0.0)  # leftover fold for two pair/trips
    mix_call = BN_POLAR_MIX(
        beta=0.0, value_buckets=frozenset(), bluff_buckets=frozenset()
    )
    assert mix_fold.leftover_vs_raise("two_pair_or_trips") == "fold"
    assert mix_call.leftover_vs_raise("two_pair_or_trips") == "call"
    ev0 = COMPUTE_STRATEGY_EV([deal], mix_fold, RING1_CALLER_FOLD_CATCHERS, payoffs=pay)
    ev_cid = COMPUTE_STRATEGY_EV(
        [deal], mix_call, RING1_CALLER_FOLD_CATCHERS, payoffs=pay
    )
    assert abs(ev0.ev_bn - (-4.0)) < 1e-9
    assert abs(ev_cid.ev_bn - (-8.0)) < 1e-9
    mix_half = BN_POLAR_MIX(beta=0.5)
    evh = COMPUTE_STRATEGY_EV(
        [deal], mix_half, RING1_CALLER_FOLD_CATCHERS, payoffs=pay
    )
    # (1−β)·(−4) + β·(+14) = 5
    assert abs(evh.ev_bn - 5.0) < 1e-9
    br = BEST_RESPONSE([deal], RING1_CALLER_FOLD_CATCHERS, payoffs=pay)
    by = {r["bucket"]: r for r in br["rows"]}
    assert by["two_pair_or_trips"]["ev_bn_fold_raise"] == -4.0
    assert by["two_pair_or_trips"]["ev_bn_call"] == -8.0
    assert by["two_pair_or_trips"]["recommend"] == "three_bet"


def test_play_deal_default_stays_max_raises_1():
    """M2 / non-bluff path does not grow a 3-bet just because cap exists."""
    sig = inspect.signature(play_deal)
    assert sig.parameters["max_raises"].default == 1
    deal = _deal(
        o_final=_hv(HandCategory.FLUSH, 14, 12, 9, 8, 3),
        d_final=_hv(HandCategory.STRAIGHT, 7),
    )
    ev, flags = play_deal(deal, HONEST_POLICY)
    assert not flags["opener_3bet"]
    assert ev == 14.0


def test_synthetic_polar_indifference_alpha_is_pot_odds():
    """Catcher drawing dead to value and always beating air → α* = 4/30.

    One boat vs flush (value) and nine two pair vs flush (air). Algebra:
    (−12 + 18·9β) / (1 + 9β) = −8  ⇒  β = 4/234,  α = 9β/(1+9β) = 4/30.
    """
    value = _deal(
        cls="full_house",
        o_final=_hv(HandCategory.FULL_HOUSE, 14, 13),
        d_final=_hv(HandCategory.FLUSH, 12, 11, 9, 6, 3),
    )
    air = _deal(
        cls="two_pair",
        o_final=_hv(HandCategory.TWO_PAIR, 14, 9, 2),
        d_final=_hv(HandCategory.FLUSH, 12, 11, 9, 6, 3),
    )
    assert family_bucket(value.opener_final) == "boat_plus"
    assert family_bucket(air.opener_final) == "two_pair_or_trips"
    assert family_bucket(air.drawer_final) == CATCHER_FLUSH
    deals = [value] + [air] * 9
    pay = PRECOMPUTE_RAISE_NODE_PAYOFFS(deals)
    result = INDIFFERENCE_ROOT(
        deals,
        value_buckets=VALUE_BOAT_PLUS,
        bluff_buckets=BLUFF_TWO_PAIR_TRIPS,
        catcher_bucket=CATCHER_FLUSH,
        payoffs=pay,
    )
    assert result.bracketed
    assert 0.0 < result.beta < 1.0
    assert abs(result.alpha - 4 / 30) < 1e-6
    assert abs(result.catcher.call_minus_fold) < 1e-6
    assert abs(result.catcher.ev_fold - (-8.0)) < 1e-9
    assert abs(result.beta - 4 / 234) < 1e-6
    alpha, n_v, n_b, n_3 = AIR_SHARE_OF_THREE_BETS(
        pay,
        BN_POLAR_MIX(
            beta=result.beta,
            value_buckets=VALUE_BOAT_PLUS,
            bluff_buckets=BLUFF_TWO_PAIR_TRIPS,
        ),
    )
    assert n_v == 1.0 and n_b == 9.0
    assert abs(alpha - result.alpha) < 1e-12
    assert abs(n_3 - (1.0 + 9.0 * result.beta)) < 1e-12


def test_strategy_ev_convex_combo_and_best_response():
    flush_bn = _deal(
        cls="flush",
        o_final=_hv(HandCategory.FLUSH, 14, 13, 9, 6, 3),
        d_final=_hv(HandCategory.STRAIGHT, 7),
    )
    trips = _deal(
        cls="trips",
        o_final=_hv(HandCategory.THREE_OF_A_KIND, 14, 9, 2),
        d_final=_hv(HandCategory.STRAIGHT, 7),
    )
    deals = [flush_bn, trips]
    pay = PRECOMPUTE_RAISE_NODE_PAYOFFS(deals)
    mix0 = BN_POLAR_MIX(beta=0.0, value_buckets=VALUE_FLUSH_PLUS)
    mix1 = BN_POLAR_MIX(beta=1.0, value_buckets=VALUE_FLUSH_PLUS)
    mixh = BN_POLAR_MIX(beta=0.5, value_buckets=VALUE_FLUSH_PLUS)
    ev0 = COMPUTE_STRATEGY_EV(deals, mix0, RING1_CALLER_FOLD_CATCHERS, payoffs=pay)
    ev1 = COMPUTE_STRATEGY_EV(deals, mix1, RING1_CALLER_FOLD_CATCHERS, payoffs=pay)
    evh = COMPUTE_STRATEGY_EV(deals, mixh, RING1_CALLER_FOLD_CATCHERS, payoffs=pay)
    assert abs(evh.ev_bn - 0.5 * (ev0.ev_bn + ev1.ev_bn)) < 1e-9
    # No air: straight is drawing dead to a flush+ 3-bet.
    br = BEST_RESPONSE(deals, mix0, payoffs=pay)
    by = {r["bucket"]: r for r in br["rows"]}
    assert by["straight"]["recommend"] == "fold"


def test_on_raise_node_reused():
    node = _deal(
        o_final=_hv(HandCategory.TWO_PAIR, 13, 9, 2),
        d_final=_hv(HandCategory.STRAIGHT, 10),
        o_strong=True,
        d_sp=True,
    )
    assert on_raise_node(node)
    miss = _deal(
        cls="pair_A",
        o_final=_hv(HandCategory.ONE_PAIR, 14, 9, 8, 2),
        d_final=_hv(HandCategory.STRAIGHT, 10),
        o_strong=False,
        d_sp=True,
    )
    assert not on_raise_node(miss)


def test_full_cap_pot_still_38():
    assert CAP_POT == 38.0
    assert PREDRAW_POT + 8 * 4.0 == 38.0


def test_fixture_ring1_patterns():
    assert FIXTURE.exists(), "run analyze-postdraw-bluff --write-fixture"
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    meta = data["meta"]
    assert meta["ring"] == 1
    assert meta["max_raises_this_module"] == 3
    assert meta["max_raises_default_m2"] == 1
    assert meta["pot_after_3bet"] == 26.0
    assert meta["to_call_3bet"] == 4.0
    assert abs(meta["pot_odds_call_3bet"] - 4 / 30) < 5e-5
    assert meta["n_range"] >= 10_000
    assert meta["n_node_weighted"] == 7559
    assert meta["value_3bet"] == "flush+"
    assert meta["bn_straights"] == "always call (not mixed)"
    assert meta["bn_leftover_two_pair_trips"] == "fold"
    f = data["findings"]
    assert f["nonbluff_grid_excludes_bluff_3bet"] is True
    assert f["cap_table_excludes_bluff_3bet"] is True
    assert f["alpha_not_pinned_to_sketch"] is True
    assert f["hypothesis_beta_in_unit_interval"] is True
    assert f["hypothesis_flush_indifferent"] is True
    assert abs(f["flush_call_minus_fold"]) <= 0.05
    assert f["hypothesis_straights_still_fold"] is True
    assert f["hypothesis_sf_still_caps"] is True
    assert f["hypothesis_bluff_delta_vs_no_air_positive"] is True
    assert f["hypothesis_bluff_delta_vs_call_it_down_positive"] is True
    assert f["hypothesis_boat_plus_value_needs_more_air"] is True
    assert f["leftover_two_pair_trips"] == "fold"
    assert f["beta_star"] == 0.0155
    assert f["alpha_star"] == 0.1016
    assert f["delta_vs_call_it_down"] == 3.4457
    assert f["delta_vs_no_air_flush_plus"] == 0.2072
    assert f["node_ev_bn_call_it_down"] == -5.3239
    assert f["node_ev_bn_at_beta_star"] == -1.8781
    assert f["boat_plus_only_alpha_star"] == 0.1528
    sketch = f["polar_sketch_alpha"]
    assert abs(sketch - (4 / 30 - 0.05) / 0.95) < 5e-5
    assert abs(f["alpha_star"] - sketch) > 0.005
    p = data["primary"]
    assert p["bracketed"] is True
    assert p["caller_flush"]["indifferent_call_fold"] is True
    assert p["caller_straight"]["still_folds"] is True
    assert p["caller_boat_plus"]["still_caps"] is True
    by_br = {r["bucket"]: r for r in p["caller_best_response"]}
    assert by_br["flush"]["recommend"] == "indifferent"
    assert by_br["straight"]["recommend"] == "fold"
    assert by_br["boat_plus"]["recommend"] == "cap"
