"""Card / deck parsing helpers."""

import pytest

from fivecarddraw.cards import (
    BUG_ID,
    bug,
    card_from_id,
    full_deck,
    make_card,
    parse_card,
    parse_hand,
)


def test_full_deck_has_bug():
    assert len(full_deck()) == 53
    assert len(full_deck(include_bug=False)) == 52
    assert full_deck()[-1] == bug()
    assert bug().card_id == BUG_ID


def test_card_from_id_roundtrip():
    for i in range(53):
        c = card_from_id(i)
        assert c.card_id == i
    assert str(card_from_id(BUG_ID)) == "Bu"
    with pytest.raises(ValueError):
        card_from_id(53)


def test_parse_hand_and_duplicates():
    h = parse_hand("As Ad 9c 8h 2d")
    assert len(h) == 5
    assert str(h[0]) == "As"
    with pytest.raises(ValueError, match="duplicate"):
        parse_hand("As As 9c 8h 2d")
    with pytest.raises(ValueError, match="expected 5"):
        parse_hand("As Ad 9c")


def test_parse_bug_aliases():
    assert parse_card("Bu").is_bug
    assert parse_card("bug").is_bug
    assert parse_card("joker").is_bug


def test_make_card_rejects_bad_rank_suit():
    with pytest.raises(ValueError):
        make_card(1, 0)
    with pytest.raises(ValueError):
        make_card(14, 4)
