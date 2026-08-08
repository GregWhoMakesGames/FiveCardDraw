"""Five-card hand evaluation with the bug (not fully wild).

The bug may be used as an Ace, or to complete a straight, flush, or straight-flush.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from functools import lru_cache
from typing import Iterable

from fivecarddraw.cards import BUG_ID, Card, card_from_id, make_card


class HandCategory(IntEnum):
    HIGH_CARD = 0
    ONE_PAIR = 1
    TWO_PAIR = 2
    THREE_OF_A_KIND = 3
    STRAIGHT = 4
    FLUSH = 5
    FULL_HOUSE = 6
    FOUR_OF_A_KIND = 7
    STRAIGHT_FLUSH = 8
    FIVE_ACES = 9


CATEGORY_NAMES = {
    HandCategory.HIGH_CARD: "high_card",
    HandCategory.ONE_PAIR: "one_pair",
    HandCategory.TWO_PAIR: "two_pair",
    HandCategory.THREE_OF_A_KIND: "three_of_a_kind",
    HandCategory.STRAIGHT: "straight",
    HandCategory.FLUSH: "flush",
    HandCategory.FULL_HOUSE: "full_house",
    HandCategory.FOUR_OF_A_KIND: "four_of_a_kind",
    HandCategory.STRAIGHT_FLUSH: "straight_flush",
    HandCategory.FIVE_ACES: "five_aces",
}


@dataclass(frozen=True, slots=True, order=True)
class HandValue:
    """Comparable hand strength; higher is better."""

    category: int
    tiebreak: tuple[int, ...]

    @property
    def category_name(self) -> str:
        return CATEGORY_NAMES[HandCategory(self.category)]

    def as_int(self) -> int:
        """Pack into a single int for fast comparisons/storage."""
        # category in high bits, then up to 5 ranks (4 bits each)
        value = self.category
        for r in self.tiebreak:
            value = (value << 4) | (r & 0xF)
        # pad to 5 kickers
        for _ in range(5 - len(self.tiebreak)):
            value <<= 4
        return value


def _ranks_of(cards: Iterable[Card]) -> list[int]:
    return sorted((c.rank for c in cards), reverse=True)


def _evaluate_no_bug(cards: tuple[Card, ...]) -> HandValue:
    ranks = [c.rank for c in cards]
    suits = [c.suit for c in cards]
    rank_counts: dict[int, int] = {}
    for r in ranks:
        rank_counts[r] = rank_counts.get(r, 0) + 1
    counts = sorted(rank_counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
    is_flush = len(set(suits)) == 1
    unique = sorted(set(ranks), reverse=True)

    straight_high = _straight_high(unique)
    is_straight = straight_high is not None

    if is_straight and is_flush:
        return HandValue(HandCategory.STRAIGHT_FLUSH, (straight_high,))

    if counts[0][1] == 4:
        four = counts[0][0]
        kicker = max(r for r in ranks if r != four)
        return HandValue(HandCategory.FOUR_OF_A_KIND, (four, kicker))

    if counts[0][1] == 3 and counts[1][1] == 2:
        return HandValue(HandCategory.FULL_HOUSE, (counts[0][0], counts[1][0]))

    if is_flush:
        return HandValue(HandCategory.FLUSH, tuple(sorted(ranks, reverse=True)))

    if is_straight:
        return HandValue(HandCategory.STRAIGHT, (straight_high,))

    if counts[0][1] == 3:
        trips = counts[0][0]
        kickers = sorted((r for r in ranks if r != trips), reverse=True)
        return HandValue(HandCategory.THREE_OF_A_KIND, (trips, *kickers))

    if counts[0][1] == 2 and counts[1][1] == 2:
        high_pair, low_pair = sorted((counts[0][0], counts[1][0]), reverse=True)
        kicker = max(r for r in ranks if r != high_pair and r != low_pair)
        return HandValue(HandCategory.TWO_PAIR, (high_pair, low_pair, kicker))

    if counts[0][1] == 2:
        pair = counts[0][0]
        kickers = sorted((r for r in ranks if r != pair), reverse=True)
        return HandValue(HandCategory.ONE_PAIR, (pair, *kickers))

    return HandValue(HandCategory.HIGH_CARD, tuple(sorted(ranks, reverse=True)))


def _straight_high(unique_desc: list[int]) -> int | None:
    """Return high card of straight if ranks form a 5-card straight (A-5 allowed)."""
    s = set(unique_desc)
    # Ace-high through wheel
    for high in range(14, 5, -1):
        need = {high, high - 1, high - 2, high - 3, high - 4}
        if high == 5:
            # already covered as high=5 -> 5,4,3,2,1 — handle wheel separately
            pass
        if need <= s:
            return high
    # Wheel: A,2,3,4,5
    if {14, 2, 3, 4, 5} <= s:
        return 5
    return None


def _legal_bug_replacements(other: tuple[Card, ...]) -> list[Card]:
    """Legal cards the bug may become given the other four cards."""
    replacements: dict[int, Card] = {}

    def add(card: Card) -> None:
        # Cannot duplicate an already-held card
        if any(c.card_id == card.card_id for c in other):
            return
        replacements[card.card_id] = card

    # Always: bug may be used as an Ace of any suit
    for suit in range(4):
        add(make_card(14, suit))

    suits = [c.suit for c in other]
    ranks = [c.rank for c in other]
    rank_set = set(ranks)

    # Flush completion: if all four share a suit, bug may be any missing rank of that suit
    if len(set(suits)) == 1:
        suit = suits[0]
        for rank in range(2, 15):
            add(make_card(rank, suit))

    # Straight / straight-flush completion:
    # For each 5-rank straight window, if other ranks are a subset, bug fills a missing rank.
    windows: list[list[int]] = []
    for high in range(6, 15):
        windows.append([high, high - 1, high - 2, high - 3, high - 4])
    windows.append([14, 5, 4, 3, 2])  # wheel ranks (ace plays low)

    for window in windows:
        wset = set(window)
        if not rank_set <= wset:
            continue
        missing = list(wset - rank_set)
        if len(missing) != 1:
            # 0 missing means four cards already in window with duplicate ranks elsewhere;
            # with four distinct cards subset, missing should be 1. If duplicates, skip.
            continue
        miss_rank = missing[0]
        # Prefer suited if that makes SF; otherwise any free suit
        if len(set(suits)) == 1:
            add(make_card(miss_rank, suits[0]))
        for suit in range(4):
            add(make_card(miss_rank, suit))

    # Also allow bug-as-ace already covered; if three of a suit + one off, bug cannot
    # make a flush (needs 4 suited among the non-bug? Actually 4 cards needed same suit
    # for bug to complete flush with 5 cards — yes need all 4 non-bug suited).

    # Straight with duplicate ranks in `other` cannot form a straight; handled by subset check.

    if not replacements:
        # Should never happen — aces always attempted — but keep safe fallback
        for suit in range(4):
            add(make_card(14, suit))

    return list(replacements.values())


def evaluate_hand(cards: Iterable[Card]) -> HandValue:
    cards_t = tuple(cards)
    if len(cards_t) != 5:
        raise ValueError("evaluate_hand expects exactly 5 cards")
    ids = [c.card_id for c in cards_t]
    if len(set(ids)) != 5:
        raise ValueError("duplicate cards in hand")

    bug_cards = [c for c in cards_t if c.is_bug]
    if len(bug_cards) > 1:
        raise ValueError("at most one bug allowed")
    if not bug_cards:
        return _evaluate_no_bug(cards_t)

    other = tuple(c for c in cards_t if not c.is_bug)
    # Four aces + bug is five aces (bug is a fifth ace, not a duplicate deck ace).
    if sum(1 for c in other if c.rank == 14) == 4:
        return HandValue(HandCategory.FIVE_ACES, (14,))

    best: HandValue | None = None
    for repl in _legal_bug_replacements(other):
        value = _evaluate_no_bug(other + (repl,))
        if best is None or value > best:
            best = value
    assert best is not None
    return best


def can_open_jacks_or_better(cards: Iterable[Card]) -> bool:
    """True if hand is a legal jacks-or-better opener."""
    value = evaluate_hand(cards)
    if value.category >= HandCategory.TWO_PAIR:
        return True
    if value.category == HandCategory.ONE_PAIR:
        return value.tiebreak[0] >= 11  # jacks or better
    return False


def pair_rank(cards: Iterable[Card]) -> int | None:
    value = evaluate_hand(cards)
    if value.category == HandCategory.ONE_PAIR:
        return value.tiebreak[0]
    return None


@lru_cache(maxsize=None)
def evaluate_hand_ids(card_ids: tuple[int, ...]) -> HandValue:
    return evaluate_hand(tuple(card_from_id(i) for i in card_ids))


def evaluate_hand_ids_int(card_ids: tuple[int, ...]) -> int:
    return evaluate_hand_ids(card_ids).as_int()
