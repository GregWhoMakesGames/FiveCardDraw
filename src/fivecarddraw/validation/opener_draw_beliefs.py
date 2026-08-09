"""Step 0: public-d belief tables for opener draw policies.

Stores P(start class | d) under pure draw policies (exact from inventory
weights) and P(final bucket | d, start class) via MC deals vs 2:1 callers.

This is the handoff substrate for pair-concealment work: quantify how naked
d=3 is when pairs always draw three, and how d=2 / d=1 / d=0 masses change
when pairs divert off d=3.

See docs/NEXT_STAGE_PAIR_CONCEALMENT.md.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Sequence

from fivecarddraw.cards import card_from_id
from fivecarddraw.hand_rank import evaluate_hand
from fivecarddraw.validation.draw_call_odds import DrawHandResult
from fivecarddraw.validation.postdraw_betting_m2 import _sample_disjoint_caller
from fivecarddraw.validation.postdraw_draw_mixes import (
    B_QUADS_D1,
    B_TP_D1_QUADS_D1,
    M2_DRAW,
    DrawPolicy,
    _strength_bucket,
    final_category_label,
    opener_draw_plan_for_action,
)
from fivecarddraw.validation.showdown_matrix import (
    OPENER_CLASSES,
    PAIR_CLASSES,
    build_opener_inventory,
    load_call_2to1_hands,
)


# Policies to pin: baseline + pair-diversion counterfactuals for belief pollution.
PAIR_D3 = DrawPolicy(name="pairs_d3", pair_d=3, two_pair_d=0, trips_d=2, quads_d=1)
PAIR_D2 = DrawPolicy(name="pairs_d2", pair_d=2, two_pair_d=0, trips_d=2, quads_d=1)
PAIR_D1 = DrawPolicy(name="pairs_d1", pair_d=1, two_pair_d=0, trips_d=2, quads_d=1)
PAIR_STAND = DrawPolicy(name="pairs_stand", pair_d=0, two_pair_d=0, trips_d=2, quads_d=1)
# Rank-split sketch: only used as a named note in meta; beliefs for pure policies
# are enough for Step 0. Step 2 will mix ranks.

BELIEF_POLICIES: tuple[DrawPolicy, ...] = (
    M2_DRAW,
    B_QUADS_D1,
    B_TP_D1_QUADS_D1,
    PAIR_D3,
    PAIR_D2,
    PAIR_D1,
    PAIR_STAND,
)

FAMILY = {
    **{c: "pair" for c in PAIR_CLASSES},
    "two_pair": "two_pair",
    "two_pair_aces_up": "two_pair",
    "trips": "trips",
    "trips_K": "trips",
    "trips_A": "trips",
    "four_of_a_kind": "four_of_a_kind",
    "straight": "other_straight_plus",
    "flush": "other_straight_plus",
    "full_house": "other_straight_plus",
    "straight_flush": "other_straight_plus",
    "five_aces": "other_straight_plus",
}


def inventory_prior(
    inventory: dict[str, list[tuple[int, ...]]],
) -> dict[str, float]:
    total = sum(len(inventory[c]) for c in OPENER_CLASSES) or 1
    return {c: round(len(inventory[c]) / total, 6) for c in OPENER_CLASSES}


def exact_beliefs_given_d(
    inventory: dict[str, list[tuple[int, ...]]],
    draw_policy: DrawPolicy,
) -> dict[str, Any]:
    """Exact P(class|d) and P(family|d) under a pure (non-mixed) draw policy.

    Each class maps to one public d, so posterior is prior reweighted among
    classes that chose that d.
    """
    prior_counts = {c: float(len(inventory[c])) for c in OPENER_CLASSES}
    by_d_class: dict[str, dict[str, float]] = {str(d): {} for d in range(4)}
    by_d_family: dict[str, dict[str, float]] = {str(d): defaultdict(float) for d in range(4)}
    d_mass: dict[str, float] = {str(d): 0.0 for d in range(4)}

    for cls in OPENER_CLASSES:
        w = prior_counts[cls]
        if w <= 0:
            continue
        d = draw_policy.n_draw_for(cls)
        key = str(d)
        by_d_class[key][cls] = by_d_class[key].get(cls, 0.0) + w
        by_d_family[key][FAMILY[cls]] += w
        d_mass[key] += w

    def normalize(m: dict[str, float]) -> dict[str, float]:
        s = sum(m.values()) or 1.0
        return {k: round(v / s, 6) for k, v in sorted(m.items())}

    return {
        "draw_policy": draw_policy.name,
        "draw": {
            "pair_d": draw_policy.pair_d,
            "two_pair_d": draw_policy.two_pair_d,
            "trips_d": draw_policy.trips_d,
            "quads_d": draw_policy.quads_d,
        },
        "p_public_d": normalize(d_mass),
        "p_class_given_d": {
            d: normalize(by_d_class[d]) for d in ("0", "1", "2", "3") if d_mass[d] > 0
        },
        "p_family_given_d": {
            d: normalize(dict(by_d_family[d]))
            for d in ("0", "1", "2", "3")
            if d_mass[d] > 0
        },
        # Convenience: how naked is d=3?
        "d3_pair_family_mass": round(
            (
                by_d_family["3"]["pair"] / d_mass["3"]
                if d_mass["3"] > 0
                else 0.0
            ),
            6,
        ),
    }


def mc_final_given_class_d(
    inventory: dict[str, list[tuple[int, ...]]],
    callers: Sequence[DrawHandResult],
    *,
    opener_class: str,
    n_draw: int,
    n_deals: int,
    seed: int,
) -> dict[str, Any]:
    """MC P(final category / strength bucket) for forced (class, n_draw)."""
    rng = random.Random(seed)
    hands = inventory[opener_class]
    if not hands:
        return {"n": 0, "p_final": {}, "p_bucket": {}}
    final_c: dict[str, float] = defaultdict(float)
    bucket_c: dict[str, float] = defaultdict(float)
    n = 0.0
    tries = 0
    while n < n_deals and tries < n_deals * 20:
        tries += 1
        ids = hands[rng.randrange(len(hands))]
        blocked = set(ids)
        caller = _sample_disjoint_caller(callers, blocked, rng)
        if caller is None:
            continue
        cards = tuple(card_from_id(i) for i in ids)
        plan = opener_draw_plan_for_action(cards, opener_class, n_draw)
        rem = [
            i
            for i in range(53)
            if i not in blocked and i not in {c.card_id for c in caller.cards}
        ]
        need = plan.n_draw + 1
        if len(rem) < need:
            continue
        rng.shuffle(rem)
        d_cards = rem[1 : 1 + plan.n_draw]
        opener_final = evaluate_hand((*plan.keep, *(card_from_id(i) for i in d_cards)))
        final_c[final_category_label(opener_final)] += 1.0
        bucket_c[_strength_bucket(opener_final)] += 1.0
        n += 1.0

    def norm(m: dict[str, float]) -> dict[str, float]:
        s = n or 1.0
        return {k: round(v / s, 5) for k, v in sorted(m.items())}

    return {
        "opener_class": opener_class,
        "n_draw": n_draw,
        "n": n,
        "p_final": norm(final_c),
        "p_bucket": norm(bucket_c),
    }


def run_step0(
    *,
    n_per_cell: int = 4_000,
    seed: int = 20260809,
    progress: bool = True,
) -> dict[str, Any]:
    if progress:
        print("Step 0: loading callers + opener inventory…")
    callers = load_call_2to1_hands(progress=progress)
    inventory = build_opener_inventory(progress=progress)
    prior = inventory_prior(inventory)
    prior_counts = {c: len(inventory[c]) for c in OPENER_CLASSES}

    beliefs = [exact_beliefs_given_d(inventory, pol) for pol in BELIEF_POLICIES]

    # Final distributions for the concealment comparison cells
    focus = [
        ("pair_J", 3),
        ("pair_J", 2),
        ("pair_J", 1),
        ("pair_J", 0),
        ("pair_A", 3),
        ("pair_A", 2),
        ("pair_A", 1),
        ("pair_A", 0),
        ("pair_Q", 3),
        ("pair_Q", 2),
        ("pair_K", 3),
        ("pair_K", 2),
        ("two_pair", 0),
        ("two_pair", 1),
        ("trips", 2),
        ("trips", 1),
        ("trips", 0),
        ("four_of_a_kind", 1),
        ("four_of_a_kind", 0),
    ]
    finals = []
    for i, (cls, d) in enumerate(focus):
        if progress:
            print(f"  finals {cls} d={d}…")
        finals.append(
            mc_final_given_class_d(
                inventory,
                callers,
                opener_class=cls,
                n_draw=d,
                n_deals=n_per_cell,
                seed=seed + i * 97,
            )
        )

    # Headline comparisons for the doc / next agent
    by_name = {b["draw_policy"]: b for b in beliefs}

    def d3_mass(name: str) -> dict[str, Any]:
        b = by_name[name]
        return {
            "draw_policy": name,
            "p_d3": b["p_public_d"].get("3", 0.0),
            "d3_pair_family_mass": b["d3_pair_family_mass"],
            "p_family_given_d3": b["p_family_given_d"].get("3", {}),
            "p_family_given_d2": b["p_family_given_d"].get("2", {}),
            "p_family_given_d1": b["p_family_given_d"].get("1", {}),
            "p_family_given_d0": b["p_family_given_d"].get("0", {}),
        }

    highlights = {
        "inventory_prior_family": _family_prior(prior_counts),
        "d3_under_pairs_d3": d3_mass("pairs_d3"),
        "d3_under_pairs_d2": d3_mass("pairs_d2"),
        "d3_under_pairs_d1": d3_mass("pairs_d1"),
        "d3_under_pairs_stand": d3_mass("pairs_stand"),
        "note": (
            "Under pairs_d3, public d=3 is 100% pair-family by construction. "
            "Diverting all pairs to d=2/d=1/stand empties d=3 and pollutes those "
            "lines; Step 2 asks whether rank-selective diversion is +EV vs "
            "Exploit-d3 drawer stabs."
        ),
    }

    return {
        "meta": {
            "step": 0,
            "seed": seed,
            "n_per_cell": n_per_cell,
            "drawer_range": "call_2to1",
            "doc": "docs/NEXT_STAGE_PAIR_CONCEALMENT.md",
            "regenerate": "analyze-opener-draw-beliefs --write-fixture",
            "notes": [
                "P(class|d) is exact from inventory weights under pure draw policies",
                "P(final|class,d) is MC vs 2:1 callers with card removal",
                "Beliefs are opener-marginal (caller removal averaged in MC finals only)",
            ],
        },
        "inventory_counts": prior_counts,
        "inventory_prior": prior,
        "beliefs_by_policy": beliefs,
        "finals_by_class_d": finals,
        "highlights": highlights,
    }


def _family_prior(counts: dict[str, int]) -> dict[str, float]:
    fam: dict[str, float] = defaultdict(float)
    for c, n in counts.items():
        fam[FAMILY[c]] += float(n)
    s = sum(fam.values()) or 1.0
    return {k: round(v / s, 6) for k, v in sorted(fam.items())}


def build_summary_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Compact checked-in fixture."""

    def round_obj(obj: Any) -> Any:
        if isinstance(obj, float):
            return round(obj, 5)
        if isinstance(obj, dict):
            return {k: round_obj(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [round_obj(x) for x in obj]
        return obj

    # Keep family posteriors + d3 nakedness; drop full class posteriors for size
    slim_beliefs = []
    for b in payload["beliefs_by_policy"]:
        slim_beliefs.append(
            {
                "draw_policy": b["draw_policy"],
                "draw": b["draw"],
                "p_public_d": b["p_public_d"],
                "p_family_given_d": b["p_family_given_d"],
                "d3_pair_family_mass": b["d3_pair_family_mass"],
                # Keep fine class posterior only for d=3 (pair split) when present
                "p_class_given_d3": b["p_class_given_d"].get("3"),
            }
        )

    # Keep JJ/AA finals for all d; others as listed
    keep_finals = {
        (x["opener_class"], x["n_draw"])
        for x in payload["finals_by_class_d"]
        if x["opener_class"] in {
            "pair_J",
            "pair_A",
            "pair_Q",
            "pair_K",
            "two_pair",
            "trips",
            "four_of_a_kind",
        }
    }
    slim_finals = [
        x
        for x in payload["finals_by_class_d"]
        if (x["opener_class"], x["n_draw"]) in keep_finals
    ]

    return round_obj(
        {
            "meta": payload["meta"],
            "inventory_counts": payload["inventory_counts"],
            "inventory_prior_family": payload["highlights"]["inventory_prior_family"],
            "highlights": payload["highlights"],
            "beliefs_by_policy": slim_beliefs,
            "finals_by_class_d": slim_finals,
        }
    )


def default_fixture_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "validation"
        / "opener_draw_beliefs.json"
    )


def write_fixture(payload: dict[str, Any], path: Path | None = None) -> Path:
    path = path or default_fixture_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_summary_payload(payload), indent=2) + "\n", encoding="utf-8"
    )
    return path


