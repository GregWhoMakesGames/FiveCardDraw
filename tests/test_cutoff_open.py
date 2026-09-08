"""Cutoff open / pass with BN behind (Agent B frame)."""

from __future__ import annotations

import json
from pathlib import Path

from fivecarddraw.cards import parse_hand
from fivecarddraw.hand_rank import HandCategory, HandValue
from fivecarddraw.validation.cascade_odds import p_one_seat_2to1
from fivecarddraw.validation.cutoff_open import (
    CO_SEAT,
    FOLD_TO_RAISE_EV,
    HJ_SEAT,
    PASS_EV,
    STEAL_EV,
    blend_2to1_street,
    bn_value_continue_as_m2_drawer,
    checkdown_ev_co,
    classify_seat_ids,
    generate_co_vs_2to1_deals,
    generate_co_vs_bn_legal_deals,
    in_sandbag_set_v1,
    is_co_sandbag_class,
    mix_open_ev,
    mix_pass_call_ev,
    planning_behind_co,
)
from fivecarddraw.validation.draw_call_odds import DrawHandResult, classify_draw
from fivecarddraw.validation.postdraw_nonbluff_ev import (
    HONEST_POLICY,
    LOCKED_BN_DRAW,
    NonbluffDeal,
    play_honest_deal,
)
from fivecarddraw.validation.showdown_matrix import classify_opener


FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "validation"
    / "cutoff_open_summary.json"
)


def _hv(cat: int, *tb: int) -> HandValue:
    return HandValue(category=cat, tiebreak=tuple(tb))


def test_sandbag_v1_predicate_hj_co_aces_not_lj():
    assert in_sandbag_set_v1("two_pair", 1) is True
    assert in_sandbag_set_v1("trips", 5) is True
    assert in_sandbag_set_v1("pair_A", HJ_SEAT) is True
    assert in_sandbag_set_v1("pair_A", CO_SEAT) is True
    assert in_sandbag_set_v1("pair_A", 5) is False  # LJ still opens AA
    assert in_sandbag_set_v1("pair_J", CO_SEAT) is False
    assert in_sandbag_set_v1(None, CO_SEAT) is False
    assert is_co_sandbag_class("pair_A") is True
    assert is_co_sandbag_class("two_pair") is True
    assert is_co_sandbag_class("pair_J") is False


def test_accounting_pins():
    assert PASS_EV == 0.0
    assert STEAL_EV == 2.0
    assert FOLD_TO_RAISE_EV == -2.0
    # Steal-only mix: 80% steal, 20% vs BN street EV=$0 → +1.20 vs pass.
    ev = mix_open_ev(
        p_steal=0.8, p_vs_2to1=0.0, p_vs_bn=0.2, ev_street_2to1=3.0, ev_street_bn=0.0
    )
    assert abs(ev - 1.2) < 1e-9
    # Same as 2 + p_bn*(0-4) = 2 - 0.8.
    assert mix_pass_call_ev(p_vs_bn=0.2, ev_street_bn=4.0) == 0.2 * 2.0
    # Pass-call on the same HU as open-vs-legal cannot beat open (steal leftover).
    open_ev = mix_open_ev(
        p_steal=0.75,
        p_vs_2to1=0.05,
        p_vs_bn=0.20,
        ev_street_2to1=3.0,
        ev_street_bn=4.0,
    )
    pass_call = mix_pass_call_ev(p_vs_bn=0.20, ev_street_bn=4.0)
    assert open_ev > pass_call
    assert open_ev > PASS_EV


def test_planning_reuses_p_one_seat_2to1():
    bug = planning_behind_co(co_has_bug=True)
    no = planning_behind_co(co_has_bug=False)
    assert bug["p_one_seat_2to1_approx"] == p_one_seat_2to1(bn_has_bug=True)
    assert no["p_one_seat_2to1_approx"] == p_one_seat_2to1(bn_has_bug=False)
    assert bug["p_any_of_1_6_2to1_approx"] < no["p_any_of_1_6_2to1_approx"]
    assert 0.20 < no["p_bn_open_legal_approx"] < 0.25


