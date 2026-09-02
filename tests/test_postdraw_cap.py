"""Post-draw cap (bet + 3 raises): pot math, 3-bet vs call, fixture pins."""

from __future__ import annotations

import json
from pathlib import Path

from fivecarddraw.hand_rank import HandCategory, HandValue
from fivecarddraw.rules import DEFAULT_CONFIG
from fivecarddraw.validation.postdraw_betting_m2 import (
    BIG,
    CAP_POT,
    CALL_IT_DOWN,
    PREDRAW_POT,
    CapPolicy,
    Deal,
    play_deal,
    play_raise_node,
    street_after_bet_and_raise,
)
from fivecarddraw.validation.postdraw_cap import (
    family_bucket,
    fine_bucket,
    on_raise_node,
)
from fivecarddraw.validation.postdraw_nonbluff_ev import (
    CALLER_ALL,
    HONEST_POLICY,
    NonbluffDeal,
    caller_ev_from_bn,
)


FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "validation"
    / "postdraw_cap_summary.json"
)


def _hv(cat: int, *tb: int) -> HandValue:
    return HandValue(category=cat, tiebreak=tuple(tb))


def _deal(
    *,
    cls: str = "flush",
    d: int = 0,
    o_final: HandValue | None = None,
    d_final: HandValue | None = None,
    o_strong: bool = True,
    d_sp: bool = True,
) -> Deal:
    if o_final is None:
        o_final = _hv(HandCategory.FLUSH, 14, 13, 9, 6, 3)
    if d_final is None:
        d_final = _hv(HandCategory.STRAIGHT, 7)
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


def test_street_state_full_cap_pot_is_38():
    """Four $4 bets each: $6 + $32 = $38. Pin against StreetState."""
    st = street_after_bet_and_raise(max_raises=3)
    assert st.pot == 18.0
    assert st.amount_to_call == BIG
    assert st.can_raise
    st = st.after_raise()  # BN 3-bet
    assert st.pot == 26.0
    st = st.after_raise()  # caller cap
    assert st.pot == 34.0
    assert not st.can_raise
    st = st.after_call()
    assert st.pot == CAP_POT == 38.0
    assert PREDRAW_POT + 8 * BIG == 38.0
    assert DEFAULT_CONFIG.max_raises == 3


def test_max_raises_1_cannot_three_bet():
    st = street_after_bet_and_raise(max_raises=1)
    assert st.pot == 18.0
    assert not st.can_raise


def test_call_it_down_matches_m2_raise_call():
    """max_raises=1 play_deal equals play_raise_node(call) on a raise node."""
    deal = _deal(
        o_final=_hv(HandCategory.TWO_PAIR, 14, 9, 2),
        d_final=_hv(HandCategory.STRAIGHT, 14),
    )
    ev_m2, flags_m2 = play_deal(deal, HONEST_POLICY, max_raises=1)
    ev_node, flags_node = play_raise_node(deal, bn_vs_raise="call", max_raises=3)
    assert flags_m2["drawer_raise"]
    assert flags_m2["opener_call_raise"]
    assert not flags_m2["opener_3bet"]
    assert ev_m2 == ev_node
    # BN two pair loses to broadway straight: invested $8, lost.
    assert ev_m2 == -8.0
    assert flags_node["showdown"]
    assert abs(ev_m2 + caller_ev_from_bn(ev_m2) - PREDRAW_POT) < 1e-9


def test_max_raises_3_without_cap_policy_still_calls():
    deal = _deal(
        o_final=_hv(HandCategory.FLUSH, 14, 12, 9, 8, 3),
        d_final=_hv(HandCategory.STRAIGHT, 7),
    )
    ev1, f1 = play_deal(deal, HONEST_POLICY, max_raises=1)
    ev3, f3 = play_deal(
        deal, HONEST_POLICY, max_raises=3, cap_policy=CALL_IT_DOWN
    )
    assert ev1 == ev3 == 14.0  # win $22, invested $8
    assert not f1["opener_3bet"] and not f3["opener_3bet"]


def test_nut_bn_three_bet_vs_straight_caller_delta():
    """Five aces vs a straight: 3-bet (caller calls, no cap) is +$4 vs call."""
    deal = _deal(
        cls="five_aces",
        o_final=_hv(HandCategory.FIVE_ACES, 14),
        d_final=_hv(HandCategory.STRAIGHT, 7),
    )
    ev_call, f_call = play_raise_node(deal, bn_vs_raise="call")
    ev_3, f_3 = play_raise_node(
        deal, bn_vs_raise="three_bet", caller_vs_3bet="call"
    )
    ev_cap, f_cap = play_raise_node(
        deal, bn_vs_raise="three_bet", caller_vs_3bet="cap", bn_vs_cap="call"
    )
    assert f_call["opener_call_raise"]
    assert f_3["opener_3bet"] and f_3["drawer_call_3bet"]
    assert f_cap["drawer_cap"] and f_cap["opener_call_cap"]
    assert ev_call == 14.0  # -8 + 22
    assert ev_3 == 18.0  # -12 + 30
    assert ev_cap == 22.0  # -16 + 38
    assert ev_3 - ev_call == BIG
    assert ev_cap - ev_call == 2 * BIG
    for ev in (ev_call, ev_3, ev_cap):
        assert abs(ev + caller_ev_from_bn(ev) - PREDRAW_POT) < 1e-9


def test_thin_straight_should_not_three_bet_into_flush():
    """Wheel straight vs ace-high flush: 3-bet costs an extra bet when behind."""
    deal = _deal(
        cls="straight",
        o_final=_hv(HandCategory.STRAIGHT, 5),
        d_final=_hv(HandCategory.FLUSH, 14, 12, 9, 8, 3),
    )
    ev_call, _ = play_raise_node(deal, bn_vs_raise="call")
    ev_3, _ = play_raise_node(
        deal, bn_vs_raise="three_bet", caller_vs_3bet="call"
    )
    assert ev_call == -8.0
    assert ev_3 == -12.0
    assert ev_3 - ev_call == -BIG


