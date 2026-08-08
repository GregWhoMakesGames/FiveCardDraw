"""Dealer opener × drawing-caller post-draw showdown matrix.

Heads-up: dealer opens a fine-split made class; one caller from the 2:1
drawing set (bug SF/straight draws + FFS16) calls and draws one.

Showdown uses the **exact remaining deck** after both hole cards are known
(43 unseen). Pot-odds calling still used outs/48; this module does not.

Discard policies (v1, pinned):
  Caller: keep 4 (best SF/flush/straight draw), draw 1.
  Dealer straight+: stand pat.
  Dealer two pair (± aces-up): stand pat.
  Dealer trips (± A/K): draw 2 (keep trips).
  Dealer one pair JJ–AA: draw 3 (keep the pair).

Cases 1–8 (+b/c complements) match docs/NEXT_STAGE_SHOWDOWN_MATRIX.md.
Cascade FFS13 is out of scope here.
"""

from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from fivecarddraw.cards import Card, card_from_id, hand_to_str
from fivecarddraw.hand_rank import (
    HandCategory,
    HandValue,
    can_open_jacks_or_better,
    evaluate_hand,
)
from fivecarddraw.validation.draw_call_odds import (
    FIRST_CALL_MIN_OUTS,
    FIRST_CALL_REQUIRED,
    DrawHandResult,
    build_keep4_outs_table,
    expand_keeps_to_hands,
)


# --- Opener classes (fine split above one pair) ---------------------------------

PAIR_CLASSES = ("pair_J", "pair_Q", "pair_K", "pair_A")
TWO_PAIR_CLASSES = ("two_pair", "two_pair_aces_up")
TRIPS_CLASSES = ("trips", "trips_K", "trips_A")
STRAIGHT_PLUS_CLASSES = (
    "straight",
    "flush",
    "full_house",
    "four_of_a_kind",
    "straight_flush",
    "five_aces",
)
OPENER_CLASSES = PAIR_CLASSES + TWO_PAIR_CLASSES + TRIPS_CLASSES + STRAIGHT_PLUS_CLASSES

_PAIR_RANK = {"pair_J": 11, "pair_Q": 12, "pair_K": 13, "pair_A": 14}
_CASE_IDS = (
    "1",
    "1b",
    "2",
    "3",
    "3b",
    "4",
    "4b",
    "5",
    "5c",
    "6",
    "6b",
    "6c",
    "7",
    "7b",
    "7c",
    "8",
    "8b",
    "8c",
)

CASE_DESCRIPTIONS = {
    "1": "Dealer straight+ beats drawer straight+",
    "1b": "Dealer straight+ beats drawer face-pair (not straight+)",
    "2": "Dealer straight+ loses to drawer straight+",
    "3": "Dealer starts <straight, improves to straight+, beats/ties drawer straight+",
    "3b": "Dealer starts <straight, improves to straight+, loses to drawer straight+",
    "4": "Dealer two pair/trips final beats drawer pair-only",
    "4b": "Dealer two pair/trips loses to drawer straight+",
    "5": "Dealer AA beats or ties drawer face pair",
    "5c": "Dealer AA loses to drawer straight+",
    "6": "Dealer KK beats or ties drawer face pair",
    "6b": "Dealer KK loses to higher drawer face pair",
    "6c": "Dealer KK loses to drawer straight+",
    "7": "Dealer QQ beats or ties drawer face pair",
    "7b": "Dealer QQ loses to higher drawer face pair",
    "7c": "Dealer QQ loses to drawer straight+",
    "8": "Dealer JJ ties drawer JJ",
    "8b": "Dealer JJ loses to higher drawer face pair",
    "8c": "Dealer JJ loses to drawer straight+",
}

DISCARD_POLICIES = {
    "caller": "keep4_draw1 (fixture 2:1 keep)",
    "dealer_straight_plus": "stand_pat",
    "dealer_two_pair": "stand_pat",
    "dealer_trips": "keep_trips_draw2",
    "dealer_one_pair": "keep_pair_draw3",
}


