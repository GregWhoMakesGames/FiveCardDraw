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
    STAGE_C_POLICY,
    CapPolicy,
    Deal,
    bn_bets_stage_c,
    play_deal,
    play_raise_node,
    street_after_bet_and_raise,
)
from fivecarddraw.validation.postdraw_cap import (
    family_bucket,
    fine_bucket,
    on_raise_node,
    on_raise_node_pre_c,
    three_bet_lines_from_by_d,
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


def test_stage_c_policy_checks_two_pair_bets_trips():
    two_pair = _deal(
        cls="two_pair",
        d=1,
        o_final=_hv(HandCategory.TWO_PAIR, 14, 9, 2),
        d_final=_hv(HandCategory.STRAIGHT, 14),
        o_strong=True,
        d_sp=True,
    )
    trips = _deal(
        cls="trips",
        d=2,
        o_final=_hv(HandCategory.THREE_OF_A_KIND, 9, 8, 2),
        d_final=_hv(HandCategory.STRAIGHT, 14),
        o_strong=True,
        d_sp=True,
    )
    ev_tp, f_tp = play_deal(two_pair, STAGE_C_POLICY, max_raises=1)
    ev_tr, f_tr = play_deal(trips, STAGE_C_POLICY, max_raises=1)
    assert not f_tp.get("drawer_raise")
    assert f_tp.get("drawer_stab")  # caller leads the straight after BN checks
    assert f_tr["drawer_raise"]
    assert f_tr["opener_call_raise"]
    # Two pair calls the stab (still two pair+) and loses $4; trips call a raise and lose $8.
    assert ev_tp == -4.0
    assert ev_tr == -8.0


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
    assert family_bucket(_hv(HandCategory.TWO_PAIR, 13, 9, 2)) == "two_pair"
    assert family_bucket(_hv(HandCategory.THREE_OF_A_KIND, 13, 9, 2)) == "trips"
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
    assert not on_raise_node(node)
    assert on_raise_node_pre_c(node)
    assert not bn_bets_stage_c(node)
    trips = NonbluffDeal(
        opener_class="trips",
        caller_class=CALLER_ALL,
        d=2,
        caller_d=1,
        opener_start_pair=None,
        opener_final=_hv(HandCategory.THREE_OF_A_KIND, 9, 8, 2),
        drawer_final=_hv(HandCategory.STRAIGHT, 7),
        opener_final_pair=None,
        drawer_final_pair=None,
        drawer_straight_plus=True,
        opener_two_pair_plus=True,
    )
    assert on_raise_node(trips)
    assert bn_bets_stage_c(trips)
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


def test_three_bet_lines_from_by_d():
    """Line 1 = d=2∪d=3 (trips air); Line 2 = d=0 (flush calls vs flush+)."""
    by_d = {
        "d0": {
            "n": 10,
            "trips_air_n": 0,
            "two_pair_n": 0,
            "bn_family_n": {"flush": 6.0, "straight": 4.0},
            "caller_vs_bn_flush_plus": {
                "flush": {
                    "n": 4.0,
                    "recommend": "call",
                    "ev_caller_fold": -8.0,
                    "ev_caller_call": -7.0,
                    "ev_caller_cap": -10.0,
                }
            },
            "caller_vs_bn_boat_plus": {
                "flush": {
                    "n": 2.0,
                    "recommend": "fold",
                    "ev_caller_fold": -8.0,
                    "ev_caller_call": -12.0,
                    "ev_caller_cap": -16.0,
                }
            },
        },
        "d1": {
            "n": 3,
            "trips_air_n": 0,
            "two_pair_n": 0,
            "bn_family_n": {"boat_plus": 3.0},
            "caller_vs_bn_flush_plus": {
                "flush": {
                    "n": 2.0,
                    "recommend": "fold",
                    "ev_caller_fold": -8.0,
                    "ev_caller_call": -12.0,
                    "ev_caller_cap": -16.0,
                }
            },
            "caller_vs_bn_boat_plus": {
                "flush": {
                    "n": 2.0,
                    "recommend": "fold",
                    "ev_caller_fold": -8.0,
                    "ev_caller_call": -12.0,
                    "ev_caller_cap": -16.0,
                }
            },
        },
        "d2": {
            "n": 8,
            "trips_air_n": 7,
            "two_pair_n": 0,
            "bn_family_n": {"trips": 7.0, "boat_plus": 1.0},
            "caller_vs_bn_flush_plus": {
                "flush": {
                    "n": 3.0,
                    "recommend": "fold",
                    "ev_caller_fold": -8.0,
                    "ev_caller_call": -12.0,
                    "ev_caller_cap": -16.0,
                }
            },
            "caller_vs_bn_boat_plus": {
                "flush": {
                    "n": 3.0,
                    "recommend": "fold",
                    "ev_caller_fold": -8.0,
                    "ev_caller_call": -12.0,
                    "ev_caller_cap": -16.0,
                }
            },
        },
        "d3": {
            "n": 5,
            "trips_air_n": 4,
            "two_pair_n": 0,
            "bn_family_n": {"trips": 4.0, "boat_plus": 1.0},
            "caller_vs_bn_flush_plus": {
                "flush": {
                    "n": 2.0,
                    "recommend": "fold",
                    "ev_caller_fold": -8.0,
                    "ev_caller_call": -12.0,
                    "ev_caller_cap": -16.0,
                }
            },
            "caller_vs_bn_boat_plus": {
                "flush": {
                    "n": 2.0,
                    "recommend": "fold",
                    "ev_caller_fold": -8.0,
                    "ev_caller_call": -12.0,
                    "ev_caller_cap": -16.0,
                }
            },
        },
    }
    lines = three_bet_lines_from_by_d(by_d)
    assert lines["line1_trips_draw"]["n"] == 13
    assert lines["line1_trips_draw"]["trips_air_n"] == 11
    assert lines["line1_trips_draw"]["has_trips_air"]
    assert lines["line1_trips_draw"]["flush_vs_flush_plus"] == "fold"
    assert not lines["line1_trips_draw"]["flush_prefers_call_vs_flush_plus"]
    assert lines["line2_pat_straight_plus"]["n"] == 10
    assert not lines["line2_pat_straight_plus"]["has_trips_air"]
    assert lines["line2_pat_straight_plus"]["flush_vs_flush_plus"] == "call"
    assert lines["line2_pat_straight_plus"]["flush_prefers_call_vs_flush_plus"]
    assert lines["d1_boats_quads"]["n"] == 3
    assert not lines["d1_boats_quads"]["has_trips_air"]


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
    assert f.get("stage_c_betting") is True
    assert f.get("hypothesis_trips_call") is True
    assert f["bn_straight_delta"] < 0.0
    assert f["bn_flush_delta"] > 0.0
    assert f["bn_boat_plus_delta"] > 0.0
    assert f["caller_should_not_cap_non_sf_vs_boat"] is True
    by_fam = {r["bucket"]: r for r in data["bn_family"]}
    assert by_fam["straight"]["recommend"] == "call"
    assert by_fam["flush"]["recommend"] == "three_bet"
    assert by_fam["boat_plus"]["recommend"] == "three_bet"
    assert "trips" in by_fam
    assert by_fam["trips"]["recommend"] == "call"
    assert by_fam["trips"].get("bluff_3bet_out_of_scope") is True
    assert "two_pair_or_trips" not in by_fam
    assert f["two_pair_on_node_n"] == 0
    assert f["p_raise_node_locked_range"] < f["p_raise_node_pre_c"]
    assert 0.05 < f["p_raise_node_locked_range"] < 0.15
    by_d = data["node_by_d"]
    assert by_d["d0"]["trips_air_n"] == 0
    assert by_d["d0"]["line"] == "pat_straight_plus"
    assert by_d["d0"]["caller_vs_bn_flush_plus"]["flush"]["recommend"] == "call"
    assert by_d["d1"]["line"] == "draw1_boats_quads"
    assert not by_d["d1"]["has_trips_air"]
    assert by_d["d2"]["has_trips_air"]
    assert by_d["d3"]["has_trips_air"]
    assert by_d["d2"]["caller_vs_bn_flush_plus"]["flush"]["recommend"] == "fold"
    assert by_d["d3"]["caller_vs_bn_flush_plus"]["flush"]["recommend"] == "fold"
    assert f["p_raise_node_locked_range"] == 0.0903
    assert f["n_node_weighted"] == 3612
    assert f["two_pair_on_node_n"] == 0
    assert f["p_raise_node_pre_c"] == 0.189
    assert f["call_it_down_ev_bn"] == -2.3995
    assert f["d0_flush_prefers_call_vs_flush_plus"] is True
    lines = f["three_bet_lines"]
    assert lines["line1_trips_draw"]["has_trips_air"] is True
    assert lines["line1_trips_draw"]["ds"] == [2, 3]
    assert lines["line1_trips_draw"]["flush_vs_flush_plus"] == "fold"
    assert lines["line1_trips_draw"]["flush_prefers_call_vs_flush_plus"] is False
    assert lines["line2_pat_straight_plus"]["has_trips_air"] is False
    assert lines["line2_pat_straight_plus"]["ds"] == [0]
    assert lines["line2_pat_straight_plus"]["flush_vs_flush_plus"] == "call"
    assert lines["line2_pat_straight_plus"]["flush_prefers_call_vs_flush_plus"] is True
    assert lines["d1_boats_quads"]["has_trips_air"] is False
    assert f["line1_has_trips_air"] is True
    assert f["line2_has_trips_air"] is False
    assert f["line2_flush_prefers_call_vs_flush_plus"] is True
    by_fine = {r["bucket"]: r for r in data["bn_fine"]}
    assert by_fine["straight_A"]["recommend"] == "three_bet"
    assert by_fine["straight_5"]["recommend"] == "call"
    assert by_fine["flush_Q"]["recommend"] == "three_bet"
    assert by_fine["flush_A"]["recommend"] == "three_bet"
