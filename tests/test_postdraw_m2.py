"""M2 post-draw face-pair grid: unit tests + summary fixture pins."""

from __future__ import annotations

import json
from pathlib import Path

from fivecarddraw.hand_rank import HandCategory, HandValue
from fivecarddraw.validation.postdraw_betting_m2 import (
    Deal,
    Policy,
    all_policies,
    play_deal,
)


FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "validation"
    / "postdraw_m2_grid_summary.json"
)


def _hv(cat: int, *tb: int) -> HandValue:
    return HandValue(category=cat, tiebreak=tuple(tb))


def _load_summary() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_policy_grid_size():
    assert len(all_policies()) == 5 * 4 * 3


def test_check_check_showdown_ev_when_opener_wins():
    deal = Deal(
        opener_class="pair_A",
        opener_start_pair=14,
        d=3,
        opener_final=_hv(HandCategory.ONE_PAIR, 14, 9, 8, 2),
        drawer_final=_hv(HandCategory.HIGH_CARD, 13, 12, 9, 8, 2),
        opener_final_pair=14,
        drawer_final_pair=None,
        drawer_straight_plus=False,
        opener_two_pair_plus=False,
    )
    pol = Policy(None, None, None)  # check pairs; no face-pair stab
    ev, flags = play_deal(deal, pol)
    assert flags["opener_pair_check"]
    assert flags["showdown"]
    assert ev == 6.0  # win unimproved pot


def test_aa_lead_gets_fold_from_miss():
    deal = Deal(
        opener_class="pair_A",
        opener_start_pair=14,
        d=3,
        opener_final=_hv(HandCategory.ONE_PAIR, 14, 9, 8, 2),
        drawer_final=_hv(HandCategory.HIGH_CARD, 13, 12, 9, 8, 2),
        opener_final_pair=14,
        drawer_final_pair=None,
        drawer_straight_plus=False,
        opener_two_pair_plus=False,
    )
    pol = Policy(14, None, None)
    ev, flags = play_deal(deal, pol)
    assert flags["opener_pair_lead"]
    assert not flags["showdown"]
    assert ev == 6.0  # bet 4 into 6, fold, collect 10 → net +6


def test_straight_plus_stabs_even_when_face_stab_never():
    """Drawer always value-bets straight+ when opener checks."""
    deal = Deal(
        opener_class="pair_K",
        opener_start_pair=13,
        d=3,
        opener_final=_hv(HandCategory.ONE_PAIR, 13, 9, 8, 2),
        drawer_final=_hv(HandCategory.FLUSH, 14, 12, 9, 8, 3),
        opener_final_pair=13,
        drawer_final_pair=None,
        drawer_straight_plus=True,
        opener_two_pair_plus=False,
    )
    pol = Policy(None, None, None)
    ev, flags = play_deal(deal, pol)
    assert flags["opener_pair_check"]
    assert flags["drawer_stab"]
    # Matched call-down with stab_min=None → opener folds one pair to stab
    assert flags["opener_fold_to_stab"]
    assert ev == 0.0


def test_fixture_summary_patterns():
    data = _load_summary()
    assert data["meta"]["opener_first"] is True
    assert data["meta"]["predraw_pot"] == 6.0
    assert data["meta"]["big_bet"] == 4.0
    assert data["meta"]["n_deals"] == 25_000
    assert data["meta"]["seed"] == 20260808

    findings = data["findings"]
    assert findings["default_check_one_pair"] is True
    # Leading one pair vs passive drawer is strictly worse
    assert findings["lead_aa_only_vs_passive_delta_d3"] < -0.3
    assert findings["lead_jplus_vs_passive_delta_d3"] < -1.0
    # Thin exception: leading AA vs AA-only stab is not worse
    assert findings["lead_aa_vs_aa_stab_delta_d3"] >= 0.0

    by_lead = {r["lead"]: r for r in data["sweep_lead"]}
    assert by_lead["never"]["vs_passive_drawer_ev_d3"] == 3.6662
    assert by_lead["AA"]["vs_passive_drawer_ev_d3"] == 3.2914
    assert by_lead["AA..JJ"]["vs_passive_drawer_ev_d3"] == 2.2056
    assert by_lead["AA"]["vs_AA_stab_no_raise"] == 3.2914
    assert by_lead["never"]["vs_AA_stab_no_raise"] == 3.2519

    by_stab = {r["stab"]: r for r in data["sweep_stab"]}
    # Straight+ still stabs when face-pair stab is off
    assert by_stab["never"]["stab_rate_if_check"] == 0.3434
    assert by_stab["AA..JJ"]["ev_d3_if_opener_never_leads"] == 2.2056

    top = data["top_by_pair_final_d3"][0]
    assert top["policy"].startswith("lead=never|stab=never")
    assert top["ev"] == 3.6662