def classify_opener(cards: Iterable[Card]) -> str | None:
    """Return fine opener class, or None if not a jacks-or-better open."""
    cards_t = tuple(cards)
    if not can_open_jacks_or_better(cards_t):
        return None
    value = evaluate_hand(cards_t)
    cat = value.category
    if cat == HandCategory.ONE_PAIR:
        return {
            11: "pair_J",
            12: "pair_Q",
            13: "pair_K",
            14: "pair_A",
        }.get(value.tiebreak[0])
    if cat == HandCategory.TWO_PAIR:
        return "two_pair_aces_up" if value.tiebreak[0] == 14 else "two_pair"
    if cat == HandCategory.THREE_OF_A_KIND:
        trips = value.tiebreak[0]
        if trips == 14:
            return "trips_A"
        if trips == 13:
            return "trips_K"
        return "trips"
    if cat == HandCategory.STRAIGHT:
        return "straight"
    if cat == HandCategory.FLUSH:
        return "flush"
    if cat == HandCategory.FULL_HOUSE:
        return "full_house"
    if cat == HandCategory.FOUR_OF_A_KIND:
        return "four_of_a_kind"
    if cat == HandCategory.STRAIGHT_FLUSH:
        return "straight_flush"
    if cat == HandCategory.FIVE_ACES:
        return "five_aces"
    return None


def is_face_pair(value: HandValue) -> bool:
    return value.category == HandCategory.ONE_PAIR and value.tiebreak[0] >= 11


def is_pair_only(value: HandValue) -> bool:
    return value.category == HandCategory.ONE_PAIR


def is_straight_plus(value: HandValue) -> bool:
    return value.category >= HandCategory.STRAIGHT


# --- Discard / draw plans -------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DrawPlan:
    keep: tuple[Card, ...]
    n_draw: int

    @property
    def keep_ids(self) -> frozenset[int]:
        return frozenset(c.card_id for c in self.keep)


def _cards_of_rank(cards: Sequence[Card], rank: int) -> list[Card]:
    """Physical rank matches, plus bug when rank is Ace (bug may play as ace)."""
    out: list[Card] = []
    for c in cards:
        if c.is_bug and rank == 14:
            out.append(c)
        elif not c.is_bug and c.rank == rank:
            out.append(c)
    return out


def dealer_draw_plan(cards: Sequence[Card], opener_class: str) -> DrawPlan:
    """Pinned discard policy for the dealer opener."""
    cards_t = tuple(cards)
    if opener_class in STRAIGHT_PLUS_CLASSES or opener_class in TWO_PAIR_CLASSES:
        return DrawPlan(keep=cards_t, n_draw=0)

    value = evaluate_hand(cards_t)
    if opener_class in TRIPS_CLASSES:
        trips_rank = value.tiebreak[0]
        keep = tuple(_cards_of_rank(cards_t, trips_rank))
        if len(keep) != 3:
            # Bug completing trips oddly — fall back to stand.
            return DrawPlan(keep=cards_t, n_draw=0)
        return DrawPlan(keep=keep, n_draw=2)

    if opener_class in PAIR_CLASSES:
        pair_rank = value.tiebreak[0]
        keep = tuple(_cards_of_rank(cards_t, pair_rank))
        if len(keep) != 2:
            return DrawPlan(keep=cards_t, n_draw=0)
        return DrawPlan(keep=keep, n_draw=3)

    return DrawPlan(keep=cards_t, n_draw=0)


def caller_draw_plan(hand: DrawHandResult) -> DrawPlan:
    return DrawPlan(keep=hand.keep, n_draw=1)


# --- Callers --------------------------------------------------------------------


def load_call_2to1_hands(*, progress: bool = False) -> list[DrawHandResult]:
    table = build_keep4_outs_table(
        list(range(53)),
        min_outs=FIRST_CALL_MIN_OUTS,
        progress=progress,
    )
    hands = expand_keeps_to_hands(
        table,
        min_outs=FIRST_CALL_MIN_OUTS,
        required_equity=FIRST_CALL_REQUIRED,
    )
    return [h for h in hands if h.outs >= FIRST_CALL_MIN_OUTS]