def test_classify_seat_open_legal_vs_neither():
    jj = parse_hand("Js Jh 9c 8d 2s")
    assert classify_opener(jj) == "pair_J"
    ids = tuple(sorted(c.card_id for c in jj))
    assert classify_seat_ids(ids, set()) == "open_legal"
    junk = parse_hand("9s 8h 7c 5d 2s")
    junk_ids = tuple(sorted(c.card_id for c in junk))
    assert classify_seat_ids(junk_ids, set()) == "neither"
    assert classify_seat_ids(junk_ids, {frozenset(junk_ids)}) == "two_to_one"


def test_bn_two_pair_continues_instead_of_m2_fold():
    """Raw M2 drawer folds two pair; the mapping must call a CO value-bet."""
    sp, face = bn_value_continue_as_m2_drawer(
        _hv(HandCategory.TWO_PAIR, 13, 12, 9)
    )
    assert sp is False
    assert face == 14
    sp_s, face_s = bn_value_continue_as_m2_drawer(
        _hv(HandCategory.STRAIGHT, 14, 13, 12, 11, 10)
    )
    assert sp_s is True
    assert face_s is None
    _sp, face_j = bn_value_continue_as_m2_drawer(
        _hv(HandCategory.ONE_PAIR, 11, 9, 8, 2)
    )
    assert face_j == 11

    deal = NonbluffDeal(
        opener_class="two_pair",
        caller_class="two_pair",
        d=1,
        caller_d=1,
        opener_start_pair=None,
        opener_final=_hv(HandCategory.TWO_PAIR, 14, 9, 2),
        drawer_final=_hv(HandCategory.TWO_PAIR, 13, 12, 9),
        opener_final_pair=None,
        drawer_final_pair=14,
        drawer_straight_plus=False,
        opener_two_pair_plus=True,
    )
    ev_co, ev_bn, flags = play_honest_deal(deal, HONEST_POLICY)
    assert flags["showdown"]
    assert ev_co + ev_bn == 6.0
    # Unmapped (face=None) would fold the BN two pair and award CO the $6.
    raw = NonbluffDeal(
        opener_class="two_pair",
        caller_class="two_pair",
        d=1,
        caller_d=1,
        opener_start_pair=None,
        opener_final=deal.opener_final,
        drawer_final=deal.drawer_final,
        opener_final_pair=None,
        drawer_final_pair=None,
        drawer_straight_plus=False,
        opener_two_pair_plus=True,
    )
    ev_raw, _c, flags_raw = play_honest_deal(raw, HONEST_POLICY)
    assert not flags_raw["showdown"]
    assert ev_raw == 6.0


def test_checkdown_and_jj_folds_to_bn_value_stab():
    jj = NonbluffDeal(
        opener_class="pair_J",
        caller_class="two_pair",
        d=3,
        caller_d=1,
        opener_start_pair=11,
        opener_final=_hv(HandCategory.ONE_PAIR, 11, 9, 8, 2),
        drawer_final=_hv(HandCategory.TWO_PAIR, 13, 12, 9),
        opener_final_pair=11,
        drawer_final_pair=14,
        drawer_straight_plus=False,
        opener_two_pair_plus=False,
    )
    assert checkdown_ev_co(jj) == 0.0
    ev_co, _ev_bn, flags = play_honest_deal(jj, HONEST_POLICY)
    assert flags["drawer_stab"]
    assert flags["opener_fold_to_stab"]
    assert ev_co == 0.0


