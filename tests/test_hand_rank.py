"""Tests for bug-aware hand ranking and jacks-or-better."""

from fivecarddraw.cards import parse_hand
from fivecarddraw.hand_rank import HandCategory, can_open_jacks_or_better, evaluate_hand


def ev(text: str):
    return evaluate_hand(parse_hand(text))


def test_pair_of_jacks_opens():
    v = ev("Js Jd 9c 4h 2d")
    assert v.category == HandCategory.ONE_PAIR
    assert v.tiebreak[0] == 11
    assert can_open_jacks_or_better(parse_hand("Js Jd 9c 4h 2d"))


def test_pair_of_tens_cannot_open():
    assert not can_open_jacks_or_better(parse_hand("Ts Td 9c 4h 2d"))


def test_bug_as_ace_makes_aces_and_opens():
    # Bug is a single ace unless paired with another ace
    high = parse_hand("Bu Kc 9d 4h 2s")
    assert evaluate_hand(high).category == HandCategory.HIGH_CARD
    assert not can_open_jacks_or_better(high)

    hand = parse_hand("Bu As 9d 4h 2s")
    v = evaluate_hand(hand)
    assert v.category == HandCategory.ONE_PAIR
    assert v.tiebreak[0] == 14
    assert can_open_jacks_or_better(hand)


def test_bug_completes_straight():
    hand = parse_hand("Bu 9c 8d 7h 6s")
    v = evaluate_hand(hand)
    assert v.category == HandCategory.STRAIGHT
    assert v.tiebreak[0] == 10  # T-high straight T9876


def test_bug_completes_flush():
    hand = parse_hand("Bu 2c 5c 9c Kc")
    v = evaluate_hand(hand)
    assert v.category == HandCategory.FLUSH


def test_bug_completes_straight_flush():
    hand = parse_hand("Bu 9c 8c 7c 6c")
    v = evaluate_hand(hand)
    assert v.category == HandCategory.STRAIGHT_FLUSH


def test_bug_does_not_make_trip_kings():
    """Bug is not fully wild — K K x x Bu is pair of kings with ace kicker, not trips."""
    hand = parse_hand("Bu Kc Kd 9h 2s")
    v = evaluate_hand(hand)
    assert v.category == HandCategory.ONE_PAIR
    assert v.tiebreak[0] == 13
    assert v.tiebreak[1] == 14
    assert can_open_jacks_or_better(hand)


def test_five_aces():
    hand = parse_hand("Bu As Ad Ac Ah")
    v = evaluate_hand(hand)
    assert v.category == HandCategory.FIVE_ACES


def test_two_pair_opens():
    assert can_open_jacks_or_better(parse_hand("2s 2d 3c 3h 9d"))


def test_wheel_straight():
    v = ev("As 2c 3d 4h 5s")
    assert v.category == HandCategory.STRAIGHT
    assert v.tiebreak[0] == 5


def test_full_house_beats_flush():
    boat = ev("As Ad Ac 9h 9s")
    flush = ev("Ah Kh Qh 4h 2h")
    assert boat > flush


def test_bug_completes_wheel():
    # A345 + bug fills the 2 → 5-high wheel. 2345 + bug is a *6-high* (bug=6).
    v = ev("Bu Ac 3d 4h 5s")
    assert v.category == HandCategory.STRAIGHT
    assert v.tiebreak[0] == 5
    six = ev("Bu 2c 3d 4h 5s")
    assert six.category == HandCategory.STRAIGHT
    assert six.tiebreak[0] == 6
    assert six > v


def test_bug_with_two_pair_is_not_a_boat():
    """Bug is an ace, not fully wild — KK99+bug is kings-up with an ace kicker, not a boat."""
    v = ev("Bu Kc Kd 9h 9s")
    assert v.category == HandCategory.TWO_PAIR
    assert v.tiebreak[0] == 13  # kings up
    assert v.tiebreak[1] == 9
    assert v.tiebreak[2] == 14  # ace kicker (the bug)


def test_quads_beat_full_house():
    quads = ev("As Ad Ac Ah 2d")
    boat = ev("Ks Kd Kc 9h 9s")
    assert quads.category == HandCategory.FOUR_OF_A_KIND
    assert quads > boat


def test_identical_hands_tie():
    a = ev("Js Jd 9c 8h 2d")
    b = ev("Js Jd 9c 8h 2d")
    assert a == b
    assert not (a > b) and not (a < b)


def test_trips_aces_with_bug():
    v = ev("Bu As Ad 9h 2s")
    assert v.category == HandCategory.THREE_OF_A_KIND
    assert v.tiebreak[0] == 14


def test_broadway_bug_straight():
    v = ev("Bu Kc Qd Jh Ts")
    assert v.category == HandCategory.STRAIGHT
    assert v.tiebreak[0] == 14