# --- Inventory ------------------------------------------------------------------


def iter_opener_hands() -> Iterator[tuple[str, tuple[int, ...]]]:
    """Yield (class, sorted card_ids) for every open-legal five-card combo."""
    for combo in combinations(range(53), 5):
        cards = tuple(card_from_id(i) for i in combo)
        cls = classify_opener(cards)
        if cls is not None:
            yield cls, combo


def build_opener_inventory(
    *, progress: bool = False
) -> dict[str, list[tuple[int, ...]]]:
    inv: dict[str, list[tuple[int, ...]]] = {c: [] for c in OPENER_CLASSES}
    combos = combinations(range(53), 5)
    if progress:
        try:
            from tqdm import tqdm

            combos = tqdm(
                combos,
                total=2_869_685,
                desc="opener inventory",
                unit="hand",
            )
        except ImportError:
            pass
    for combo in combos:
        cards = tuple(card_from_id(i) for i in combo)
        cls = classify_opener(cards)
        if cls is not None:
            inv[cls].append(combo)
    return inv


# --- Showdown enumeration / MC --------------------------------------------------


@dataclass(slots=True)
class OutcomeAccum:
    weight: float = 0.0
    dealer_wins: float = 0.0
    ties: float = 0.0
    caller_wins: float = 0.0
    cases: Counter = None  # type: ignore[assignment]
    caller_final: Counter = None  # type: ignore[assignment]
    dealer_final_straight_plus: float = 0.0

    def __post_init__(self) -> None:
        if self.cases is None:
            self.cases = Counter()
        if self.caller_final is None:
            self.caller_final = Counter()

    def add(
        self,
        *,
        w: float,
        dealer_final: HandValue,
        caller_final: HandValue,
        opener_class: str,
        dealer_started_straight_plus: bool,
        dealer_started_two_pair_or_trips: bool,
        dealer_pair_rank: int | None,
    ) -> None:
        self.weight += w
        if dealer_final > caller_final:
            self.dealer_wins += w
            cmp = 1
        elif dealer_final < caller_final:
            self.caller_wins += w
            cmp = -1
        else:
            self.ties += w
            cmp = 0

        if is_straight_plus(caller_final):
            self.caller_final["straight_plus"] += w
        elif is_face_pair(caller_final):
            self.caller_final["face_pair"] += w
        elif is_pair_only(caller_final):
            self.caller_final["pair_low"] += w
        elif caller_final.category >= HandCategory.TWO_PAIR:
            self.caller_final["two_pair_or_trips"] += w
        else:
            self.caller_final["miss"] += w

        if is_straight_plus(dealer_final):
            self.dealer_final_straight_plus += w

        for case_id in _case_hits(
            opener_class=opener_class,
            dealer_started_straight_plus=dealer_started_straight_plus,
            dealer_started_two_pair_or_trips=dealer_started_two_pair_or_trips,
            dealer_pair_rank=dealer_pair_rank,
            dealer_final=dealer_final,
            caller_final=caller_final,
            cmp=cmp,
        ):
            self.cases[case_id] += w


def _case_hits(
    *,
    opener_class: str,
    dealer_started_straight_plus: bool,
    dealer_started_two_pair_or_trips: bool,
    dealer_pair_rank: int | None,
    dealer_final: HandValue,
    caller_final: HandValue,
    cmp: int,
) -> list[str]:
    hits: list[str] = []
    c_sp = is_straight_plus(caller_final)
    d_sp = is_straight_plus(dealer_final)
    c_fp = is_face_pair(caller_final)

    if dealer_started_straight_plus:
        if c_sp:
            if cmp > 0:
                hits.append("1")
            elif cmp < 0:
                hits.append("2")
            # chops omitted / lumped out
        elif c_fp and cmp > 0:
            hits.append("1b")

    if (not dealer_started_straight_plus) and d_sp and c_sp:
        if cmp >= 0:
            hits.append("3")
        else:
            hits.append("3b")

    if dealer_started_two_pair_or_trips:
        if is_pair_only(caller_final) and cmp > 0:
            hits.append("4")
        if c_sp and cmp < 0:
            hits.append("4b")

    if dealer_pair_rank is not None:
        # Map pair rank → case family 5=AA … 8=JJ
        family = {14: "5", 13: "6", 12: "7", 11: "8"}[dealer_pair_rank]
        if c_sp and cmp < 0:
            hits.append(f"{family}c")
        if c_fp:
            if dealer_pair_rank == 11:
                # JJ never beats a JoB pair; ties → 8, else loses to higher → 8b
                if cmp == 0:
                    hits.append("8")
                elif cmp < 0:
                    hits.append("8b")
            elif cmp >= 0:
                hits.append(family)
            elif cmp < 0 and dealer_pair_rank < 14:
                # loses to higher face pair (AA never has a higher face pair)
                hits.append(f"{family}b")

    return hits


