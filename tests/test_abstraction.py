"""Abstraction merge/split checks."""

from fivecarddraw.abstraction import bucket_hand
from fivecarddraw.cards import parse_hand


def test_aa852_merges_with_aat43():
    a = bucket_hand(parse_hand("As Ad 8c 5h 2d"))
    b = bucket_hand(parse_hand("As Ad Tc 4h 3d"))
    assert a.label() == b.label()


def test_aaq85_differs_from_aa852():
    a = bucket_hand(parse_hand("As Ad 8c 5h 2d"))
    q = bucket_hand(parse_hand("As Ad Qc 8h 5d"))
    assert a.label() != q.label()
    assert q.count == 1
    assert a.count == 0
    assert "F1" in q.detail
    assert "F0" in a.detail


def test_open_legal_flag():
    openers = bucket_hand(parse_hand("Js Jd 9c 4h 2d"))
    junk = bucket_hand(parse_hand("9s 8d 7c 4h 2d"))
    assert openers.open_legal
    assert not junk.open_legal


def test_bug_sf_draw_classified():
    # Suited connectors + bug — strong SF draw class
    key = bucket_hand(parse_hand("Bu 9c 8c 7c 2d"))
    assert key.draw.startswith("bug")
