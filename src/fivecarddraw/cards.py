"""Card, deck, and bug representation for five-card draw."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable

RANK_CHARS = "23456789TJQKA"
SUIT_CHARS = "cdhs"
RANK_NAMES = {
    2: "2",
    3: "3",
    4: "4",
    5: "5",
    6: "6",
    7: "7",
    8: "8",
    9: "9",
    10: "T",
    11: "J",
    12: "Q",
    13: "K",
    14: "A",
}
SUIT_NAMES = {0: "c", 1: "d", 2: "h", 3: "s"}

FACE_RANKS = frozenset({11, 12, 13})  # J, Q, K (Aces tracked separately)
OPENER_PAIR_RANKS = frozenset({11, 12, 13, 14})  # jacks or better


class Suit(IntEnum):
    CLUBS = 0
    DIAMONDS = 1
    HEARTS = 2
    SPADES = 3


BUG_ID = 52  # index after 52 standard cards


@dataclass(frozen=True, slots=True, order=True)
class Card:
    """A standard card or the bug (joker)."""

    rank: int  # 2-14, or 0 for bug
    suit: int  # 0-3, or -1 for bug
    card_id: int

    @property
    def is_bug(self) -> bool:
        return self.card_id == BUG_ID

    @property
    def is_face(self) -> bool:
        return self.rank in FACE_RANKS

    @property
    def is_ace(self) -> bool:
        return self.rank == 14

    def __str__(self) -> str:
        if self.is_bug:
            return "Bu"
        return f"{RANK_NAMES[self.rank]}{SUIT_NAMES[self.suit]}"

    def __repr__(self) -> str:
        return str(self)


def make_card(rank: int, suit: int) -> Card:
    if not (2 <= rank <= 14):
        raise ValueError(f"invalid rank: {rank}")
    if not (0 <= suit <= 3):
        raise ValueError(f"invalid suit: {suit}")
    card_id = (rank - 2) * 4 + suit
    return Card(rank=rank, suit=suit, card_id=card_id)


def bug() -> Card:
    return Card(rank=0, suit=-1, card_id=BUG_ID)


def card_from_id(card_id: int) -> Card:
    if card_id == BUG_ID:
        return bug()
    if not (0 <= card_id < 52):
        raise ValueError(f"invalid card_id: {card_id}")
    rank = card_id // 4 + 2
    suit = card_id % 4
    return Card(rank=rank, suit=suit, card_id=card_id)


def parse_card(text: str) -> Card:
    text = text.strip()
    if text.lower() in {"bu", "bug", "joker", "jk", "jo"}:
        return bug()
    if len(text) != 2:
        raise ValueError(f"invalid card: {text}")
    rank_char, suit_char = text[0].upper(), text[1].lower()
    if rank_char not in RANK_CHARS or suit_char not in SUIT_CHARS:
        raise ValueError(f"invalid card: {text}")
    # RANK_CHARS = "23456789TJQKA" — index 0 -> rank 2
    rank = RANK_CHARS.index(rank_char) + 2
    suit = SUIT_CHARS.index(suit_char)
    return make_card(rank, suit)


def parse_hand(text: str) -> tuple[Card, ...]:
    """Parse a hand like 'As Ad 8c 5h 2d' or 'AA852' style short forms are not supported here."""
    parts = text.replace(",", " ").split()
    if len(parts) != 5:
        raise ValueError(f"expected 5 cards, got {len(parts)} from {text!r}")
    cards = tuple(parse_card(p) for p in parts)
    ids = [c.card_id for c in cards]
    if len(set(ids)) != 5:
        raise ValueError(f"duplicate cards in hand: {text}")
    return cards


def full_deck(include_bug: bool = True) -> list[Card]:
    cards = [card_from_id(i) for i in range(52)]
    if include_bug:
        cards.append(bug())
    return cards


def hand_to_str(cards: Iterable[Card]) -> str:
    return " ".join(str(c) for c in cards)