def _remaining_ids(blocked: set[int]) -> list[int]:
    return [i for i in range(53) if i not in blocked]


def _eval_keep_plus(keep: Sequence[Card], drawn_ids: Sequence[int]) -> HandValue:
    cards = (*keep, *(card_from_id(i) for i in drawn_ids))
    return evaluate_hand(cards)


def showdown_pair_exact_caller_draw(
    *,
    dealer_cards: Sequence[Card],
    dealer_plan: DrawPlan,
    caller: DrawHandResult,
    opener_class: str,
    accum: OutcomeAccum,
) -> None:
    """Dealer stands (n_draw=0); exact average over caller's one-card draws."""
    assert dealer_plan.n_draw == 0
    blocked = {c.card_id for c in dealer_cards} | {c.card_id for c in caller.cards}
    rem = _remaining_ids(blocked)
    if not rem:
        return
    w_each = 1.0 / len(rem)
    dealer_final = evaluate_hand(dealer_plan.keep)
    started_sp = opener_class in STRAIGHT_PLUS_CLASSES
    started_tp = opener_class in TWO_PAIR_CLASSES or opener_class in TRIPS_CLASSES
    pair_rank = _PAIR_RANK.get(opener_class)

    for cid in rem:
        caller_final = _eval_keep_plus(caller.keep, (cid,))
        accum.add(
            w=w_each,
            dealer_final=dealer_final,
            caller_final=caller_final,
            opener_class=opener_class,
            dealer_started_straight_plus=started_sp,
            dealer_started_two_pair_or_trips=started_tp,
            dealer_pair_rank=pair_rank,
        )


def showdown_pair_mc_joint(
    *,
    dealer_cards: Sequence[Card],
    dealer_plan: DrawPlan,
    caller: DrawHandResult,
    opener_class: str,
    accum: OutcomeAccum,
    rng: random.Random,
    draws: int,
) -> None:
    """Sample joint draws when dealer also draws."""
    blocked = {c.card_id for c in dealer_cards} | {c.card_id for c in caller.cards}
    rem = _remaining_ids(blocked)
    need = dealer_plan.n_draw + 1  # caller always draws 1
    if len(rem) < need or draws <= 0:
        return
    w_each = 1.0 / draws
    started_sp = opener_class in STRAIGHT_PLUS_CLASSES
    started_tp = opener_class in TWO_PAIR_CLASSES or opener_class in TRIPS_CLASSES
    pair_rank = _PAIR_RANK.get(opener_class)
    caller_plan = caller_draw_plan(caller)

    for _ in range(draws):
        # Caller draws first (seat left of dealer), then dealer.
        pool = rem[:]
        rng.shuffle(pool)
        c_card = pool[0]
        d_cards = pool[1 : 1 + dealer_plan.n_draw]
        dealer_final = _eval_keep_plus(dealer_plan.keep, d_cards)
        caller_final = _eval_keep_plus(caller_plan.keep, (c_card,))
        accum.add(
            w=w_each,
            dealer_final=dealer_final,
            caller_final=caller_final,
            opener_class=opener_class,
            dealer_started_straight_plus=started_sp,
            dealer_started_two_pair_or_trips=started_tp,
            dealer_pair_rank=pair_rank,
        )