def test_two_pair_value_bet_miss_folds():
    deal = Deal(
        opener_class="two_pair",
        opener_start_pair=None,
        d=1,
        opener_final=_hv(HandCategory.TWO_PAIR, 14, 9, 2),
        drawer_final=_hv(HandCategory.HIGH_CARD, 13, 12, 9, 8, 2),
        opener_final_pair=None,
        drawer_final_pair=None,
        drawer_straight_plus=False,
        opener_two_pair_plus=True,
    )
    ev, flags = play_deal(deal, Policy(None, None, None))
    assert not flags["opener_pair_check"]
    assert not flags["showdown"]
    assert ev == 6.0


def test_two_pair_value_bet_face_pair_calls_to_showdown():
    deal = Deal(
        opener_class="two_pair",
        opener_start_pair=None,
        d=1,
        opener_final=_hv(HandCategory.TWO_PAIR, 14, 9, 2),
        drawer_final=_hv(HandCategory.ONE_PAIR, 14, 9, 8, 2),
        opener_final_pair=None,
        drawer_final_pair=14,
        drawer_straight_plus=False,
        opener_two_pair_plus=True,
    )
    ev, flags = play_deal(deal, Policy(None, 14, None))
    assert flags["showdown"]
    assert flags["opener_wins_sd"]
    assert ev == 10.0  # bet 4, called, pot 14, win → +10


def test_kk_folds_aa_stab_aa_calls():
    kk = Deal(
        opener_class="pair_K",
        opener_start_pair=13,
        d=3,
        opener_final=_hv(HandCategory.ONE_PAIR, 13, 9, 8, 2),
        drawer_final=_hv(HandCategory.ONE_PAIR, 14, 9, 8, 2),
        opener_final_pair=13,
        drawer_final_pair=14,
        drawer_straight_plus=False,
        opener_two_pair_plus=False,
    )
    pol = Policy(None, 14, None)
    ev, flags = play_deal(kk, pol)
    assert flags["opener_fold_to_stab"]
    assert ev == 0.0

    aa = Deal(
        opener_class="pair_A",
        opener_start_pair=14,
        d=3,
        opener_final=_hv(HandCategory.ONE_PAIR, 14, 9, 8, 2),
        drawer_final=_hv(HandCategory.ONE_PAIR, 14, 13, 8, 2),
        opener_final_pair=14,
        drawer_final_pair=14,
        drawer_straight_plus=False,
        opener_two_pair_plus=False,
    )
    ev, flags = play_deal(aa, pol)
    assert flags["opener_call_stab"]
    assert flags["showdown"]


def test_check_check_tie_splits_pot():
    v = _hv(HandCategory.ONE_PAIR, 14, 9, 8, 2)
    deal = Deal(
        opener_class="pair_A",
        opener_start_pair=14,
        d=3,
        opener_final=v,
        drawer_final=v,
        opener_final_pair=14,
        drawer_final_pair=14,
        drawer_straight_plus=False,
        opener_two_pair_plus=False,
    )
    # No face stab → both check; split the $6 pot.
    ev, flags = play_deal(deal, Policy(None, None, None))
    assert flags["showdown"]
    assert ev == 3.0


def test_aa_lead_folds_to_straight_plus_raise_when_no_raise_band():
    """Straight+ always raises a bet; with raise_min=None a one-pair opener folds."""
    deal = Deal(
        opener_class="pair_A",
        opener_start_pair=14,
        d=3,
        opener_final=_hv(HandCategory.ONE_PAIR, 14, 9, 8, 2),
        drawer_final=_hv(HandCategory.FLUSH, 14, 12, 9, 8, 3),
        opener_final_pair=14,
        drawer_final_pair=None,
        drawer_straight_plus=True,
        opener_two_pair_plus=False,
    )
    ev, flags = play_deal(deal, Policy(14, None, None))
    assert flags["opener_pair_lead"]
    assert flags["drawer_raise"]
    assert flags["opener_fold_to_raise"]
    assert ev == -4.0
