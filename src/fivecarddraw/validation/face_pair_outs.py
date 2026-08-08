"""Face-pair (JJ/QQ/KK/AA) one-card outs among drawing callers.

Among non-opening calling draws, count outs that finish as **exactly**
one pair of jacks, queens, kings, or aces (HandCategory.ONE_PAIR).

These outs are disjoint from straight+ outs for the studied keep shapes:
pairing a face does not simultaneously rank as straight/flush here (when
a card would make a straight+, evaluate_hand returns that higher category).

Stored for reuse in opener-vs-draw EV (pair-vs-JJ/QQ/KK paths).
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from fivecarddraw.cards import Card, card_from_id, hand_to_str
from fivecarddraw.hand_rank import HandCategory, evaluate_hand
from fivecarddraw.validation.draw_call_odds import (
    FIRST_CALL_MIN_OUTS,
    SECOND_CALL_MIN_OUTS,
    SECOND_CALL_REQUIRED,
    DrawHandResult,
    build_keep4_outs_table,
    expand_keeps_to_hands,
    outs_set,
)


FACE_PAIR_RANKS = {11: "JJ", 12: "QQ", 13: "KK", 14: "AA"}
TARGET_ORDER = ("AA", "KK", "QQ", "JJ")


@dataclass(frozen=True, slots=True)
class FacePairOuts:
    """Per-hand face-pair out breakdown for the best one-card keep."""

    target: str  # JJ/QQ/KK/AA
    out_ids: tuple[int, ...]
    pure_pair_out_ids: tuple[int, ...]  # not straight+ outs
    also_straight_plus_ids: tuple[int, ...]

    @property
    def n_outs(self) -> int:
        return len(self.out_ids)

    @property
    def n_pure(self) -> int:
        return len(self.pure_pair_out_ids)


def face_pair_outs_for_hand(hand: DrawHandResult) -> list[FacePairOuts]:
    held = {c.card_id for c in hand.cards}
    keep_ids = tuple(sorted(c.card_id for c in hand.keep))
    straight_plus = set(outs_set(keep_ids, set(range(53))) - held)

    by_target: dict[str, list[int]] = defaultdict(list)
    for cid in range(53):
        if cid in held:
            continue
        value = evaluate_hand((*hand.keep, card_from_id(cid)))
        if value.category != HandCategory.ONE_PAIR:
            continue
        pair = value.tiebreak[0]
        if pair not in FACE_PAIR_RANKS:
            continue
        by_target[FACE_PAIR_RANKS[pair]].append(cid)

    results: list[FacePairOuts] = []
    for target in TARGET_ORDER:
        ids = tuple(sorted(by_target.get(target, [])))
        if not ids:
            continue
        pure = tuple(c for c in ids if c not in straight_plus)
        both = tuple(c for c in ids if c in straight_plus)
        results.append(
            FacePairOuts(
                target=target,
                out_ids=ids,
                pure_pair_out_ids=pure,
                also_straight_plus_ids=both,
            )
        )
    return results


def _load_caller_sets() -> dict[str, list[DrawHandResult]]:
    table = build_keep4_outs_table(
        list(range(53)),
        min_outs=SECOND_CALL_MIN_OUTS,
        progress=False,
    )
    hands = expand_keeps_to_hands(
        table,
        min_outs=SECOND_CALL_MIN_OUTS,
        required_equity=SECOND_CALL_REQUIRED,
    )
    return {
        "call_2to1": [h for h in hands if h.outs >= FIRST_CALL_MIN_OUTS],
        "bug_2to1": [h for h in hands if h.has_bug and h.outs >= FIRST_CALL_MIN_OUTS],
        "ffs16": [
            h
            for h in hands
            if (not h.has_bug)
            and h.draw_class == "four_flush_straight"
            and h.outs == 16
        ],
        "ffs13": [
            h
            for h in hands
            if (not h.has_bug)
            and h.draw_class == "four_flush_straight"
            and h.outs == 13
        ],
    }


def summarize_set(name: str, hands: list[DrawHandResult]) -> dict[str, Any]:
    n_with = 0
    by_target_hands = Counter()
    outs_dist: dict[str, Counter[int]] = defaultdict(Counter)
    pure_dist: dict[str, Counter[int]] = defaultdict(Counter)
    overlap_dist: dict[str, Counter[int]] = defaultdict(Counter)
    by_class_target: dict[str, Counter[str]] = defaultdict(Counter)
    fine = Counter()  # (draw_class, target, n_outs, n_pure, n_overlap) -> hands
    multi = Counter()  # frozenset of targets available on one hand
    examples: list[dict[str, Any]] = []
    seen_example_keys: set[tuple] = set()

    for hand in hands:
        fp = face_pair_outs_for_hand(hand)
        if not fp:
            continue
        n_with += 1
        targets = []
        for item in fp:
            targets.append(item.target)
            by_target_hands[item.target] += 1
            outs_dist[item.target][item.n_outs] += 1
            pure_dist[item.target][item.n_pure] += 1
            overlap_dist[item.target][len(item.also_straight_plus_ids)] += 1
            by_class_target[hand.draw_class][item.target] += 1
            key = (
                hand.draw_class,
                item.target,
                item.n_outs,
                item.n_pure,
                len(item.also_straight_plus_ids),
            )
            fine[key] += 1
            if key not in seen_example_keys and len(examples) < 40:
                seen_example_keys.add(key)
                examples.append(
                    {
                        "hand": hand_to_str(hand.cards),
                        "keep": hand_to_str(hand.keep),
                        "discard": str(hand.discard),
                        "draw_class": hand.draw_class,
                        "straight_plus_outs": hand.outs,
                        "target": item.target,
                        "face_pair_outs": item.n_outs,
                        "pure_pair_outs": item.n_pure,
                        "also_straight_plus_outs": len(item.also_straight_plus_ids),
                        "example_out_cards": [str(card_from_id(c)) for c in item.out_ids],
                    }
                )
        multi[frozenset(targets)] += 1

    return {
        "set": name,
        "n_hands": len(hands),
        "n_with_face_pair_draw": n_with,
        "fraction_with_face_pair_draw": round(n_with / len(hands), 5) if hands else 0.0,
        "by_target": {
            t: {
                "hands_that_can_make": by_target_hands[t],
                "outs_dist": {str(k): v for k, v in sorted(outs_dist[t].items())},
                "pure_pair_outs_dist": {str(k): v for k, v in sorted(pure_dist[t].items())},
                "also_straight_plus_outs_dist": {
                    str(k): v for k, v in sorted(overlap_dist[t].items())
                },
                "note": (
                    "outs_dist: among hands that can make this pair, how many "
                    "one-card outs finish as exactly that one pair."
                ),
            }
            for t in TARGET_ORDER
        },
        "by_draw_class": {
            dc: dict(ctr) for dc, ctr in sorted(by_class_target.items())
        },
        "fine_buckets": [
            {
                "draw_class": dc,
                "target": tgt,
                "face_pair_outs": n_out,
                "pure_pair_outs": n_pure,
                "also_straight_plus_outs": n_ov,
                "hands": cnt,
            }
            for (dc, tgt, n_out, n_pure, n_ov), cnt in sorted(
                fine.items(), key=lambda kv: (-kv[1], kv[0][1], -kv[0][2])
            )
        ],
        "multi_target_hands": {
            "+".join(sorted(s, key=lambda x: TARGET_ORDER.index(x))): n
            for s, n in sorted(multi.items(), key=lambda kv: -kv[1])
        },
        "examples": examples,
        "observation": (
            "For these caller keeps, face-pair outs never coincide with "
            "straight+ outs (also_straight_plus_outs always 0): a card that "
            "makes a straight/flush ranks as that, not as one pair."
        ),
    }


def build_face_pair_outs_payload(*, progress: bool = False) -> dict[str, Any]:
    del progress
    sets = _load_caller_sets()
    summaries = {name: summarize_set(name, hs) for name, hs in sets.items()}
    return {
        "meta": {
            "out_definition": (
                "keep4 + draw => HandCategory.ONE_PAIR with pair rank in "
                "{J,Q,K,A}; higher categories (straight+) excluded from these outs"
            ),
            "caller_sets": {
                "call_2to1": "bug 2:1 + FFS16 (outs/48 ≥ 1/3)",
                "bug_2to1": "bug-assisted 2:1 only",
                "ffs16": "no-bug four_flush_straight with 16 outs",
                "ffs13": "no-bug four_flush_straight with 13 outs (cascade-only)",
            },
        },
        "sets": summaries,
    }


def default_fixture_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "validation"
        / "face_pair_outs.json"
    )


def write_face_pair_outs_fixture(path: Path | None = None) -> Path:
    path = path or default_fixture_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_face_pair_outs_payload()
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def load_face_pair_outs(path: Path | None = None) -> dict[str, Any]:
    path = path or default_fixture_path()
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Face-pair outs among drawing callers")
    p.add_argument("-o", "--output", type=Path, default=None)
    p.add_argument("--also-outputs", action="store_true")
    args = p.parse_args()

    print("Enumerating calling hands and face-pair outs (slow first run)…")
    payload = build_face_pair_outs_payload()
    path = args.output or default_fixture_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {path}")
    if args.also_outputs:
        out = Path("outputs/validation/face_pair_outs.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {out}")

    s = payload["sets"]["call_2to1"]
    print()
    print(f"call_2to1: {s['n_hands']} hands; "
          f"{s['n_with_face_pair_draw']} ({100*s['fraction_with_face_pair_draw']:.1f}%) "
          f"can make JJ/QQ/KK/AA as one pair")
    print()
    print(f"{'target':<6} {'hands':>8} {'outs dist':<20} {'pure outs dist'}")
    for t in TARGET_ORDER:
        row = s["by_target"][t]
        print(
            f"{t:<6} {row['hands_that_can_make']:>8} "
            f"{str(row['outs_dist']):<20} {row['pure_pair_outs_dist']}"
        )
    print()
    print("Fine buckets (draw_class × target × outs):")
    print(f"{'draw_class':<22} {'tgt':<4} {'outs':>5} {'hands':>7}")
    for row in s["fine_buckets"]:
        print(
            f"{row['draw_class']:<22} {row['target']:<4} "
            f"{row['face_pair_outs']:>5} {row['hands']:>7}"
        )


if __name__ == "__main__":
    main()