def test_draw_order_flag_assigns_first_card_to_first_drawer():
    """CO vs one 2:1: caller-first vs CO-first consume a shuffled remainder differently."""
    co = parse_hand("Js Jh 9c 8d 2s")
    assert classify_opener(co) == "pair_J"
    caller_cards = parse_hand("Ah Kh Qh Th 3c")
    keep = tuple(c for c in caller_cards if str(c) != "3c")
    caller = DrawHandResult(
        cards=caller_cards,
        discard=next(c for c in caller_cards if str(c) == "3c"),
        keep=keep,
        outs=16,
        undealt=48,
        has_bug=False,
        draw_class=classify_draw(keep),
    )
    # Tiny caller list + one CO combo: generator still shuffles remaining.
    deals_16 = generate_co_vs_2to1_deals(
        "pair_J",
        [caller],
        n_deals=6,
        seed=1,
        drawer_is_bn=False,
    )
    deals_bn = generate_co_vs_2to1_deals(
        "pair_J",
        [caller],
        n_deals=6,
        seed=1,
        drawer_is_bn=True,
    )
    assert len(deals_16) == 6
    assert len(deals_bn) == 6
    assert all(d.d == LOCKED_BN_DRAW.pair_d for d in deals_16)
    assert all(d.caller_d == 1 for d in deals_bn)
    # Same seed + same first shuffle of remaining ⇒ different assignment.
    assert any(
        a.opener_final != b.opener_final or a.drawer_final != b.drawer_final
        for a, b in zip(deals_16, deals_bn)
    )


def test_co_vs_bn_hu_generator_locked_draws():
    deals = generate_co_vs_bn_legal_deals("pair_J", n_deals=8, seed=3)
    assert len(deals) == 8
    assert all(d.d == 3 for d in deals)
    assert all(d.opener_class == "pair_J" for d in deals)
    # BN is some open-legal class; CO drew first so BN's caller_d is locked n.
    assert all(d.caller_d in (0, 1, 2, 3) for d in deals)


def test_blend_2to1_weights_bn_caller_leaf():
    probs = {
        "p_vs_2to1": 0.04,
        "p_bn_2to1_leaf": 0.01,
        "p_seat16_2to1_bn_neither": 0.03,
    }
    blended = blend_2to1_street(probs, ev_caller_first=3.0, ev_co_first=4.0)
    assert abs(blended - (0.25 * 4.0 + 0.75 * 3.0)) < 1e-12


def test_fixture_product_answers():
    assert FIXTURE.exists(), "run analyze-cutoff-open --write-fixture"
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    meta = data["meta"]
    assert meta["frame"] == "cutoff_open_no_sandbagging"
    assert meta["accounting"]["pass"] == 0.0
    assert meta["accounting"]["steal"] == 2.0
    assert meta["locked_draws"]["pair_d"] == 3
    assert meta["locked_draws"]["two_pair_d"] == 1
    assert "CO first" in meta["draw_order"]["co_opens_bn_calls"]

    answers = data["answers"]
    assert answers["q1_open_every_legal"] is True
    assert answers["q1_jj_ev_open"] > 0.5
    assert answers["q1_jj_ev_pass"] == 0.0
    assert answers["q2_co_should_sandbag"] is False
    assert answers["q2_pair_A_ev_open"] > answers["q2_pair_A_best_pass"]
    assert answers["q2_two_pair_ev_open"] > answers["q2_two_pair_best_pass"]

    by = {r["co_class"]: r for r in data["by_class"]}
    for cls in ("pair_J", "pair_A", "two_pair"):
        row = by[cls]
        p = row["probs"]
        # Steal is the mass; BN legal is well below 50%.
        assert p["p_steal"] > 0.70
        assert p["p_vs_bn_legal"] < 0.30
        assert abs(p["p_steal"] + p["p_vs_2to1"] + p["p_vs_bn_legal"] - 1.0) < 0.02
        assert row["should_open"] is True
        assert row["ev_open"] > 0.0
        # Open vs BN-legal HU still a $6 street.
        assert 0.0 <= row["vs_bn_legal"]["ev_co_street"] <= 10.0
    # JJ is not a sandbag-set hand; AA / two pair are.
    assert by["pair_J"]["sandbag_set_v1_on_co"] is False
    assert by["pair_A"]["sandbag_set_v1_on_co"] is True
    assert by["two_pair"]["sandbag_set_v1_on_co"] is True
    # Pass-call cannot exceed open (forgone steal).
    for cls in ("pair_A", "two_pair"):
        assert by[cls]["ev_open"] > by[cls]["ev_pass_call"]