def _sample_disjoint_caller(
    callers: Sequence[DrawHandResult],
    dealer_ids: set[int],
    rng: random.Random,
    *,
    max_tries: int = 80,
) -> DrawHandResult | None:
    n = len(callers)
    for _ in range(max_tries):
        c = callers[rng.randrange(n)]
        if dealer_ids.isdisjoint(x.card_id for x in c.cards):
            return c
    # Fallback linear scan from random offset
    start = rng.randrange(n)
    for k in range(n):
        c = callers[(start + k) % n]
        if dealer_ids.isdisjoint(x.card_id for x in c.cards):
            return c
    return None


def simulate_class(
    opener_class: str,
    dealer_hands: Sequence[tuple[int, ...]],
    callers: Sequence[DrawHandResult],
    *,
    rng: random.Random,
    n_dealer: int,
    n_callers_per_dealer: int,
    mc_draws_when_dealer_draws: int,
) -> dict[str, Any]:
    """Combo-style MC/exact hybrid for one opener class."""
    accum = OutcomeAccum()
    if not dealer_hands or not callers:
        return _empty_class_payload(opener_class, n_dealer_combos=len(dealer_hands))

    # With replacement indices so rare classes (five_aces=1) still get weight.
    dealer_samples = [
        dealer_hands[rng.randrange(len(dealer_hands))] for _ in range(n_dealer)
    ]
    pair_weight = 0.0

    for ids in dealer_samples:
        cards = tuple(card_from_id(i) for i in ids)
        plan = dealer_draw_plan(cards, opener_class)
        d_set = set(ids)
        for _ in range(n_callers_per_dealer):
            caller = _sample_disjoint_caller(callers, d_set, rng)
            if caller is None:
                continue
            pair_weight += 1.0
            if plan.n_draw == 0:
                # Exact over remaining; scale so each (dealer,caller) pair
                # contributes 1.0 total weight regardless of deck size.
                before = accum.weight
                showdown_pair_exact_caller_draw(
                    dealer_cards=cards,
                    dealer_plan=plan,
                    caller=caller,
                    opener_class=opener_class,
                    accum=accum,
                )
                # showdown adds ~1.0 already (sum of 1/|rem|)
                del before
            else:
                showdown_pair_mc_joint(
                    dealer_cards=cards,
                    dealer_plan=plan,
                    caller=caller,
                    opener_class=opener_class,
                    accum=accum,
                    rng=rng,
                    draws=mc_draws_when_dealer_draws,
                )

    return _finalize_class_payload(
        opener_class,
        accum,
        n_dealer_combos=len(dealer_hands),
        n_dealer_samples=len(dealer_samples),
        n_caller_pairs=int(pair_weight),
        mc_draws_when_dealer_draws=mc_draws_when_dealer_draws,
    )


def _empty_class_payload(opener_class: str, *, n_dealer_combos: int) -> dict[str, Any]:
    return {
        "opener_class": opener_class,
        "n_dealer_combos": n_dealer_combos,
        "n_dealer_samples": 0,
        "n_caller_pairs": 0,
        "outcomes": {"dealer_wins": 0.0, "tie": 0.0, "caller_wins": 0.0},
        "cases": {cid: 0.0 for cid in _CASE_IDS},
        "caller_final": {},
        "dealer_final_straight_plus": 0.0,
    }