def test_play_deal_flush_three_bets_when_policy_says_so():
    deal = _deal(
        o_final=_hv(HandCategory.FLUSH, 12, 11, 9, 6, 3),
        d_final=_hv(HandCategory.STRAIGHT, 9),
    )
    pol = CapPolicy(
        opener_3bet_min=HandCategory.FLUSH,
        drawer_cap_min=HandCategory.STRAIGHT_FLUSH,
        drawer_call_3bet_min=HandCategory.STRAIGHT,
    )
    ev, flags = play_deal(deal, HONEST_POLICY, max_raises=3, cap_policy=pol)
    assert flags["opener_3bet"]
    assert flags["drawer_call_3bet"]
    assert not flags["drawer_cap"]
    assert ev == 18.0


def test_sf_caps_flush_calls():
    sf = _deal(
        o_final=_hv(HandCategory.FULL_HOUSE, 14, 13),
        d_final=_hv(HandCategory.STRAIGHT_FLUSH, 14),
    )
    pol = CapPolicy(
        opener_3bet_min=HandCategory.FULL_HOUSE,
        drawer_cap_min=HandCategory.STRAIGHT_FLUSH,
    )
    ev, flags = play_deal(sf, HONEST_POLICY, max_raises=3, cap_policy=pol)
    assert flags["opener_3bet"]
    assert flags["drawer_cap"]
    assert flags["opener_call_cap"]
    # Boat loses to SF at the $38 pot: BN invested $16.
    assert ev == -16.0


def test_fine_and_family_buckets():
    assert fine_bucket(_hv(HandCategory.STRAIGHT, 14)) == "straight_A"
    assert fine_bucket(_hv(HandCategory.STRAIGHT, 5)) == "straight_5"
    assert fine_bucket(_hv(HandCategory.FLUSH, 12, 9, 8, 4, 2)) == "flush_Q"
    assert fine_bucket(_hv(HandCategory.FLUSH, 10, 9, 8, 4, 2)) == "flush_low"
    assert family_bucket(_hv(HandCategory.TWO_PAIR, 13, 9, 2)) == "two_pair_or_trips"
    assert family_bucket(_hv(HandCategory.FULL_HOUSE, 9, 8)) == "boat_plus"


def test_on_raise_node():
    node = NonbluffDeal(
        opener_class="two_pair",
        caller_class=CALLER_ALL,
        d=1,
        caller_d=1,
        opener_start_pair=None,
        opener_final=_hv(HandCategory.TWO_PAIR, 14, 9, 2),
        drawer_final=_hv(HandCategory.STRAIGHT, 7),
        opener_final_pair=None,
        drawer_final_pair=None,
        drawer_straight_plus=True,
        opener_two_pair_plus=True,
    )
    assert on_raise_node(node)
    miss = NonbluffDeal(
        opener_class="pair_A",
        caller_class=CALLER_ALL,
        d=3,
        caller_d=1,
        opener_start_pair=14,
        opener_final=_hv(HandCategory.ONE_PAIR, 14, 9, 8, 2),
        drawer_final=_hv(HandCategory.STRAIGHT, 7),
        opener_final_pair=14,
        drawer_final_pair=None,
        drawer_straight_plus=True,
        opener_two_pair_plus=False,
    )
    assert not on_raise_node(miss)


def test_fixture_summary_patterns():
    assert FIXTURE.exists(), "run analyze-postdraw-cap --write-fixture"
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    meta = data["meta"]
    assert meta["max_raises_this_module"] == 3
    assert meta["max_raises_default_m2"] == 1
    assert meta["cap_pot"] == 38.0
    assert meta["predraw_pot"] == 6.0
    assert meta["n_range"] >= 10_000
    f = data["findings"]
    assert f["nonbluff_grid_excludes_cap"] is True
    # Coarse pins from the handoff hypotheses (numbers from the fixture run).
    assert f["hypothesis_straight_calls"] is True
    assert f["hypothesis_flush_3bets"] is True
    assert f["hypothesis_boat_3bets"] is True
    assert f["hypothesis_two_pair_trips_call"] is True
    assert f["bn_straight_delta"] < 0.0
    assert f["bn_flush_delta"] > 0.0
    assert f["bn_boat_plus_delta"] > 0.0
    assert f["caller_should_not_cap_non_sf_vs_boat"] is True
    by_fam = {r["bucket"]: r for r in data["bn_family"]}
    assert by_fam["straight"]["recommend"] == "call"
    assert by_fam["flush"]["recommend"] == "three_bet"
    assert by_fam["boat_plus"]["recommend"] == "three_bet"
    assert by_fam["two_pair_or_trips"]["recommend"] == "call"
    assert by_fam["two_pair_or_trips"].get("bluff_3bet_out_of_scope") is True
    assert f["p_raise_node_locked_range"] == 0.189
    assert f["n_node_weighted"] == 7559
    assert f["bn_straight_delta"] == -1.8144
    assert f["bn_flush_delta"] == 2.1672
    assert f["bn_boat_plus_delta"] == 3.4659
    assert f["call_it_down_ev_bn"] == -5.3239
    by_fine = {r["bucket"]: r for r in data["bn_fine"]}
    assert by_fine["straight_A"]["recommend"] == "three_bet"
    assert by_fine["straight_5"]["recommend"] == "call"
    assert by_fine["flush_Q"]["recommend"] == "three_bet"
    assert by_fine["flush_A"]["recommend"] == "three_bet"