def write_markdown(payload: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    h = payload["highlights"]
    lines = [
        "# Step 0: opener public-d belief tables",
        "",
        f"Seed `{payload['meta']['seed']}`, finals MC `{payload['meta']['n_per_cell']}`/cell.",
        "",
        "## Inventory family prior",
        "",
        "```json",
        json.dumps(h["inventory_prior_family"], indent=2),
        "```",
        "",
        "## How naked is d=3?",
        "",
        "| Pair draw policy | P(d=3) | P(pair family \\| d=3) |",
        "| --- | ---: | ---: |",
    ]
    for key in (
        "d3_under_pairs_d3",
        "d3_under_pairs_d2",
        "d3_under_pairs_d1",
        "d3_under_pairs_stand",
    ):
        r = h[key]
        lines.append(
            f"| `{r['draw_policy']}` | {r['p_d3']:.4f} | {r['d3_pair_family_mass']:.4f} |"
        )
    lines += [
        "",
        h["note"],
        "",
        "## Family posteriors (pairs_d3 = quads_d1 background)",
        "",
    ]
    b = next(x for x in payload["beliefs_by_policy"] if x["draw_policy"] == "pairs_d3")
    for d in ("0", "1", "2", "3"):
        fam = b["p_family_given_d"].get(d)
        if not fam:
            continue
        lines.append(f"- d={d}: `{json.dumps(fam)}`")
    lines += [
        "",
        "## JJ vs AA finals (improvement half)",
        "",
        "| Class | d | one_pair | two_pair | trips | boat+ish |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for cls in ("pair_J", "pair_A"):
        for d in (3, 2, 1, 0):
            cell = next(
                x
                for x in payload["finals_by_class_d"]
                if x["opener_class"] == cls and x["n_draw"] == d
            )
            pf = cell["p_final"]
            boat = (
                pf.get("full_house", 0)
                + pf.get("four_of_a_kind", 0)
                + pf.get("five_aces", 0)
            )
            lines.append(
                f"| {cls} | {d} | {pf.get('one_pair', 0):.3f} | "
                f"{pf.get('two_pair', 0):.3f} | {pf.get('trips', 0):.3f} | {boat:.3f} |"
            )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Step 0 opener public-d belief tables")
    p.add_argument("--n-per-cell", type=int, default=4_000)
    p.add_argument("--seed", type=int, default=20260809)
    p.add_argument("--quick", action="store_true")
    p.add_argument("-o", "--output", type=Path, default=None)
    p.add_argument("--write-fixture", action="store_true")
    args = p.parse_args()
    n = 1_000 if args.quick else args.n_per_cell
    payload = run_step0(n_per_cell=n, seed=args.seed, progress=True)
    out = args.output or Path("outputs/validation/opener_draw_beliefs.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md = out.with_suffix(".md")
    write_markdown(payload, md)
    print(f"Wrote {out}")
    print(f"Wrote {md}")
    if args.write_fixture:
        fix = write_fixture(payload)
        print(f"Wrote fixture {fix}")
    h = payload["highlights"]
    print("\nd=3 nakedness:")
    for key in (
        "d3_under_pairs_d3",
        "d3_under_pairs_d2",
        "d3_under_pairs_d1",
        "d3_under_pairs_stand",
    ):
        r = h[key]
        print(
            f"  {r['draw_policy']}: P(d=3)={r['p_d3']:.4f}  "
            f"P(pair|d=3)={r['d3_pair_family_mass']:.4f}"
        )


if __name__ == "__main__":
    main()
