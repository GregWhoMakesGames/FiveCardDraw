"""Smoke tests for M2 post-draw face-pair grid helpers."""

from fivecarddraw.hand_rank import HandCategory, HandValue
from fivecarddraw.validation.postdraw_betting_m2 import (
    Deal,
    Policy,
    all_policies,
    play_deal,
)


def _hv(cat: int, *tb: int) -> HandValue:
    return HandValue(category=cat, tiebreak=tuple(tb))


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
    pol = Policy(None, None, None)  # check pairs; no stab
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
