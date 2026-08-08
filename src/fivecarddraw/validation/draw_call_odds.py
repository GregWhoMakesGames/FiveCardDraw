"""Pot-odds analysis for one-card drawing callers facing an open.

Stakes: $0.25 ante × 8 (pot $2), $2/$4 limit.

Stage A — first caller vs open:
  Facing pot $4, call $2 → need 2:1 pot odds → equity ≥ 1/3.
  One-card draw approximation: outs / 48 ≥ 1/3 → outs ≥ 16.
  (Hero knows 5 cards; 48 unknown.)

Stage B — second caller after one drawing call:
  Facing pot $6, call $2 → need 3:1 → equity ≥ 1/4.
  Same independent-events approximation: outs / 48 ≥ 1/4 → outs ≥ 12.
  Do **not** use outs/43. Conditioning the denominator on other players'
  hole cards would assume those outs are absent from the deck; in other
  deals the same outs remain. Each drawer treats the other 48 cards as
  unknown.

Card removal still matters for **coexistence**: two players cannot both
hold the bug; a first caller who holds specific ranks/suits removes those
combos from the deal. Removal is applied when asking whether a 3:1 hand
can be dealt alongside a given 2:1 hand — not by shrinking the outs
denominator.

Outs: keep-4 + draw card evaluates to category ≥ straight.
Discard: exactly one card; maximize outs.
Callers: non-open-legal hands only.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations, product
from pathlib import Path
from typing import Iterable

from fivecarddraw.cards import BUG_ID, Card, card_from_id, hand_to_str
from fivecarddraw.hand_rank import HandCategory, can_open_jacks_or_better, evaluate_hand
from fivecarddraw.rules import DEFAULT_CONFIG, pot_odds_to_call


# Each player sees only their own 5 cards → 48 unknown for the one-card draw.
UNKNOWN_AFTER_HERO = 48

FIRST_CALL_POT = DEFAULT_CONFIG.starting_pot + DEFAULT_CONFIG.small_bet  # 4
FIRST_CALL_TO_CALL = DEFAULT_CONFIG.small_bet  # 2
FIRST_CALL_REQUIRED = pot_odds_to_call(FIRST_CALL_POT, FIRST_CALL_TO_CALL)  # 1/3

SECOND_CALL_POT = FIRST_CALL_POT + FIRST_CALL_TO_CALL  # 6
SECOND_CALL_TO_CALL = DEFAULT_CONFIG.small_bet
SECOND_CALL_REQUIRED = pot_odds_to_call(SECOND_CALL_POT, SECOND_CALL_TO_CALL)  # 1/4

FIRST_CALL_MIN_OUTS = 16  # 16/48 = 1/3
SECOND_CALL_MIN_OUTS = 12  # 12/48 = 1/4


@dataclass(frozen=True, slots=True)
class DrawHandResult:
    cards: tuple[Card, ...]
    discard: Card
    keep: tuple[Card, ...]
    outs: int
    undealt: int
    has_bug: bool
    draw_class: str

    @property
    def hit_prob(self) -> float:
        return self.outs / self.undealt if self.undealt else 0.0


def _windows() -> list[list[int]]:
    ws = [[h, h - 1, h - 2, h - 3, h - 4] for h in range(6, 15)]
    ws.append([14, 5, 4, 3, 2])
    return ws


_WINDOWS = _windows()


def _overlap(ranks: Iterable[int]) -> int:
    s = set(ranks)
    return max(len(s & set(w)) for w in _WINDOWS)


def classify_draw(keep: tuple[Card, ...]) -> str:
    has_bug = any(c.is_bug for c in keep)
    other = [c for c in keep if not c.is_bug]
    suits = [c.suit for c in other]
    max_suit = max(Counter(suits).values()) if suits else 0
    ov = _overlap(c.rank for c in other)
    if has_bug and max_suit >= 3 and ov >= 3:
        return "bug_sf_draw"
    if has_bug and max_suit >= 3:
        return "bug_flush_draw"
    if has_bug and ov >= 3:
        return "bug_straight_draw"
    if has_bug:
        return "bug_other_draw"
    if max_suit == 4 and ov >= 4:
        return "four_flush_straight"
    if max_suit == 4:
        return "four_flush"
    if ov >= 4:
        return "oesd_or_better"
    return "other"


def outs_set(keep_ids: tuple[int, ...], pool: set[int]) -> set[int]:
    keep = tuple(card_from_id(i) for i in keep_ids)
    out: set[int] = set()
    for cid in pool:
        if cid in keep_ids:
            continue
        if evaluate_hand((*keep, card_from_id(cid))).category >= HandCategory.STRAIGHT:
            out.add(cid)
    return out


def iter_interesting_keep4(pool: list[int]) -> Iterable[tuple[int, ...]]:
    """Yield structurally strong 4-card keeps from pool (sorted tuples)."""
    pool_set = set(pool)
    std = [i for i in pool if i != BUG_ID]
    has_bug = BUG_ID in pool_set
    seen: set[tuple[int, ...]] = set()

    def emit(ids: Iterable[int]) -> Iterable[tuple[int, ...]]:
        t = tuple(sorted(ids))
        if t not in seen and set(t) <= pool_set:
            seen.add(t)
            yield t

    if has_bug:
        for combo in combinations(std, 3):
            cards = [card_from_id(i) for i in combo]
            suits = [c.suit for c in cards]
            max_suit = max(Counter(suits).values())
            ov = _overlap(c.rank for c in cards)
            if max_suit >= 2 or ov >= 2:
                yield from emit((BUG_ID, *combo))

    for suit in range(4):
        suited = [i for i in std if i % 4 == suit]
        if len(suited) >= 4:
            for four in combinations(suited, 4):
                yield from emit(four)

    for window in _WINDOWS:
        for miss in window:
            hold = [r for r in window if r != miss]
            options = []
            ok = True
            for r in hold:
                choices = [i for i in std if i // 4 + 2 == r]
                if not choices:
                    ok = False
                    break
                options.append(choices)
            if not ok:
                continue
            for picks in product(*options):
                if len({card_from_id(i).suit for i in picks}) == 1:
                    continue
                yield from emit(picks)


def build_keep4_outs_table(
    pool: list[int],
    *,
    min_outs: int,
    progress: bool = True,
    desc: str = "keep4 outs",
) -> dict[tuple[int, ...], set[int]]:
    """Map keep4 → out card ids within pool, retaining those with ≥ min_outs."""
    pool_set = set(pool)
    table: dict[tuple[int, ...], set[int]] = {}
    keeps = list(iter_interesting_keep4(pool))
    iterator: Iterable[tuple[int, ...]] = keeps
    if progress:
        try:
            from tqdm import tqdm

            iterator = tqdm(keeps, desc=desc, unit="keep")
        except ImportError:
            pass
    for keep in iterator:
        outs = outs_set(keep, pool_set)
        if len(outs) >= min_outs:
            table[keep] = outs
    return table


def expand_keeps_to_hands(
    keep_outs: dict[tuple[int, ...], set[int]],
    *,
    min_outs: int,
    required_equity: float,
    unknown: int = UNKNOWN_AFTER_HERO,
) -> list[DrawHandResult]:
    """Add a discard to each strong keep4; keep non-opening hands meeting threshold.

    Hit probability uses outs / ``unknown`` with ``unknown`` = 48 (hero's five
    cards known; remaining deck treated as unknown — independent-events approx).
    """
    deck = set(range(53))
    best_for_hand: dict[frozenset[int], DrawHandResult] = {}

    for keep_ids, outs in keep_outs.items():
        keep_set = set(keep_ids)
        keep_cards = tuple(card_from_id(i) for i in keep_ids)
        for disc_id in deck:
            if disc_id in keep_set:
                continue
            hand_ids = frozenset((*keep_ids, disc_id))
            # Outs among the 48 cards not in this hand (discard is not drawable).
            live_outs = outs - {disc_id}
            n = len(live_outs)
            if n < min_outs:
                continue
            if n / unknown + 1e-15 < required_equity:
                continue
            cards = tuple(card_from_id(i) for i in sorted(hand_ids))
            if can_open_jacks_or_better(cards):
                continue
            cand = DrawHandResult(
                cards=cards,
                discard=card_from_id(disc_id),
                keep=keep_cards,
                outs=n,
                undealt=unknown,
                has_bug=BUG_ID in hand_ids,
                draw_class=classify_draw(keep_cards),
            )
            prev = best_for_hand.get(hand_ids)
            if prev is None or cand.outs > prev.outs:
                best_for_hand[hand_ids] = cand

    return list(best_for_hand.values())


def summarize_by_class(results: list[DrawHandResult]) -> list[dict]:
    groups: dict[str, list[DrawHandResult]] = defaultdict(list)
    for r in results:
        groups[f"{r.draw_class}|bug={r.has_bug}"].append(r)
    rows = []
    for key, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        outs_list = [r.outs for r in items]
        rows.append(
            {
                "class": key,
                "combos": len(items),
                "outs_min": min(outs_list),
                "outs_max": max(outs_list),
                "outs_avg": round(sum(outs_list) / len(outs_list), 3),
                "hit_prob_min": round(min(r.hit_prob for r in items), 5),
                "hit_prob_max": round(max(r.hit_prob for r in items), 5),
                "example": hand_to_str(items[0].cards),
                "example_discard": str(items[0].discard),
                "example_keep": hand_to_str(items[0].keep),
                "more_examples": [hand_to_str(r.cards) for r in items[1:4]],
            }
        )
    return rows


def max_outs_in_table(keep_outs: dict[tuple[int, ...], set[int]]) -> dict:
    if not keep_outs:
        return {"max_outs": 0, "example_keep": None}
    keep, outs = max(keep_outs.items(), key=lambda kv: len(kv[1]))
    n = len(outs)
    return {
        "max_outs": n,
        "example_keep": hand_to_str(tuple(card_from_id(i) for i in keep)),
        "hit_prob_vs_48": round(n / UNKNOWN_AFTER_HERO, 5),
        "meets_2to1": n / UNKNOWN_AFTER_HERO >= FIRST_CALL_REQUIRED,
        "meets_3to1": n / UNKNOWN_AFTER_HERO >= SECOND_CALL_REQUIRED,
    }


def _ids(hand: DrawHandResult) -> frozenset[int]:
    return frozenset(c.card_id for c in hand.cards)


def find_disjoint_pair(
    left: list[DrawHandResult], right: list[DrawHandResult]
) -> dict | None:
    for a in left:
        ba = _ids(a)
        for b in right:
            if a is b:
                continue
            if ba.isdisjoint(_ids(b)):
                return {
                    "hand_a": hand_to_str(a.cards),
                    "class_a": a.draw_class,
                    "outs_a": a.outs,
                    "has_bug_a": a.has_bug,
                    "hand_b": hand_to_str(b.cards),
                    "class_b": b.draw_class,
                    "outs_b": b.outs,
                    "has_bug_b": b.has_bug,
                }
    return None


def coexistence_among(hands: list[DrawHandResult]) -> dict:
    with_bug = [r for r in hands if r.has_bug]
    without = [r for r in hands if not r.has_bug]
    bug_nobug = find_disjoint_pair(with_bug, without)
    two_nobug = None
    for i, a in enumerate(without):
        ba = _ids(a)
        for b in without[i + 1 :]:
            if ba.isdisjoint(_ids(b)):
                two_nobug = {
                    "hand_a": hand_to_str(a.cards),
                    "class_a": a.draw_class,
                    "outs_a": a.outs,
                    "hand_b": hand_to_str(b.cards),
                    "class_b": b.draw_class,
                    "outs_b": b.outs,
                }
                break
        if two_nobug:
            break
    return {
        "two_bug_impossible": True,
        "bug_plus_nobug_possible": bug_nobug is not None,
        "bug_plus_nobug_example": bug_nobug,
        "two_nobug_possible": two_nobug is not None,
        "two_nobug_example": two_nobug,
        "bug_combo_count": len(with_bug),
        "nobug_combo_count": len(without),
    }


def analyze_cascade(
    first: list[DrawHandResult],
    second_candidates: list[DrawHandResult],
    *,
    progress: bool = True,
) -> dict:
    """Can a 3:1 draw (outs/48 ≥ 1/4) be dealt with a 2:1 first caller?

    Outs stay outs/48. Card removal = disjoint hole cards (esp. single bug).
    """
    first_bug = [r for r in first if r.has_bug]
    first_nobug = [r for r in first if not r.has_bug]
    second_bug = [r for r in second_candidates if r.has_bug]
    second_nobug = [r for r in second_candidates if not r.has_bug]

    # After a bug 2:1 call, only no-bug 3:1 hands can coexist.
    after_bug_pair = find_disjoint_pair(first_bug, second_nobug)
    # After a no-bug 2:1 call (if any), bug or no-bug 3:1 may coexist.
    after_nobug_with_bug_second = find_disjoint_pair(first_nobug, second_bug)
    after_nobug_with_nobug_second = find_disjoint_pair(first_nobug, second_nobug)

    strongest_bug = max(first_bug, key=lambda r: r.outs, default=None)
    after_bug_full: dict | None = None
    examples: list[dict] = []
    pair_class_counts: Counter[tuple[str, str]] = Counter()

    if strongest_bug is not None:
        blocked = _ids(strongest_bug)
        surviving = [s for s in second_nobug if blocked.isdisjoint(_ids(s))]
        after_bug_full = {
            "first_example": hand_to_str(strongest_bug.cards),
            "first_class": strongest_bug.draw_class,
            "first_outs": strongest_bug.outs,
            "second_combos_meeting_3to1_disjoint": len(surviving),
            "second_by_class": summarize_by_class(surviving),
            "second_outs_histogram": dict(
                sorted(Counter(s.outs for s in surviving).items())
            ),
            "note": (
                "Second hands keep outs/48; first caller's cards are not removed "
                "from the outs denominator. Only deal-disjointness is enforced "
                "(bug taken ⇒ no second bug draws)."
            ),
        }
        for s in surviving:
            pair_class_counts[(strongest_bug.draw_class, s.draw_class)] += 1
            if len(examples) < 20:
                examples.append(
                    {
                        "first_hand": hand_to_str(strongest_bug.cards),
                        "first_class": strongest_bug.draw_class,
                        "first_has_bug": True,
                        "second_hand": hand_to_str(s.cards),
                        "second_class": s.draw_class,
                        "second_has_bug": False,
                        "second_outs": s.outs,
                        "second_hit_prob": round(s.hit_prob, 5),
                    }
                )

    cascading = (
        after_bug_pair is not None
        or after_nobug_with_bug_second is not None
        or after_nobug_with_nobug_second is not None
        or (
            after_bug_full is not None
            and after_bug_full["second_combos_meeting_3to1_disjoint"] > 0
        )
    )

    if progress:
        print(
            f"  3:1 candidates: {len(second_candidates)} "
            f"(bug={len(second_bug)}, no-bug={len(second_nobug)})"
        )
        if after_bug_full:
            print(
                "  after strongest bug 2:1 call, disjoint no-bug 3:1 combos: "
                f"{after_bug_full['second_combos_meeting_3to1_disjoint']}"
            )

    return {
        "approximation": "outs/48 for every caller (independent events)",
        "cascading_3to1_exists": cascading,
        "second_candidate_total": len(second_candidates),
        "second_with_bug": len(second_bug),
        "second_without_bug": len(second_nobug),
        "second_by_class": summarize_by_class(second_candidates),
        "second_outs_histogram": dict(
            sorted(Counter(r.outs for r in second_candidates).items())
        ),
        "disjoint_after_bug_first": after_bug_pair is not None,
        "disjoint_after_bug_first_example": after_bug_pair,
        "disjoint_after_nobug_first_with_bug_second": after_nobug_with_bug_second
        is not None,
        "disjoint_after_nobug_first_with_bug_second_example": after_nobug_with_bug_second,
        "disjoint_after_nobug_first_with_nobug_second": after_nobug_with_nobug_second
        is not None,
        "disjoint_after_nobug_first_with_nobug_second_example": after_nobug_with_nobug_second,
        "after_specific_bug_first_caller": after_bug_full,
        "first_second_class_pairs": [
            {"first": a, "second": b, "disjoint_pair_hits": n}
            for (a, b), n in pair_class_counts.most_common(30)
        ],
        "second_hit_examples": examples,
    }


def run_draw_call_odds_analysis(
    output_dir: str | Path = "outputs/validation",
    progress: bool = True,
    cascade_examples_per_class: int = 3,
) -> dict:
    del cascade_examples_per_class  # kept for CLI compat; cascade is full enum now
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    meta = {
        "ante": DEFAULT_CONFIG.ante,
        "players": DEFAULT_CONFIG.num_players,
        "starting_pot": DEFAULT_CONFIG.starting_pot,
        "small_bet": DEFAULT_CONFIG.small_bet,
        "outs_denominator": UNKNOWN_AFTER_HERO,
        "outs_denominator_rationale": (
            "Independent-events approximation: each hero knows only their 5 cards, "
            "so 48 cards are unknown. Do not use 43 (that would assume other "
            "players' hole cards are known missing from the draw deck)."
        ),
        "first_call": {
            "pot_facing": FIRST_CALL_POT,
            "to_call": FIRST_CALL_TO_CALL,
            "required_equity": FIRST_CALL_REQUIRED,
            "required_odds": "2:1",
            "unknown_cards": UNKNOWN_AFTER_HERO,
            "min_outs": FIRST_CALL_MIN_OUTS,
        },
        "second_call": {
            "pot_facing": SECOND_CALL_POT,
            "to_call": SECOND_CALL_TO_CALL,
            "required_equity": SECOND_CALL_REQUIRED,
            "required_odds": "3:1",
            "unknown_cards": UNKNOWN_AFTER_HERO,
            "min_outs": SECOND_CALL_MIN_OUTS,
        },
        "out_definition": "keep4 + draw => category >= straight",
        "discard_policy": "discard exactly one; maximize outs",
        "card_removal": (
            "Applied only for coexistence / deal-disjointness (especially the "
            "single bug), not by changing the outs denominator."
        ),
    }

    if progress:
        print("Building keep4 outs table (min 12 for 3:1; reuse for 2:1)…")
    # One table at the looser 3:1 threshold; filter up for 2:1.
    table = build_keep4_outs_table(
        list(range(53)),
        min_outs=SECOND_CALL_MIN_OUTS,
        progress=progress,
        desc="keep4 outs (≥12)",
    )
    if progress:
        print(f"  keep4s with ≥{SECOND_CALL_MIN_OUTS} outs: {len(table)}")
        print("Expanding keep4s to five-card non-opening hands…")

    # Expand once at the 3:1 threshold; Stage A is the ≥16-out subset.
    all_from_12 = expand_keeps_to_hands(
        table,
        min_outs=SECOND_CALL_MIN_OUTS,
        required_equity=SECOND_CALL_REQUIRED,
    )
    first = [h for h in all_from_12 if h.outs >= FIRST_CALL_MIN_OUTS]
    second = all_from_12

    first_summary = summarize_by_class(first)
    bug_n = sum(1 for r in first if r.has_bug)
    nobug_n = len(first) - bug_n
    if progress:
        print(f"  2:1 combos: {len(first)} (bug={bug_n}, no-bug={nobug_n})")
        print(f"  3:1 combos: {len(second)}")

    co_first = coexistence_among(first)

    if progress:
        print("Stage B: cascading 3:1 via coexistence (outs still /48)…")
    cascade = analyze_cascade(first, second, progress=progress)

    # No-bug-only bound: max outs among keeps that do not include the bug
    nobug_keeps = {k: v for k, v in table.items() if BUG_ID not in k}
    nobug_bound = max_outs_in_table(nobug_keeps)

    report = {
        "meta": meta,
        "stage_a_first_call_2to1": {
            "total_combos": len(first),
            "with_bug": bug_n,
            "without_bug": nobug_n,
            "by_class": first_summary,
            "outs_histogram": dict(sorted(Counter(r.outs for r in first).items())),
            "coexistence_among_2to1": co_first,
        },
        "stage_b_second_call_3to1": {
            **cascade,
            "bound_keep4_no_bug_in_keep": nobug_bound,
        },
        "decision_tree_implication": _decision_note(
            first_summary, cascade, co_first, nobug_bound
        ),
    }

    (output_path / "draw_call_odds.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    md = _format_markdown(report)
    (output_path / "draw_call_odds.md").write_text(md, encoding="utf-8")
    (output_path / "draw_call_odds_examples.json").write_text(
        json.dumps(
            {
                "first_call_by_class": first_summary,
                "second_call_by_class": cascade.get("second_by_class"),
                "cascade_examples": cascade.get("second_hit_examples", [])[:20],
                "after_bug_taken": cascade.get("after_specific_bug_first_caller"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    if progress:
        print(f"Wrote {output_path / 'draw_call_odds.json'}")
        print(f"Wrote {output_path / 'draw_call_odds.md'}")
        print()
        print(md)
    return report


def _decision_note(
    first_summary: list[dict],
    cascade: dict,
    co_first: dict,
    nobug_bound: dict,
) -> str:
    classes = (
        ", ".join(f"{r['class']} ({r['combos']})" for r in first_summary[:8]) or "(none)"
    )
    parts = [
        f"Stage-A 2:1 classes: {classes}.",
        f"No-bug keep4 max outs={nobug_bound.get('max_outs')} "
        f"(3:1 via outs/48: {nobug_bound.get('meets_3to1')}).",
        "Hit odds use outs/48 for every caller (independent events).",
    ]
    if cascade.get("cascading_3to1_exists"):
        parts.append(
            "A disjoint 3:1 drawing hand can be dealt with a 2:1 first caller "
            "(card removal = coexistence only). Cascading callers matter for the "
            "decision tree."
        )
    else:
        parts.append(
            "No deal-disjoint 3:1 draw found beside a 2:1 first caller — a small "
            "no-cascade tree may be viable."
        )
    if co_first.get("nobug_combo_count", 0) == 0:
        parts.append(
            "Only bug-assisted hands clear initial 2:1; two such callers cannot "
            "share the single bug."
        )
    return " ".join(parts)


def _format_markdown(report: dict) -> str:
    meta = report["meta"]
    a = report["stage_a_first_call_2to1"]
    b = report["stage_b_second_call_3to1"]
    co = a["coexistence_among_2to1"]
    lines = [
        "# Drawing-hand call odds ($0.25 / $2–$4)",
        "",
        "## Pot math & approximation",
        "",
        f"- Starting pot: ${meta['starting_pot']}",
        f"- Face open: pot ${meta['first_call']['pot_facing']}, call "
        f"${meta['first_call']['to_call']} → {meta['first_call']['required_odds']} "
        f"(equity ≥ {meta['first_call']['required_equity']:.4f}, "
        f"**outs ≥ {meta['first_call']['min_outs']}/48**)",
        f"- After one call: pot ${meta['second_call']['pot_facing']}, call "
        f"${meta['second_call']['to_call']} → {meta['second_call']['required_odds']} "
        f"(equity ≥ {meta['second_call']['required_equity']:.4f}, "
        f"**outs ≥ {meta['second_call']['min_outs']}/48**)",
        f"- Denominator: always **{meta['outs_denominator']}** unknown cards "
        "(independent events). Not 43.",
        f"- Card removal: {meta['card_removal']}",
        "- Outs: one-card draw to category ≥ straight; best single discard.",
        "",
        "## Stage A — call the open (2:1)",
        "",
        f"- **Total combos:** {a['total_combos']}",
        f"- With bug: {a['with_bug']}",
        f"- Without bug: {a['without_bug']}",
        f"- Outs histogram: `{a['outs_histogram']}`",
        "",
        "| Class | Combos | Outs min–max | Hit prob (outs/48) | Example |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for row in a["by_class"]:
        lines.append(
            f"| {row['class']} | {row['combos']} | {row['outs_min']}–{row['outs_max']} | "
            f"{row['hit_prob_min']:.3f}–{row['hit_prob_max']:.3f} | "
            f"`{row['example']}` discard `{row['example_discard']}` |"
        )

    lines += [
        "",
        "### Coexistence among 2:1 draws",
        "",
        "- Two bug 2:1 draws: impossible",
        f"- Bug + no-bug 2:1: **{co['bug_plus_nobug_possible']}**",
        f"- Two no-bug 2:1: **{co['two_nobug_possible']}**",
    ]

    br = b.get("bound_keep4_no_bug_in_keep", {})
    lines += [
        "",
        "## Stage B — cascading call (3:1, outs/48, coexistence removal)",
        "",
        f"- 3:1 candidate combos: **{b['second_candidate_total']}** "
        f"(bug={b['second_with_bug']}, no-bug={b['second_without_bug']})",
        f"- Cascading 3:1 exists (disjoint deal): **{b['cascading_3to1_exists']}**",
        f"- Disjoint no-bug 3:1 after a bug 2:1: **{b['disjoint_after_bug_first']}**",
        f"- Max no-bug keep4 outs: **{br.get('max_outs')}** (`{br.get('example_keep')}`) "
        f"→ {br.get('hit_prob_vs_48')} vs 48; meets 3:1: {br.get('meets_3to1')}",
        "",
        "| 3:1 class | Combos | Outs min–max | Example |",
        "| --- | ---: | --- | --- |",
    ]
    for row in b.get("second_by_class", []):
        lines.append(
            f"| {row['class']} | {row['combos']} | {row['outs_min']}–{row['outs_max']} | "
            f"`{row['example']}` |"
        )

    ab = b.get("after_specific_bug_first_caller")
    if ab:
        lines += [
            "",
            "### After strongest bug 2:1 call (disjoint no-bug 3:1 hands)",
            "",
            f"- First: `{ab['first_example']}` ({ab['first_class']}, outs={ab['first_outs']})",
            f"- Disjoint second combos at 3:1: **{ab['second_combos_meeting_3to1_disjoint']}**",
            f"- Histogram: `{ab['second_outs_histogram']}`",
            f"- Note: {ab['note']}",
            "",
            "| Second class | Combos | Outs min–max | Example |",
            "| --- | ---: | --- | --- |",
        ]
        for row in ab["second_by_class"]:
            lines.append(
                f"| {row['class']} | {row['combos']} | {row['outs_min']}–{row['outs_max']} | "
                f"`{row['example']}` |"
            )

    if b.get("disjoint_after_bug_first_example"):
        ex = b["disjoint_after_bug_first_example"]
        lines += [
            "",
            f"- Example pair: `{ex['hand_a']}` + `{ex['hand_b']}` "
            f"({ex['class_a']} → {ex['class_b']})",
        ]

    lines += [
        "",
        "## Decision-tree implication",
        "",
        report["decision_tree_implication"],
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(
        description="Drawing-hand 2:1 / cascading 3:1 pot-odds analysis (outs/48)."
    )
    p.add_argument("-o", "--output-dir", default="outputs/validation")
    p.add_argument(
        "--cascade-examples-per-class",
        type=int,
        default=3,
        help="Deprecated/ignored; cascade uses full coexistence enum.",
    )
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()
    run_draw_call_odds_analysis(
        output_dir=args.output_dir,
        progress=not args.quiet,
        cascade_examples_per_class=args.cascade_examples_per_class,
    )


if __name__ == "__main__":
    main()