def _finalize_class_payload(
    opener_class: str,
    accum: OutcomeAccum,
    *,
    n_dealer_combos: int,
    n_dealer_samples: int,
    n_caller_pairs: int,
    mc_draws_when_dealer_draws: int,
) -> dict[str, Any]:
    w = accum.weight
    if w <= 0:
        return _empty_class_payload(opener_class, n_dealer_combos=n_dealer_combos)

    def p(x: float) -> float:
        return round(x / w, 6)

    cases = {cid: p(accum.cases.get(cid, 0.0)) for cid in _CASE_IDS}
    # Drop structurally impossible labels for readability? Keep zeros for pins.
    return {
        "opener_class": opener_class,
        "n_dealer_combos": n_dealer_combos,
        "n_dealer_samples": n_dealer_samples,
        "n_caller_pairs": n_caller_pairs,
        "total_outcome_weight": round(w, 4),
        "mc_draws_when_dealer_draws": mc_draws_when_dealer_draws,
        "outcomes": {
            "dealer_wins": p(accum.dealer_wins),
            "tie": p(accum.ties),
            "caller_wins": p(accum.caller_wins),
        },
        "cases": cases,
        "caller_final": {
            k: p(v) for k, v in sorted(accum.caller_final.items(), key=lambda kv: -kv[1])
        },
        "dealer_final_straight_plus": p(accum.dealer_final_straight_plus),
    }


# --- Payload / I/O --------------------------------------------------------------


DEFAULT_SEED = 20260808
DEFAULT_N_DEALER = 400
DEFAULT_N_CALLERS = 25
DEFAULT_MC_DRAWS = 8


def build_showdown_matrix_payload(
    *,
    seed: int = DEFAULT_SEED,
    n_dealer: int = DEFAULT_N_DEALER,
    n_callers_per_dealer: int = DEFAULT_N_CALLERS,
    mc_draws_when_dealer_draws: int = DEFAULT_MC_DRAWS,
    progress: bool = False,
    inventory: dict[str, list[tuple[int, ...]]] | None = None,
    callers: list[DrawHandResult] | None = None,
    classes: Sequence[str] | None = None,
) -> dict[str, Any]:
    rng = random.Random(seed)
    if callers is None:
        callers = load_call_2to1_hands(progress=progress)
    if inventory is None:
        inventory = build_opener_inventory(progress=progress)

    use_classes = list(classes) if classes else list(OPENER_CLASSES)
    rows = []
    for cls in use_classes:
        if progress:
            print(f"simulating {cls} ({len(inventory.get(cls, []))} combos)…")
        # Independent stream per class for stability when subsetting classes
        class_rng = random.Random(rng.random())
        rows.append(
            simulate_class(
                cls,
                inventory.get(cls, []),
                callers,
                rng=class_rng,
                n_dealer=n_dealer if cls != "five_aces" else max(n_dealer, 200),
                n_callers_per_dealer=n_callers_per_dealer,
                mc_draws_when_dealer_draws=mc_draws_when_dealer_draws,
            )
        )

    return {
        "meta": {
            "stakes": "$0.25 ante / $2-$4",
            "matchup": "dealer_opener_vs_one_2to1_drawing_caller",
            "caller_set": "call_2to1 (bug 2:1 + FFS16), 18396 combos",
            "deck_model": (
                "exact remaining deck after both hands (43 cards); "
                "caller draws first, then dealer if drawing"
            ),
            "outs_denominator_note": (
                "Pot-odds fixtures use outs/48; this showdown matrix uses "
                "exact card removal for both holdings."
            ),
            "discard_policies": DISCARD_POLICIES,
            "case_descriptions": CASE_DESCRIPTIONS,
            "seed": seed,
            "n_dealer_per_class": n_dealer,
            "n_callers_per_dealer": n_callers_per_dealer,
            "mc_draws_when_dealer_draws": mc_draws_when_dealer_draws,
            "cascade_ffs13": "deferred (deal rate ~0.03%)",
        },
        "opener_combo_counts": {c: len(inventory.get(c, [])) for c in OPENER_CLASSES},
        "rows": rows,
    }


def default_fixture_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "validation"
        / "showdown_matrix.json"
    )


def write_showdown_matrix_fixture(
    path: Path | None = None, **kwargs: Any
) -> Path:
    path = path or default_fixture_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_showdown_matrix_payload(**kwargs)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def load_showdown_matrix(path: Path | None = None) -> dict[str, Any]:
    path = path or default_fixture_path()
    return json.loads(path.read_text(encoding="utf-8"))


