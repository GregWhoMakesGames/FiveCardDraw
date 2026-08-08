"""Hand abstraction: collapse strategically similar five-card holdings into buckets."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from typing import Iterable

from fivecarddraw.cards import (
    BUG_ID,
    FACE_RANKS,
    Card,
    card_from_id,
    full_deck,
    parse_hand,
)
from fivecarddraw.hand_rank import (
    HandCategory,
    can_open_jacks_or_better,
    evaluate_hand,
)


def _face_count(cards: Iterable[Card]) -> int:
    return sum(1 for c in cards if not c.is_bug and c.rank in FACE_RANKS)


def _ace_count(cards: Iterable[Card], bug_as_ace_potential: bool = True) -> int:
    n = sum(1 for c in cards if not c.is_bug and c.rank == 14)
    if bug_as_ace_potential and any(c.is_bug for c in cards):
        # Bug can always be an ace; count it for "ace material" when not used in SF/flush
        n += 1
    return n


def _kicker_bin(rank: int) -> str:
    """Coarse kicker bins.

    Non-face kickers collapse together so AA852 ≈ AAT43, while a queen
    kicker (AAQ85) remains distinct via face count / face bin.
    """
    if rank == 14:
        return "A"
    if rank in FACE_RANKS:
        # Preserve Q vs K vs J somewhat — still coarse
        if rank == 13:
            return "K"
        if rank == 12:
            return "Q"
        return "J"
    return "x"


def _draw_outs_class(cards: tuple[Card, ...]) -> str:
    """Classify primary draw potential (especially bug SF / flush / straight draws)."""
    has_bug = any(c.is_bug for c in cards)
    other = [c for c in cards if not c.is_bug]
    value = evaluate_hand(cards)

    # Already a strong made hand — draw class secondary
    if value.category >= HandCategory.STRAIGHT:
        return "made_straight+"
    if value.category == HandCategory.THREE_OF_A_KIND:
        return "made_trips"
    if value.category == HandCategory.TWO_PAIR:
        return "made_two_pair"
    if value.category == HandCategory.FOUR_OF_A_KIND:
        return "made_quads"
    if value.category == HandCategory.FULL_HOUSE:
        return "made_boat"
    if value.category == HandCategory.FIVE_ACES:
        return "made_five_aces"

    suits = [c.suit for c in other]
    suit_counts = Counter(suits)
    max_suit = max(suit_counts.values()) if suit_counts else 0
    ranks = sorted({c.rank for c in other})

    # Four-flush (with or without bug already completing — if bug+3 suited unfinished flush)
    if has_bug and max_suit >= 3:
        # bug + 3 suited: flush draw / SF potential
        suited = [c for c in other if suit_counts[c.suit] == max_suit]
        if max_suit >= 4:
            return "bug_flush_or_better"
        return _bug_sf_draw_bin(suited, ranks)
    if not has_bug and max_suit == 4:
        return "four_flush"

    # Open-ended / gutshot style with bug
    if has_bug:
        straightish = _straight_gap_score(ranks)
        if straightish >= 2:
            return f"bug_straight_draw_{straightish}"
        return "bug_ace_material"

    if max_suit == 3:
        return "three_flush"
    straightish = _straight_gap_score(ranks)
    if straightish >= 2:
        return f"straight_draw_{straightish}"
    return "no_draw"


def _bug_sf_draw_bin(suited: list[Card], all_ranks: list[int]) -> str:
    """Rough outs bin for bug + suited cards (classic 15–22 out SF draws)."""
    ranks = sorted({c.rank for c in suited})
    gaps = _straight_gap_score(ranks)
    # Higher gaps connectivity => more SF outs when bug fills
    if gaps >= 3 and len(ranks) >= 3:
        return "bug_sf_draw_high"  # ~22-out class
    if gaps >= 2:
        return "bug_sf_draw_med"
    if len(suited) >= 3:
        return "bug_flush_draw"
    return "bug_sf_draw_low"


def _straight_gap_score(ranks: list[int]) -> int:
    """How connected are ranks toward a straight (0–4). Includes wheel ace."""
    if not ranks:
        return 0
    s = set(ranks)
    best = 0
    windows = [[h, h - 1, h - 2, h - 3, h - 4] for h in range(6, 15)]
    windows.append([14, 5, 4, 3, 2])
    for w in windows:
        overlap = len(s & set(w))
        best = max(best, overlap)
    return best


@dataclass(frozen=True, slots=True)
class BucketKey:
    """Hashable abstraction key for a five-card hand."""

    category: str
    detail: str
    count: int  # face-card count (J/Q/K)
    aces: int  # ace material including bug-as-ace potential
    has_bug: bool
    draw: str
    open_legal: bool

    def label(self) -> str:
        bug = "Bu" if self.has_bug else "noBu"
        open_s = "open" if self.open_legal else "pass"
        return (
            f"{self.category}|{self.detail}|faces{self.count}|A{self.aces}|"
            f"{bug}|{self.draw}|{open_s}"
        )


def bucket_hand(cards: Iterable[Card]) -> BucketKey:
    cards_t = tuple(cards)
    if len(cards_t) != 5:
        raise ValueError("bucket_hand expects 5 cards")
    value = evaluate_hand(cards_t)
    has_bug = any(c.is_bug for c in cards_t)
    faces = _face_count(cards_t)
    # For ace count display in key: physical aces + bug flag separately via has_bug
    physical_aces = sum(1 for c in cards_t if not c.is_bug and c.rank == 14)
    aces = physical_aces + (1 if has_bug else 0)
    open_legal = can_open_jacks_or_better(cards_t)
    draw = _draw_outs_class(cards_t)
    cat = value.category_name

    if value.category == HandCategory.ONE_PAIR:
        pair = value.tiebreak[0]
        kickers = value.tiebreak[1:]
        kbins = "".join(_kicker_bin(k) for k in kickers)
        # Collapse low/mid patterns without faces: AA852 ~ AAT43 => pair=A, kbins without F
        detail = f"pair{pair}:{kbins}"
    elif value.category == HandCategory.TWO_PAIR:
        detail = f"tp{value.tiebreak[0]}_{value.tiebreak[1]}:{_kicker_bin(value.tiebreak[2])}"
    elif value.category == HandCategory.THREE_OF_A_KIND:
        trips = value.tiebreak[0]
        kbins = "".join(_kicker_bin(k) for k in value.tiebreak[1:])
        detail = f"trips{trips}:{kbins}"
    elif value.category == HandCategory.HIGH_CARD:
        top = value.tiebreak[0]
        kbins = "".join(_kicker_bin(k) for k in value.tiebreak[:5])
        detail = f"hc{top}:{kbins}"
    elif value.category in (
        HandCategory.STRAIGHT,
        HandCategory.FLUSH,
        HandCategory.STRAIGHT_FLUSH,
    ):
        detail = f"high{value.tiebreak[0]}"
    elif value.category == HandCategory.FULL_HOUSE:
        detail = f"fh{value.tiebreak[0]}_{value.tiebreak[1]}"
    elif value.category == HandCategory.FOUR_OF_A_KIND:
        detail = f"quad{value.tiebreak[0]}"
    elif value.category == HandCategory.FIVE_ACES:
        detail = "five_aces"
    else:
        detail = "na"

    return BucketKey(
        category=cat,
        detail=detail,
        count=faces,
        aces=aces,
        has_bug=has_bug,
        draw=draw,
        open_legal=open_legal,
    )


@dataclass(slots=True)
class AbstractionTable:
    """Maps every 5-card combo to a bucket id and stores combo weights."""

    bucket_labels: list[str]
    # card_ids (sorted tuple) -> bucket_id
    hand_to_bucket: dict[tuple[int, ...], int]
    bucket_weight: list[float]
    bucket_open_legal: list[bool]
    examples: dict[str, list[str]]

    @property
    def num_buckets(self) -> int:
        return len(self.bucket_labels)

    def bucket_id_for_cards(self, cards: Iterable[Card]) -> int:
        key = tuple(sorted(c.card_id for c in cards))
        return self.hand_to_bucket[key]


def build_abstraction(
    include_bug: bool = True,
    progress: bool = True,
    store_hands: bool = False,
) -> AbstractionTable:
    """Enumerate all 5-card hands and assign abstraction buckets.

    By default does not store the full hand→bucket map (memory-heavy); solve
    stages only need bucket labels/weights. Pass store_hands=True for audits
    that need exact combo lookup.
    """
    deck = full_deck(include_bug=include_bug)
    ids = [c.card_id for c in deck]
    label_to_id: dict[str, int] = {}
    bucket_labels: list[str] = []
    hand_to_bucket: dict[tuple[int, ...], int] = {}
    weights: list[float] = []
    open_legal: list[bool] = []
    examples: dict[str, list[str]] = defaultdict(list)
    total_hands = 0

    # C(53,5) = 2,869,685 — feasible
    iterator = combinations(ids, 5)
    if progress:
        try:
            from tqdm import tqdm

            n = 2_869_685 if include_bug else 2_598_960
            iterator = tqdm(iterator, total=n, desc="abstraction", unit="hand")
        except ImportError:
            pass

    for combo in iterator:
        total_hands += 1
        cards = tuple(card_from_id(i) for i in combo)
        key = bucket_hand(cards)
        label = key.label()
        if label not in label_to_id:
            label_to_id[label] = len(bucket_labels)
            bucket_labels.append(label)
            weights.append(0.0)
            open_legal.append(key.open_legal)
        bid = label_to_id[label]
        if store_hands:
            hand_to_bucket[tuple(sorted(combo))] = bid
        weights[bid] += 1.0
        if len(examples[label]) < 3:
            examples[label].append(" ".join(str(c) for c in cards))

    table = AbstractionTable(
        bucket_labels=bucket_labels,
        hand_to_bucket=hand_to_bucket,
        bucket_weight=weights,
        bucket_open_legal=open_legal,
        examples=dict(examples),
    )
    # Stash total for reporting when hand map is omitted
    table.examples.setdefault("__meta__", []).append(f"total_hands={total_hands}")
    return table


def audit_abstraction(table: AbstractionTable | None = None) -> str:
    """Human-readable audit: bucket count and key merge/split examples."""
    if table is None:
        table = build_abstraction(progress=True)
    num_hands = int(sum(table.bucket_weight))
    if table.hand_to_bucket:
        num_hands = len(table.hand_to_bucket)
    lines = [
        f"num_buckets={table.num_buckets}",
        f"num_hands={num_hands}",
        f"open_legal_buckets={sum(1 for x in table.bucket_open_legal if x)}",
        f"pass_only_buckets={sum(1 for x in table.bucket_open_legal if not x)}",
    ]

    def label_for(hand_text: str) -> str:
        cards = parse_hand(hand_text)
        return bucket_hand(cards).label()

    aa852 = label_for("As Ad 8c 5h 2d")
    aat43 = label_for("As Ad Tc 4h 3d")
    aaq85 = label_for("As Ad Qc 8h 5d")
    lines.append(f"AA852 bucket: {aa852}")
    lines.append(f"AAT43 bucket: {aat43}")
    lines.append(f"AAQ85 bucket: {aaq85}")
    lines.append(f"AA852==AAT43: {aa852 == aat43}")
    lines.append(f"AA852!=AAQ85: {aa852 != aaq85}")

    # Top heaviest buckets
    heavy = sorted(
        enumerate(table.bucket_weight), key=lambda x: x[1], reverse=True
    )[:10]
    lines.append("top_buckets_by_weight:")
    for bid, w in heavy:
        lines.append(f"  {w:.0f}\t{table.bucket_labels[bid]}")
    return "\n".join(lines)


def main_audit() -> None:
    print(audit_abstraction())


if __name__ == "__main__":
    main_audit()