def write_markdown_table(payload: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Dealer vs 2:1 drawing-caller showdown matrix",
        "",
        f"Seed `{payload['meta']['seed']}`; "
        f"dealer samples/class `{payload['meta']['n_dealer_per_class']}`; "
        f"callers/dealer `{payload['meta']['n_callers_per_dealer']}`.",
        "",
        "Deck model: exact remaining after both hands (caller draws 1; "
        "dealer per pinned discard policy).",
        "",
        "| Opener | Combos | P(dealer wins) | P(tie) | P(caller wins) | "
        "1 | 2 | 1b | 4b | 5c/6c/7c/8c |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["rows"]:
        cases = row["cases"]
        # Pair rows: their *c; two_pair/trips: 4b; pat: case 2
        if row["opener_class"] in PAIR_CLASSES:
            sp_loss = cases.get(
                {"pair_A": "5c", "pair_K": "6c", "pair_Q": "7c", "pair_J": "8c"}[
                    row["opener_class"]
                ],
                0,
            )
        elif row["opener_class"] in TWO_PAIR_CLASSES + TRIPS_CLASSES:
            sp_loss = cases.get("4b", 0)
        else:
            sp_loss = cases.get("2", 0)

        o = row["outcomes"]
        lines.append(
            f"| {row['opener_class']} | {row['n_dealer_combos']} | "
            f"{o['dealer_wins']:.4f} | {o['tie']:.4f} | {o['caller_wins']:.4f} | "
            f"{cases.get('1', 0):.4f} | {cases.get('2', 0):.4f} | "
            f"{cases.get('1b', 0):.4f} | {cases.get('4b', 0):.4f} | "
            f"{sp_loss:.4f} |"
        )
    lines.append("")
    lines.append("Case IDs: see `docs/NEXT_STAGE_SHOWDOWN_MATRIX.md`.")
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def row_by_class(payload: dict[str, Any], opener_class: str) -> dict[str, Any]:
    for row in payload["rows"]:
        if row["opener_class"] == opener_class:
            return row
    raise KeyError(opener_class)


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(
        description="Dealer vs drawing-caller post-draw showdown matrix"
    )
    p.add_argument("-o", "--output", type=Path, default=None)
    p.add_argument("--also-outputs", action="store_true")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--n-dealer", type=int, default=DEFAULT_N_DEALER)
    p.add_argument("--n-callers", type=int, default=DEFAULT_N_CALLERS)
    p.add_argument("--mc-draws", type=int, default=DEFAULT_MC_DRAWS)
    p.add_argument(
        "--classes",
        type=str,
        default=None,
        help="Comma-separated opener classes (default: all)",
    )
    p.add_argument("--quick", action="store_true", help="Smaller sample for smoke runs")
    args = p.parse_args()

    n_dealer = 80 if args.quick else args.n_dealer
    n_callers = 10 if args.quick else args.n_callers
    mc_draws = 4 if args.quick else args.mc_draws
    classes = (
        [c.strip() for c in args.classes.split(",") if c.strip()]
        if args.classes
        else None
    )

    print("Loading 2:1 callers + building opener inventory (slow first)…")
    payload = build_showdown_matrix_payload(
        seed=args.seed,
        n_dealer=n_dealer,
        n_callers_per_dealer=n_callers,
        mc_draws_when_dealer_draws=mc_draws,
        progress=True,
        classes=classes,
    )
    path = args.output or default_fixture_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {path}")

    if args.also_outputs:
        out_json = Path("outputs/validation/showdown_matrix.json")
        out_md = Path("outputs/validation/showdown_matrix.md")
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        write_markdown_table(payload, out_md)
        print(f"Wrote {out_json}")
        print(f"Wrote {out_md}")

    print()
    print(f"{'class':<20} {'combos':>8} {'win':>8} {'tie':>8} {'lose':>8}")
    for row in payload["rows"]:
        o = row["outcomes"]
        print(
            f"{row['opener_class']:<20} {row['n_dealer_combos']:>8} "
            f"{o['dealer_wins']:>8.4f} {o['tie']:>8.4f} {o['caller_wins']:>8.4f}"
        )


if __name__ == "__main__":
    main()
