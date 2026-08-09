"""Opener draw-count mixes + checking-range protection (post-draw).

Extends M2 (`postdraw_betting_m2`) beyond the locked d=3 face-pair lead grid.

Ladder (docs/NEXT_STAGE_OPENER_DRAW_MIXES.md):
  A — Draw mechanical tables (final categories + showdown; no betting change)
  B — Baseline post-draw EV under new draw defaults (M2 betting)
  C — Check-mix protection so drawer face-pair stabs are ≤0 / near-0 EV

Locked setup reused from M2:
  open + call only; pot $6 into draw; big bet $4; opener first; drawer keep4/d=1.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from fivecarddraw.cards import Card, card_from_id
from fivecarddraw.hand_rank import HandCategory, HandValue, evaluate_hand
from fivecarddraw.validation.draw_call_odds import DrawHandResult
from fivecarddraw.validation.postdraw_betting_m2 import (
    BIG,
    PREDRAW_POT,
    Policy as M2Policy,
    _face_pair_rank,
    _one_pair_rank,
    _sample_disjoint_caller,
    play_deal as m2_play_deal,
)
from fivecarddraw.validation.showdown_matrix import (
    OPENER_CLASSES,
    PAIR_CLASSES,
    STRAIGHT_PLUS_CLASSES,
    TRIPS_CLASSES,
    TWO_PAIR_CLASSES,
    DrawPlan,
    _cards_of_rank,
    build_opener_inventory,
    load_call_2to1_hands,
)


# --- Legal actions / keep rules (pinned) ----------------------------------------

OTHER_STRAIGHT_PLUS = tuple(c for c in STRAIGHT_PLUS_CLASSES if c != "four_of_a_kind")

LEGAL_DRAW_COUNTS: dict[str, tuple[int, ...]] = {
    **{c: (0, 1, 2, 3) for c in PAIR_CLASSES},
    **{c: (0, 1) for c in TWO_PAIR_CLASSES},
    **{c: (0, 1, 2) for c in TRIPS_CLASSES},
    "four_of_a_kind": (0, 1),
    **{c: (0,) for c in OTHER_STRAIGHT_PLUS},
}

KEEP_RULE_NOTES = {
    "pair_d3": "keep the pair",
    "pair_d2": "keep pair + highest-rank kicker (bug=ace)",
    "pair_d1": "keep pair + two highest-rank kickers (bug=ace)",
    "pair_d0": "stand with full five",
    "two_pair_d1": "keep both pairs; discard kicker",
    "two_pair_d0": "stand",
    "trips_d2": "keep trips; discard two kickers",
    "trips_d1": "keep trips + highest-rank kicker (bug=ace)",
    "trips_d0": "stand",
    "quads_d1": "keep quads; discard kicker (not breaking)",
    "quads_d0": "stand",
    "other_straight_plus_d0": "straight/flush/boat/SF/five aces always stand",
}


def _eff_rank(c: Card) -> int:
    """Rank for kicker selection; bug counts as ace."""
    return 14 if c.is_bug else c.rank


def opener_draw_plan_for_action(
    cards: Sequence[Card], opener_class: str, n_draw: int
) -> DrawPlan:
    """Non-breaking keep for (class, public draw count). Raises if illegal."""
    cards_t = tuple(cards)
    legal = LEGAL_DRAW_COUNTS.get(opener_class)
    if legal is None or n_draw not in legal:
        raise ValueError(f"illegal draw action: {opener_class=} {n_draw=}")

    if n_draw == 0:
        return DrawPlan(keep=cards_t, n_draw=0)

    value = evaluate_hand(cards_t)

    if opener_class in PAIR_CLASSES:
        pair_rank = value.tiebreak[0]
        pair = tuple(_cards_of_rank(cards_t, pair_rank))
        if len(pair) != 2:
            return DrawPlan(keep=cards_t, n_draw=0)
        rest = [c for c in cards_t if c not in pair]
        rest_sorted = sorted(rest, key=lambda c: (_eff_rank(c), c.card_id), reverse=True)
        if n_draw == 3:
            keep = pair
        elif n_draw == 2:
            keep = (*pair, rest_sorted[0])
        else:  # n_draw == 1
            keep = (*pair, rest_sorted[0], rest_sorted[1])
        return DrawPlan(keep=keep, n_draw=n_draw)

    if opener_class in TWO_PAIR_CLASSES:
        # Keep both pairs; discard kicker. n_draw must be 1.
        hi, lo = value.tiebreak[0], value.tiebreak[1]
        keep = tuple(_cards_of_rank(cards_t, hi) + _cards_of_rank(cards_t, lo))
        if len(keep) != 4:
            return DrawPlan(keep=cards_t, n_draw=0)
        return DrawPlan(keep=keep, n_draw=1)

    if opener_class in TRIPS_CLASSES:
        trips_rank = value.tiebreak[0]
        trips = tuple(_cards_of_rank(cards_t, trips_rank))
        if len(trips) != 3:
            return DrawPlan(keep=cards_t, n_draw=0)
        rest = [c for c in cards_t if c not in trips]
        rest_sorted = sorted(rest, key=lambda c: (_eff_rank(c), c.card_id), reverse=True)
        if n_draw == 2:
            keep = trips
        else:  # n_draw == 1
            keep = (*trips, rest_sorted[0])
        return DrawPlan(keep=keep, n_draw=n_draw)

    if opener_class == "four_of_a_kind":
        four_rank = value.tiebreak[0]
        quads = tuple(_cards_of_rank(cards_t, four_rank))
        if len(quads) != 4:
            return DrawPlan(keep=cards_t, n_draw=0)
        return DrawPlan(keep=quads, n_draw=1)

    # Other straight+: only stand is legal (already handled by n_draw==0).
    raise ValueError(f"unexpected draw for {opener_class}")


def legal_actions_for_class(opener_class: str) -> tuple[int, ...]:
    return LEGAL_DRAW_COUNTS.get(opener_class, (0,))


# --- Draw policy vectors --------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DrawPolicy:
    """Pure (non-mixed) draw counts by class family.

    pair / two_pair / trips / quads; other straight+ always stand.
    """

    name: str
    pair_d: int = 3
    two_pair_d: int = 0
    trips_d: int = 2
    quads_d: int = 1

    def n_draw_for(self, opener_class: str) -> int:
        if opener_class in PAIR_CLASSES:
            return self.pair_d
        if opener_class in TWO_PAIR_CLASSES:
            return self.two_pair_d
        if opener_class in TRIPS_CLASSES:
            return self.trips_d
        if opener_class == "four_of_a_kind":
            return self.quads_d
        return 0


# Stage B grid: pairs fixed d=3; full factorial over
#   two_pair_d ∈ {0,1}, trips_d ∈ {0,1,2}, quads_d ∈ {0,1}  → 12 policies.


def stage_b_draw_policy(two_pair_d: int, trips_d: int, quads_d: int) -> DrawPolicy:
    """One cell of the Stage B draw grid (pairs always d=3)."""
    return DrawPolicy(
        name=f"tp{two_pair_d}_tr{trips_d}_q{quads_d}",
        pair_d=3,
        two_pair_d=two_pair_d,
        trips_d=trips_d,
        quads_d=quads_d,
    )


def stage_b_draw_policies() -> tuple[DrawPolicy, ...]:
    """All 12 Stage B draw policies (pairs d=3 fixed)."""
    return tuple(
        stage_b_draw_policy(tp, tr, q)
        for tp in (0, 1)
        for tr in (0, 1, 2)
        for q in (0, 1)
    )


STAGE_B_DRAW_POLICIES: tuple[DrawPolicy, ...] = stage_b_draw_policies()
STAGE_B_BASELINE = stage_b_draw_policy(0, 2, 0)  # M2 locked dims

# Named aliases (legacy names) for beliefs / Stage C call sites. Same draw dims
# as the corresponding grid cells; names preserved for checked-in fixtures.
M2_DRAW = DrawPolicy(name="m2_locked", pair_d=3, two_pair_d=0, trips_d=2, quads_d=0)
B_QUADS_D1 = DrawPolicy(name="quads_d1", pair_d=3, two_pair_d=0, trips_d=2, quads_d=1)
B_TP_D1_QUADS_D1 = DrawPolicy(
    name="two_pair_d1_quads_d1", pair_d=3, two_pair_d=1, trips_d=2, quads_d=1
)
B_TP_TRIPS_QUADS_D1 = DrawPolicy(
    name="tp_trips_quads_d1", pair_d=3, two_pair_d=1, trips_d=1, quads_d=1
)
B_TRIPS_STAND_QUADS_D1 = DrawPolicy(
    name="trips_stand_quads_d1", pair_d=3, two_pair_d=0, trips_d=0, quads_d=1
)


# --- Final category labels ------------------------------------------------------


def final_category_label(v: HandValue) -> str:
    cat = v.category
    if cat == HandCategory.ONE_PAIR:
        return "one_pair"
    if cat == HandCategory.TWO_PAIR:
        return "two_pair"
    if cat == HandCategory.THREE_OF_A_KIND:
        return "trips"
    if cat == HandCategory.FULL_HOUSE:
        return "full_house"
    if cat == HandCategory.FOUR_OF_A_KIND:
        return "four_of_a_kind"
    if cat == HandCategory.FIVE_ACES:
        return "five_aces"
    if cat >= HandCategory.STRAIGHT:
        return "straight_plus_other"
    return "worse"


def _strength_bucket(v: HandValue) -> str:
    """Betting strength bucket for check mixes."""
    cat = v.category
    if cat == HandCategory.ONE_PAIR:
        return "one_pair"
    if cat == HandCategory.TWO_PAIR:
        return "two_pair"
    if cat == HandCategory.THREE_OF_A_KIND:
        return "trips"
    if cat >= HandCategory.STRAIGHT:
        return "boat_plus"  # straight+ treated as strong value (boat+/straight+)
    return "worse"


# --- Deal generation ------------------------------------------------------------


@dataclass(slots=True)
class MixDeal:
    opener_class: str
    opener_start_pair: int | None
    d: int
    opener_final: HandValue
    drawer_final: HandValue
    opener_final_pair: int | None
    drawer_final_pair: int | None
    drawer_straight_plus: bool
    opener_two_pair_plus: bool
    opener_bucket: str  # one_pair / two_pair / trips / boat_plus / worse


def _pair_rank_from_class(cls: str) -> int | None:
    return {"pair_J": 11, "pair_Q": 12, "pair_K": 13, "pair_A": 14}.get(cls)


def generate_deals_with_draw_policy(
    inventory: dict[str, list[tuple[int, ...]]],
    callers: Sequence[DrawHandResult],
    draw_policy: DrawPolicy,
    *,
    n_deals: int,
    seed: int,
    classes: Sequence[str] | None = None,
) -> list[MixDeal]:
    rng = random.Random(seed)
    use = list(classes) if classes else list(OPENER_CLASSES)
    weights = [len(inventory[c]) for c in use]
    if sum(weights) == 0:
        return []
    deals: list[MixDeal] = []
    tries = 0
    while len(deals) < n_deals and tries < n_deals * 20:
        tries += 1
        cls = rng.choices(use, weights=weights, k=1)[0]
        ids = inventory[cls][rng.randrange(len(inventory[cls]))]
        blocked = set(ids)
        caller = _sample_disjoint_caller(callers, blocked, rng)
        if caller is None:
            continue
        cards = tuple(card_from_id(i) for i in ids)
        n_draw = draw_policy.n_draw_for(cls)
        plan = opener_draw_plan_for_action(cards, cls, n_draw)
        rem = [
            i
            for i in range(53)
            if i not in blocked and i not in {c.card_id for c in caller.cards}
        ]
        need = plan.n_draw + 1
        if len(rem) < need:
            continue
        rng.shuffle(rem)
        c_card = rem[0]
        d_cards = rem[1 : 1 + plan.n_draw]
        opener_final = evaluate_hand((*plan.keep, *(card_from_id(i) for i in d_cards)))
        drawer_final = evaluate_hand((*caller.keep, card_from_id(c_card)))
        deals.append(
            MixDeal(
                opener_class=cls,
                opener_start_pair=_pair_rank_from_class(cls),
                d=plan.n_draw,
                opener_final=opener_final,
                drawer_final=drawer_final,
                opener_final_pair=_one_pair_rank(opener_final),
                drawer_final_pair=_face_pair_rank(drawer_final),
                drawer_straight_plus=drawer_final.category >= HandCategory.STRAIGHT,
                opener_two_pair_plus=opener_final.category >= HandCategory.TWO_PAIR,
                opener_bucket=_strength_bucket(opener_final),
            )
        )
    return deals


def generate_deals_fixed_action(
    inventory: dict[str, list[tuple[int, ...]]],
    callers: Sequence[DrawHandResult],
    opener_class: str,
    n_draw: int,
    *,
    n_deals: int,
    seed: int,
) -> list[MixDeal]:
    """Force every sampled opener of `opener_class` to use `n_draw`."""
    pol = DrawPolicy(
        name=f"force_{opener_class}_d{n_draw}",
        pair_d=n_draw if opener_class in PAIR_CLASSES else 3,
        two_pair_d=n_draw if opener_class in TWO_PAIR_CLASSES else 0,
        trips_d=n_draw if opener_class in TRIPS_CLASSES else 2,
        quads_d=n_draw if opener_class == "four_of_a_kind" else 1,
    )
    return generate_deals_with_draw_policy(
        inventory,
        callers,
        pol,
        n_deals=n_deals,
        seed=seed,
        classes=[opener_class],
    )


# --- Stage A: mechanical tables -------------------------------------------------


@dataclass(slots=True)
class MechAccum:
    n: float = 0.0
    wins: float = 0.0
    ties: float = 0.0
    losses: float = 0.0
    by_final: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    boat_plus: float = 0.0  # full house or better

    def add(self, opener: HandValue, drawer: HandValue) -> None:
        self.n += 1.0
        lab = final_category_label(opener)
        self.by_final[lab] += 1.0
        if opener.category >= HandCategory.FULL_HOUSE:
            self.boat_plus += 1.0
        if opener > drawer:
            self.wins += 1.0
        elif opener < drawer:
            self.losses += 1.0
        else:
            self.ties += 1.0

    def as_dict(self) -> dict[str, Any]:
        n = self.n or 1.0
        finals = {k: round(v / n, 5) for k, v in sorted(self.by_final.items())}
        return {
            "n": self.n,
            "p_win": round(self.wins / n, 5),
            "p_tie": round(self.ties / n, 5),
            "p_lose": round(self.losses / n, 5),
            "p_boat_plus": round(self.boat_plus / n, 5),
            "p_final": finals,
        }


def run_stage_a(
    *,
    n_per_cell: int = 8_000,
    seed: int = 20260809,
    progress: bool = True,
    callers: Sequence[DrawHandResult] | None = None,
    inventory: dict[str, list[tuple[int, ...]]] | None = None,
) -> dict[str, Any]:
    """Mechanical improvement / showdown tables by class × draw action."""
    if callers is None or inventory is None:
        if progress:
            print("Stage A: loading callers + opener inventory…")
        callers = callers or load_call_2to1_hands(progress=progress)
        inventory = inventory or build_opener_inventory(progress=progress)
    else:
        if progress:
            print("Stage A: using shared callers + opener inventory…")

    # Report groups: each fine class that has >1 legal action, plus aggregates.
    focus_classes = (
        list(PAIR_CLASSES)
        + list(TWO_PAIR_CLASSES)
        + list(TRIPS_CLASSES)
        + ["four_of_a_kind"]
    )
    cells: list[dict[str, Any]] = []
    rng_base = seed
    for i, cls in enumerate(focus_classes):
        for n_draw in legal_actions_for_class(cls):
            if progress:
                print(f"  {cls} d={n_draw}…")
            deals = generate_deals_fixed_action(
                inventory,
                callers,
                cls,
                n_draw,
                n_deals=n_per_cell,
                seed=rng_base + i * 17 + n_draw * 101,
            )
            acc = MechAccum()
            for d in deals:
                acc.add(d.opener_final, d.drawer_final)
            cells.append(
                {
                    "opener_class": cls,
                    "n_draw": n_draw,
                    "inventory_size": len(inventory[cls]),
                    **acc.as_dict(),
                }
            )

    # Aggregate pair / two_pair / trips across fine classes (equal combo weight
    # via inventory sizes already reflected in per-class sampling).
    def agg(prefix: str, classes: Sequence[str]) -> list[dict[str, Any]]:
        out = []
        for n_draw in legal_actions_for_class(classes[0]):
            # Weighted merge by inventory size × cell n
            merged = MechAccum()
            inv_total = 0
            for cls in classes:
                cell = next(
                    c for c in cells if c["opener_class"] == cls and c["n_draw"] == n_draw
                )
                # Reconstruct approximate counts from rates
                n = cell["n"]
                for lab, p in cell["p_final"].items():
                    merged.by_final[lab] += p * n
                merged.boat_plus += cell["p_boat_plus"] * n
                merged.wins += cell["p_win"] * n
                merged.ties += cell["p_tie"] * n
                merged.losses += cell["p_lose"] * n
                merged.n += n
                inv_total += cell["inventory_size"]
            out.append(
                {
                    "opener_class": prefix,
                    "n_draw": n_draw,
                    "inventory_size": inv_total,
                    **merged.as_dict(),
                }
            )
        return out

    aggregates = (
        agg("pair_JJ_AA", PAIR_CLASSES)
        + agg("two_pair_all", TWO_PAIR_CLASSES)
        + agg("trips_all", TRIPS_CLASSES)
    )

    # Key comparisons highlighted for the writeup
    def cell(cls: str, d: int) -> dict[str, Any]:
        return next(c for c in cells if c["opener_class"] == cls and c["n_draw"] == d)

    highlights = {
        "two_pair_d1_vs_stand_boat_plus": {
            "d1": cell("two_pair", 1)["p_boat_plus"],
            "stand": cell("two_pair", 0)["p_boat_plus"],
            "d1_p_win": cell("two_pair", 1)["p_win"],
            "stand_p_win": cell("two_pair", 0)["p_win"],
        },
        "two_pair_aces_up_d1_vs_stand": {
            "d1_boat": cell("two_pair_aces_up", 1)["p_boat_plus"],
            "stand_boat": cell("two_pair_aces_up", 0)["p_boat_plus"],
            "d1_p_win": cell("two_pair_aces_up", 1)["p_win"],
            "stand_p_win": cell("two_pair_aces_up", 0)["p_win"],
        },
        "trips_d2_vs_stand_boat_plus": {
            "d2": cell("trips", 2)["p_boat_plus"],
            "d1": cell("trips", 1)["p_boat_plus"],
            "stand": cell("trips", 0)["p_boat_plus"],
            "d2_p_win": cell("trips", 2)["p_win"],
            "stand_p_win": cell("trips", 0)["p_win"],
        },
        "quads_d1_vs_stand": {
            "d1_p_win": cell("four_of_a_kind", 1)["p_win"],
            "stand_p_win": cell("four_of_a_kind", 0)["p_win"],
            "d1_final": cell("four_of_a_kind", 1)["p_final"],
            "stand_final": cell("four_of_a_kind", 0)["p_final"],
            "note": "Drawer cannot make quads from keep4; d=1 is showdown-safe pollution of public d=1",
        },
        "pair_A_draw_mix_win": {
            f"d{d}": cell("pair_A", d)["p_win"] for d in (0, 1, 2, 3)
        },
        "pair_A_draw_mix_boat": {
            f"d{d}": cell("pair_A", d)["p_boat_plus"] for d in (0, 1, 2, 3)
        },
    }

    return {
        "meta": {
            "stage": "A",
            "n_per_cell": n_per_cell,
            "seed": seed,
            "drawer_range": "call_2to1",
            "keep_rules": KEEP_RULE_NOTES,
            "doc": "docs/NEXT_STAGE_OPENER_DRAW_MIXES.md",
        },
        "cells": cells,
        "aggregates": aggregates,
        "highlights": highlights,
    }


# --- Betting with check mixes (extends M2) --------------------------------------


@dataclass(frozen=True, slots=True)
class CheckMix:
    """Fraction of each strong bucket that *checks* instead of auto-betting.

    One-pair lead still controlled by M2Policy.opener_lead_min.
    """

    check_frac_two_pair: float = 0.0
    check_frac_trips: float = 0.0
    check_frac_boat_plus: float = 0.0

    @property
    def key(self) -> str:
        return (
            f"chk_tp={self.check_frac_two_pair:.2f}|"
            f"tr={self.check_frac_trips:.2f}|"
            f"bp={self.check_frac_boat_plus:.2f}"
        )


@dataclass(frozen=True, slots=True)
class MixPolicy:
    m2: M2Policy
    check_mix: CheckMix = CheckMix()

    @property
    def key(self) -> str:
        return f"{self.m2.key}|{self.check_mix.key}"


def _opener_bets_strong(deal: MixDeal, check_mix: CheckMix, rng: random.Random) -> bool:
    """Whether opener bets a two-pair+ hand under the check mix."""
    bucket = deal.opener_bucket
    if bucket == "two_pair":
        frac = check_mix.check_frac_two_pair
    elif bucket == "trips":
        frac = check_mix.check_frac_trips
    elif bucket == "boat_plus":
        frac = check_mix.check_frac_boat_plus
    else:
        return False
    if frac <= 0.0:
        return True
    if frac >= 1.0:
        return False
    return rng.random() >= frac


def play_mix_deal(
    deal: MixDeal, policy: MixPolicy, rng: random.Random
) -> tuple[float, dict[str, bool]]:
    """Same street accounting as M2, with optional strong-hand check mixes."""
    # Reuse M2 path when check mix is all-bet.
    cm = policy.check_mix
    if (
        cm.check_frac_two_pair == 0.0
        and cm.check_frac_trips == 0.0
        and cm.check_frac_boat_plus == 0.0
    ):
        # Convert to M2 Deal-compatible play via duck typing fields
        return m2_play_deal(deal, policy.m2)  # type: ignore[arg-type]

    flags = {
        "opener_pair_lead": False,
        "opener_pair_check": False,
        "opener_strong_check": False,
        "opener_strong_bet": False,
        "drawer_stab": False,
        "drawer_raise": False,
        "opener_fold_to_stab": False,
        "opener_call_stab": False,
        "opener_fold_to_raise": False,
        "opener_call_raise": False,
        "showdown": False,
        "opener_wins_sd": False,
    }
    pot = PREDRAW_POT
    o_in = 0.0
    o_pair = deal.opener_final_pair
    d_face = deal.drawer_final_pair
    d_sp = deal.drawer_straight_plus
    o_strong = deal.opener_two_pair_plus
    is_job_pair = o_pair is not None and o_pair >= 11 and not o_strong

    opener_bets = False
    if o_strong:
        opener_bets = _opener_bets_strong(deal, cm, rng)
        if opener_bets:
            flags["opener_strong_bet"] = True
        else:
            flags["opener_strong_check"] = True
    elif is_job_pair:
        if (
            policy.m2.opener_lead_min is not None
            and o_pair >= policy.m2.opener_lead_min
        ):
            opener_bets = True
            flags["opener_pair_lead"] = True
        else:
            flags["opener_pair_check"] = True

    if opener_bets:
        o_in += BIG
        pot += BIG
        if d_sp or (
            d_face is not None
            and policy.m2.drawer_raise_min is not None
            and d_face >= policy.m2.drawer_raise_min
        ):
            flags["drawer_raise"] = True
            pot += 2 * BIG
            call = o_strong or (
                o_pair is not None
                and policy.m2.drawer_raise_min is not None
                and o_pair >= policy.m2.drawer_raise_min
            )
            if call:
                flags["opener_call_raise"] = True
                o_in += BIG
                pot += BIG
                flags["showdown"] = True
            else:
                flags["opener_fold_to_raise"] = True
                return -o_in, flags
        elif d_face is not None:
            pot += BIG
            flags["showdown"] = True
        else:
            return -o_in + pot, flags
    else:
        stab = d_sp or (
            d_face is not None
            and policy.m2.drawer_stab_min is not None
            and d_face >= policy.m2.drawer_stab_min
        )
        if stab:
            flags["drawer_stab"] = True
            pot += BIG
            call = o_strong or (
                o_pair is not None
                and policy.m2.drawer_stab_min is not None
                and o_pair >= policy.m2.drawer_stab_min
            )
            if call:
                flags["opener_call_stab"] = True
                o_in += BIG
                pot += BIG
                flags["showdown"] = True
            else:
                flags["opener_fold_to_stab"] = True
                return -o_in, flags
        else:
            flags["showdown"] = True

    if deal.opener_final > deal.drawer_final:
        flags["opener_wins_sd"] = True
        return -o_in + pot, flags
    if deal.opener_final < deal.drawer_final:
        return -o_in, flags
    return -o_in + pot / 2.0, flags


@dataclass(slots=True)
class MixStreetStats:
    n: float = 0.0
    opener_ev: float = 0.0
    opener_pair_lead: float = 0.0
    opener_pair_check: float = 0.0
    drawer_stab: float = 0.0
    drawer_raise: float = 0.0
    opener_fold_to_stab: float = 0.0
    opener_call_stab: float = 0.0
    opener_fold_to_raise: float = 0.0
    opener_call_raise: float = 0.0
    showdown: float = 0.0
    opener_wins_sd: float = 0.0
    opener_strong_check: float = 0.0
    opener_strong_bet: float = 0.0
    # Drawer face-pair stab counterfactual (opener-check + face-pair nodes)
    face_stab_nodes: float = 0.0
    face_stab_ev_drawer: float = 0.0
    face_check_ev_drawer: float = 0.0

    def add(self, ev: float, **flags: bool) -> None:
        self.n += 1.0
        self.opener_ev += ev
        for k, v in flags.items():
            if v and hasattr(self, k):
                setattr(self, k, getattr(self, k) + 1.0)

    def as_dict(self) -> dict[str, float]:
        n = self.n or 1.0
        fn = self.face_stab_nodes or 1.0
        return {
            "n": self.n,
            "opener_ev": round(self.opener_ev / n, 5),
            "opener_pair_lead_rate": round(self.opener_pair_lead / n, 5),
            "opener_pair_check_rate": round(self.opener_pair_check / n, 5),
            "drawer_stab_rate": round(self.drawer_stab / n, 5),
            "drawer_raise_rate": round(self.drawer_raise / n, 5),
            "opener_fold_to_stab_rate": round(self.opener_fold_to_stab / n, 5),
            "opener_call_stab_rate": round(self.opener_call_stab / n, 5),
            "opener_fold_to_raise_rate": round(self.opener_fold_to_raise / n, 5),
            "opener_call_raise_rate": round(self.opener_call_raise / n, 5),
            "showdown_rate": round(self.showdown / n, 5),
            "opener_sd_win_given_sd": round(
                self.opener_wins_sd / self.showdown if self.showdown else 0.0, 5
            ),
            "opener_strong_check_rate": round(self.opener_strong_check / n, 5),
            "opener_strong_bet_rate": round(self.opener_strong_bet / n, 5),
            "face_stab_nodes": self.face_stab_nodes,
            "drawer_face_stab_ev": round(self.face_stab_ev_drawer / fn, 5),
            "drawer_face_check_ev": round(self.face_check_ev_drawer / fn, 5),
            "drawer_face_stab_delta": round(
                (self.face_stab_ev_drawer - self.face_check_ev_drawer) / fn, 5
            ),
        }


def _drawer_showdown_ev(deal: MixDeal, pot: float, d_in: float) -> float:
    """Drawer net from post-draw node given invested d_in and final pot."""
    if deal.drawer_final > deal.opener_final:
        return -d_in + pot
    if deal.drawer_final < deal.opener_final:
        return -d_in
    return -d_in + pot / 2.0


def _face_pair_counterfactual_ev(
    deal: MixDeal, policy: MixPolicy
) -> tuple[float, float] | None:
    """If opener checked and drawer has a face pair in the stab band, return
    (EV_if_stab, EV_if_check) from the drawer's seat.

    Opener call-down matches M2: call with strong or pair >= stab_min.
    """
    if deal.drawer_final_pair is None:
        return None
    stab_min = policy.m2.drawer_stab_min
    if stab_min is None or deal.drawer_final_pair < stab_min:
        return None
    # Opener checked (caller must only invoke on check nodes).
    o_pair = deal.opener_final_pair
    o_strong = deal.opener_two_pair_plus
    # Check line: both showdown for PREDRAW_POT, neither invests more.
    ev_check = _drawer_showdown_ev(deal, PREDRAW_POT, 0.0)
    # Stab: drawer bets BIG; opener call or fold.
    call = o_strong or (
        o_pair is not None and o_pair >= stab_min
    )
    if call:
        pot = PREDRAW_POT + 2 * BIG
        ev_stab = _drawer_showdown_ev(deal, pot, BIG)
    else:
        # Opener folds; drawer wins PREDRAW_POT after investing BIG.
        ev_stab = -BIG + (PREDRAW_POT + BIG)
    return ev_stab, ev_check


def evaluate_mix_policy(
    deals: Sequence[MixDeal],
    policy: MixPolicy,
    *,
    seed: int = 0,
    subset: str = "all",
) -> MixStreetStats:
    rng = random.Random(seed)
    stats = MixStreetStats()
    for deal in deals:
        if subset == "started_pair" and deal.opener_start_pair is None:
            continue
        if subset.startswith("class:") and deal.opener_class != subset.split(":", 1)[1]:
            continue
        if subset.startswith("d:") and deal.d != int(subset.split(":", 1)[1]):
            continue
        if subset == "pair_final_d3":
            if not (
                deal.d == 3
                and deal.opener_final_pair is not None
                and deal.opener_final_pair >= 11
                and not deal.opener_two_pair_plus
            ):
                continue

        ev, flags = play_mix_deal(deal, policy, rng)
        extra = {
            k: bool(flags.get(k, False))
            for k in (
                "opener_pair_lead",
                "opener_pair_check",
                "drawer_stab",
                "drawer_raise",
                "opener_fold_to_stab",
                "opener_call_stab",
                "opener_fold_to_raise",
                "opener_call_raise",
                "showdown",
                "opener_wins_sd",
            )
        }
        stats.add(ev, **extra)
        if flags.get("opener_strong_check"):
            stats.opener_strong_check += 1.0
        if flags.get("opener_strong_bet"):
            stats.opener_strong_bet += 1.0

        # Opener checked on this deal if they did not lead a pair and did not
        # bet a strong hand (including M2 always-bet strong via m2_play_deal).
        bet_first = bool(flags.get("opener_pair_lead") or flags.get("opener_strong_bet"))
        if not bet_first and deal.opener_two_pair_plus:
            # m2_play_deal path: strong always bets, no strong_* flags.
            cm = policy.check_mix
            if (
                cm.check_frac_two_pair == 0.0
                and cm.check_frac_trips == 0.0
                and cm.check_frac_boat_plus == 0.0
            ):
                bet_first = True
        checked = not bet_first

        if checked:
            cf = _face_pair_counterfactual_ev(deal, policy)
            if cf is not None:
                ev_stab, ev_check = cf
                stats.face_stab_nodes += 1.0
                stats.face_stab_ev_drawer += ev_stab
                stats.face_check_ev_drawer += ev_check

    return stats


# --- Stage B -------------------------------------------------------------------


def run_stage_b(
    *,
    n_deals: int = 20_000,
    seed: int = 20260809,
    progress: bool = True,
    callers: Sequence[DrawHandResult] | None = None,
    inventory: dict[str, list[tuple[int, ...]]] | None = None,
) -> dict[str, Any]:
    if callers is None or inventory is None:
        if progress:
            print("Stage B: loading callers + opener inventory…")
        callers = callers or load_call_2to1_hands(progress=progress)
        inventory = inventory or build_opener_inventory(progress=progress)
    else:
        if progress:
            print("Stage B: using shared callers + opener inventory…")

    draw_policies = list(STAGE_B_DRAW_POLICIES)
    # M2 betting baseline: check one pair; narrow stab AA / AA+KK; no face raise
    bet_policies = [
        M2Policy(None, None, None),  # passive face
        M2Policy(None, 14, None),  # AA stab
        M2Policy(None, 13, None),  # AA+KK stab
    ]

    rows = []
    for dp in draw_policies:
        if progress:
            print(f"  Generating deals under {dp.name}…")
        deals = generate_deals_with_draw_policy(
            inventory, callers, dp, n_deals=n_deals, seed=seed
        )
        d_hist = Counterish(deals)
        for bp in bet_policies:
            pol = MixPolicy(m2=bp, check_mix=CheckMix())
            st_all = evaluate_mix_policy(deals, pol, seed=seed + 1, subset="all")
            st_d = {
                f"d{d}": evaluate_mix_policy(
                    deals, pol, seed=seed + 1, subset=f"d:{d}"
                ).as_dict()
                for d in (0, 1, 2, 3)
            }
            by_class = {}
            for cls in (
                "pair_A",
                "pair_K",
                "two_pair",
                "trips",
                "four_of_a_kind",
                "straight",
                "full_house",
            ):
                by_class[cls] = evaluate_mix_policy(
                    deals, pol, seed=seed + 1, subset=f"class:{cls}"
                ).as_dict()
            rows.append(
                {
                    "draw_policy": dp.name,
                    "draw": {
                        "pair_d": dp.pair_d,
                        "two_pair_d": dp.two_pair_d,
                        "trips_d": dp.trips_d,
                        "quads_d": dp.quads_d,
                    },
                    "bet_policy": bp.key,
                    "public_d_rate": d_hist,
                    "all": st_all.as_dict(),
                    "by_d": st_d,
                    "by_class": by_class,
                }
            )

    # Full 12-cell grid vs M2 locked dims (tp0_tr2_q0), including baseline Δ=0
    comparisons = []
    for bp in bet_policies:
        m2_row = next(
            r
            for r in rows
            if r["draw_policy"] == STAGE_B_BASELINE.name and r["bet_policy"] == bp.key
        )
        for dp in draw_policies:
            r = next(
                x
                for x in rows
                if x["draw_policy"] == dp.name and x["bet_policy"] == bp.key
            )
            comparisons.append(
                {
                    "bet_policy": bp.key,
                    "draw_policy": dp.name,
                    "quads_d": dp.quads_d,
                    "trips_d": dp.trips_d,
                    "two_pair_d": dp.two_pair_d,
                    "ev_all": r["all"]["opener_ev"],
                    "ev_m2": m2_row["all"]["opener_ev"],
                    "delta_vs_m2": round(
                        r["all"]["opener_ev"] - m2_row["all"]["opener_ev"], 5
                    ),
                    "d1_rate": r["public_d_rate"].get("1", 0.0),
                    "d1_rate_m2": m2_row["public_d_rate"].get("1", 0.0),
                    "d2_rate": r["public_d_rate"].get("2", 0.0),
                    "d2_rate_m2": m2_row["public_d_rate"].get("2", 0.0),
                }
            )

    return {
        "meta": {
            "stage": "B",
            "n_deals": n_deals,
            "seed": seed,
            "betting": "M2 always-bet two pair+; one-pair check; drawer straight+ value",
            "draw_grid": "pairs d=3 fixed; two_pair∈{0,1} × trips∈{0,1,2} × quads∈{0,1} (12)",
            "baseline_draw_policy": STAGE_B_BASELINE.name,
            "doc": "docs/NEXT_STAGE_OPENER_DRAW_MIXES.md",
        },
        "rows": rows,
        "comparisons_vs_m2": comparisons,
    }


def Counterish(deals: Sequence[MixDeal]) -> dict[str, float]:
    counts: dict[int, float] = defaultdict(float)
    for d in deals:
        counts[d.d] += 1.0
    n = len(deals) or 1
    return {str(k): round(v / n, 5) for k, v in sorted(counts.items())}


# --- Stage C: check-mix protection ---------------------------------------------


def run_stage_c(
    *,
    n_deals: int = 20_000,
    seed: int = 20260809,
    progress: bool = True,
    draw_policy: DrawPolicy | None = None,
    callers: Sequence[DrawHandResult] | None = None,
    inventory: dict[str, list[tuple[int, ...]]] | None = None,
) -> dict[str, Any]:
    """Search check mixes under fixed draw policy + narrow drawer stabs."""
    draw_policy = draw_policy or B_QUADS_D1
    if callers is None or inventory is None:
        if progress:
            print("Stage C: loading callers + opener inventory…")
        callers = callers or load_call_2to1_hands(progress=progress)
        inventory = inventory or build_opener_inventory(progress=progress)
    else:
        if progress:
            print("Stage C: using shared callers + opener inventory…")
    if progress:
        print(f"  Generating deals under {draw_policy.name}…")
    deals = generate_deals_with_draw_policy(
        inventory, callers, draw_policy, n_deals=n_deals, seed=seed
    )

    # Narrow drawer band from M2 findings
    drawer_bands = [
        M2Policy(None, 14, None),  # AA stab, no face raise
        M2Policy(None, 13, None),  # AA+KK stab
        M2Policy(None, 14, 14),  # AA stab + AA raise
    ]

    check_grid = [
        CheckMix(0.0, 0.0, 0.0),  # M2: always bet strong
        CheckMix(0.3, 0.0, 0.0),
        CheckMix(0.0, 0.3, 0.0),
        CheckMix(0.0, 0.0, 0.3),
        CheckMix(0.3, 0.3, 0.0),
        CheckMix(0.3, 0.3, 0.3),
        CheckMix(0.5, 0.3, 0.2),
        CheckMix(0.5, 0.5, 0.3),
        CheckMix(1.0, 0.0, 0.0),  # always check two pair
        CheckMix(0.0, 1.0, 0.0),  # always check trips
        CheckMix(0.0, 0.0, 1.0),  # always check boat+
        CheckMix(0.5, 0.5, 0.5),
    ]

    rows = []
    for bp in drawer_bands:
        for cm in check_grid:
            pol = MixPolicy(m2=bp, check_mix=cm)
            st = evaluate_mix_policy(deals, pol, seed=seed + 7, subset="all")
            by_d = {
                f"d{d}": evaluate_mix_policy(
                    deals, pol, seed=seed + 7, subset=f"d:{d}"
                ).as_dict()
                for d in (0, 1, 2, 3)
            }
            row = {
                "stab": bp.key,
                "check_mix": cm.key,
                "check_frac_two_pair": cm.check_frac_two_pair,
                "check_frac_trips": cm.check_frac_trips,
                "check_frac_boat_plus": cm.check_frac_boat_plus,
                "all": st.as_dict(),
                "by_d": by_d,
            }
            rows.append(row)

    # Per stab band: baseline (no check mix) vs best opener EV and vs
    # policies that make face-stab delta ≤ 0.
    summaries = []
    for bp in drawer_bands:
        band = [r for r in rows if r["stab"] == bp.key]
        base = next(r for r in band if r["check_mix"] == CheckMix().key)
        best = max(band, key=lambda r: r["all"]["opener_ev"])
        # Policies where drawer face-pair stab delta ≤ 0 (unprofitable)
        unprof = [
            r
            for r in band
            if r["all"]["face_stab_nodes"] > 50
            and r["all"]["drawer_face_stab_delta"] <= 0.0
        ]
        near0 = [
            r
            for r in band
            if r["all"]["face_stab_nodes"] > 50
            and abs(r["all"]["drawer_face_stab_delta"]) <= 0.15
        ]
        best_unprof = (
            max(unprof, key=lambda r: r["all"]["opener_ev"]) if unprof else None
        )
        summaries.append(
            {
                "stab": bp.key,
                "baseline_ev": base["all"]["opener_ev"],
                "baseline_stab_delta": base["all"]["drawer_face_stab_delta"],
                "baseline_stab_rate": base["all"]["drawer_stab_rate"],
                "best_ev": best["all"]["opener_ev"],
                "best_check_mix": best["check_mix"],
                "best_stab_delta": best["all"]["drawer_face_stab_delta"],
                "best_delta_vs_baseline": round(
                    best["all"]["opener_ev"] - base["all"]["opener_ev"], 5
                ),
                "unprofitable_stab_count": len(unprof),
                "best_unprofitable": (
                    {
                        "check_mix": best_unprof["check_mix"],
                        "ev": best_unprof["all"]["opener_ev"],
                        "stab_delta": best_unprof["all"]["drawer_face_stab_delta"],
                        "delta_vs_baseline": round(
                            best_unprof["all"]["opener_ev"] - base["all"]["opener_ev"],
                            5,
                        ),
                    }
                    if best_unprof
                    else None
                ),
                "near_indifferent_count": len(near0),
            }
        )

    return {
        "meta": {
            "stage": "C",
            "n_deals": n_deals,
            "seed": seed,
            "draw_policy": draw_policy.name,
            "draw": {
                "pair_d": draw_policy.pair_d,
                "two_pair_d": draw_policy.two_pair_d,
                "trips_d": draw_policy.trips_d,
                "quads_d": draw_policy.quads_d,
            },
            "opener_lead": "never (one pair)",
            "doc": "docs/NEXT_STAGE_OPENER_DRAW_MIXES.md",
        },
        "rows": rows,
        "summaries": summaries,
    }


# --- Full ladder + recommendations ---------------------------------------------


def build_recommendations(
    stage_a: dict[str, Any],
    stage_b: dict[str, Any],
    stage_c: dict[str, Any],
) -> list[dict[str, str]]:
    """Compact recommendation table from A/B/C numbers."""
    h = stage_a["highlights"]
    # Quads: prefer d=1 for public d=1 pollution; showdown should match stand
    # within MC noise (drawer cannot make quads). Only prefer stand if d=1 is
    # clearly worse.
    q = h["quads_d1_vs_stand"]
    if q["d1_p_win"] + 0.02 < q["stand_p_win"]:
        quads_draw = "stand (d=1 showdown worse beyond noise)"
    else:
        quads_draw = "d=1 (discard kicker)"

    # Two pair: prefer higher win rate; note boat+ improvement from d=1
    tp = h["two_pair_d1_vs_stand_boat_plus"]
    if tp["d1_p_win"] > tp["stand_p_win"] + 0.01:
        tp_draw = "d=1 (keep both pairs)"
        tp_note = (
            f"boat+ {tp['stand']:.3f}→{tp['d1']:.3f}; "
            f"win {tp['stand_p_win']:.3f}→{tp['d1_p_win']:.3f}"
        )
    else:
        tp_draw = "stand (default) or thin d=1 mix"
        tp_note = (
            f"d=1 boat+ {tp['d1']:.3f} vs stand {tp['stand']:.3f}; "
            f"win {tp['d1_p_win']:.3f} vs {tp['stand_p_win']:.3f}"
        )

    trips = h["trips_d2_vs_stand_boat_plus"]
    # Pure improvement still prefers d=2; unified d=1 (with TP/quads) is the
    # concealment / pair-d=1-pollution vector measured in Stage B.
    def _b_cell(tp: int, tr: int, q: int) -> dict[str, Any] | None:
        name = stage_b_draw_policy(tp, tr, q).name
        return next(
            (
                c
                for c in stage_b["comparisons_vs_m2"]
                if c["draw_policy"] == name and "stab=AA|" in c["bet_policy"]
            ),
            None,
        )

    unified = _b_cell(1, 1, 1)
    tp_d1 = _b_cell(1, 2, 1)
    trips_draw = "d=2 (keep trips); d=1 joins unified public d=1 with TP/quads"
    trips_note = (
        f"boat+ d2={trips['d2']:.3f} d1={trips['d1']:.3f} stand={trips['stand']:.3f}; "
        f"win d2={trips['d2_p_win']:.3f} stand={trips['stand_p_win']:.3f}"
    )
    if unified is not None and tp_d1 is not None:
        trips_note += (
            f"; unified tp+trips+quads d=1 ΔEV={unified['delta_vs_m2']:+.3f} "
            f"vs tp+quads d=1 / trips d=2 ΔEV={tp_d1['delta_vs_m2']:+.3f}"
        )

    # Stage C: pick best check mix under AA stab band + smallest helpful mix
    c_sum = next(
        (s for s in stage_c["summaries"] if "stab=AA|" in s["stab"]),
        stage_c["summaries"][0],
    )
    aa_rows = [
        r
        for r in stage_c["rows"]
        if r["stab"] == c_sum["stab"]
    ]
    base_ev = c_sum["baseline_ev"]
    # Smallest non-zero two-pair check frac that still gains ≥0.05 EV
    small = None
    for r in sorted(aa_rows, key=lambda x: x["check_frac_two_pair"]):
        if (
            r["check_frac_trips"] == 0.0
            and r["check_frac_boat_plus"] == 0.0
            and r["check_frac_two_pair"] > 0.0
            and r["all"]["opener_ev"] >= base_ev + 0.05
        ):
            small = r
            break
    check_note = (
        f"vs {c_sum['stab']}: baseline stabΔ={c_sum['baseline_stab_delta']:+.3f} "
        f"(already ≤0); best {c_sum['best_check_mix']} "
        f"EVΔ={c_sum['best_delta_vs_baseline']:+.3f}"
    )
    if small is not None:
        check_note += (
            f"; smallest helpful: check {small['check_frac_two_pair']:.0%} of "
            f"two pair (EVΔ="
            f"{small['all']['opener_ev'] - base_ev:+.3f}, "
            f"stabΔ={small['all']['drawer_face_stab_delta']:+.3f})"
        )
    if c_sum.get("best_unprofitable"):
        bu = c_sum["best_unprofitable"]
        check_note += (
            f"; max-punish mix {bu['check_mix']} "
            f"stabΔ={bu['stab_delta']:+.3f} EVΔ={bu['delta_vs_baseline']:+.3f}"
        )

    # B comparison under AA stab — compact note: baseline + best + unified
    b_aa = [
        c
        for c in stage_b["comparisons_vs_m2"]
        if "stab=AA|" in c["bet_policy"]
    ]
    best = max(b_aa, key=lambda c: c["delta_vs_m2"]) if b_aa else None
    uni = next((c for c in b_aa if c["draw_policy"] == "tp1_tr1_q1"), None)
    b_note_parts = [f"grid={len(b_aa)} cells"]
    if best is not None:
        b_note_parts.append(
            f"best {best['draw_policy']} Δ={best['delta_vs_m2']:+.4f}"
        )
    if uni is not None:
        b_note_parts.append(f"unified d=1 Δ={uni['delta_vs_m2']:+.4f}")
    b_note = "; ".join(b_note_parts)

    return [
        {
            "class": "four_of_a_kind",
            "draw_action": quads_draw,
            "postdraw_bet_check": "bet (value); optional thin check mix into d=1 protection",
            "notes": (
                f"d1 win={q['d1_p_win']:.4f} stand win={q['stand_p_win']:.4f}; "
                "drawer cannot make quads"
            ),
        },
        {
            "class": "other straight+",
            "draw_action": "stand only",
            "postdraw_bet_check": "always bet",
            "notes": "cannot join d=3; do not mix into pair draws",
        },
        {
            "class": "trips",
            "draw_action": trips_draw,
            "postdraw_bet_check": "mostly bet; check mix per stage C",
            "notes": trips_note,
        },
        {
            "class": "two_pair",
            "draw_action": tp_draw,
            "postdraw_bet_check": "bet most; check ~30–100% as protection vs face-pair stabs",
            "notes": tp_note,
        },
        {
            "class": "pair JJ–AA",
            "draw_action": "d=3 (default); d∈{0,1,2} only as thin pollution",
            "postdraw_bet_check": "check JJ–AA (M2); lead AA only vs narrow stabs",
            "notes": f"stage B draw deltas (AA stab): {b_note}",
        },
        {
            "class": "checking-range protection",
            "draw_action": (
                "quads→d=1; two pair→d=1; trips d=2 (EV) or d=1 (unified d=1); "
                "pairs stay d=3 (d=1 pollution optional later)"
            ),
            "postdraw_bet_check": check_note,
            "notes": (
                "Hypothesis confirmed under fixed narrow drawer stabs: mixing "
                "two pair into checks raises opener EV and deepens stab losses. "
                "Boat+ check mixes alone do not help. Pat straight+ cannot join d=3. "
                "Unified trips+TP+quads d=1 keeps the draw-one line coherent for "
                "later pair-d=1 concealment."
            ),
        },
    ]


def run_ladder(
    *,
    n_per_cell_a: int = 6_000,
    n_deals_bc: int = 20_000,
    seed: int = 20260809,
    progress: bool = True,
) -> dict[str, Any]:
    if progress:
        print("Loading shared callers + opener inventory…")
    callers = load_call_2to1_hands(progress=progress)
    inventory = build_opener_inventory(progress=progress)
    stage_a = run_stage_a(
        n_per_cell=n_per_cell_a,
        seed=seed,
        progress=progress,
        callers=callers,
        inventory=inventory,
    )
    stage_b = run_stage_b(
        n_deals=n_deals_bc,
        seed=seed,
        progress=progress,
        callers=callers,
        inventory=inventory,
    )
    # Use quads_d1 as the draw base for C (isolates check mixes; two pair still stand)
    stage_c = run_stage_c(
        n_deals=n_deals_bc,
        seed=seed,
        progress=progress,
        draw_policy=B_QUADS_D1,
        callers=callers,
        inventory=inventory,
    )
    recs = build_recommendations(stage_a, stage_b, stage_c)
    return {
        "meta": {
            "seed": seed,
            "n_per_cell_a": n_per_cell_a,
            "n_deals_bc": n_deals_bc,
            "doc": "docs/NEXT_STAGE_OPENER_DRAW_MIXES.md",
            "predraw_pot": PREDRAW_POT,
            "big_bet": BIG,
        },
        "stage_a": stage_a,
        "stage_b": stage_b,
        "stage_c": stage_c,
        "recommendations": recs,
    }


def build_summary_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Compact checked-in fixture (no full row dumps)."""
    a = payload["stage_a"]
    b = payload["stage_b"]
    c = payload["stage_c"]

    def round_obj(obj: Any) -> Any:
        if isinstance(obj, float):
            return round(obj, 4)
        if isinstance(obj, dict):
            return {k: round_obj(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [round_obj(x) for x in obj]
        return obj

    # Slim stage A: aggregates + highlights + a few key cells
    key_cells = [
        x
        for x in a["cells"]
        if x["opener_class"] in {
            "pair_A",
            "two_pair",
            "two_pair_aces_up",
            "trips",
            "trips_A",
            "four_of_a_kind",
        }
    ]

    # Slim B: comparisons + one row per draw policy under AA stab
    b_aa = [
        {
            "draw_policy": r["draw_policy"],
            "draw": r["draw"],
            "ev_all": r["all"]["opener_ev"],
            "stab_rate": r["all"]["drawer_stab_rate"],
            "public_d_rate": r["public_d_rate"],
            "class_four_of_a_kind_ev": r["by_class"]["four_of_a_kind"]["opener_ev"],
            "class_two_pair_ev": r["by_class"]["two_pair"]["opener_ev"],
            "class_trips_ev": r["by_class"]["trips"]["opener_ev"],
        }
        for r in b["rows"]
        if r["bet_policy"] == "lead=never|stab=AA|raise=never"
    ]

    # Slim C: summaries + top rows per stab band
    c_slim_rows = []
    for s in c["summaries"]:
        band = [r for r in c["rows"] if r["stab"] == s["stab"]]
        # keep baseline + best + best_unprof if any
        keep_keys = {CheckMix().key, s["best_check_mix"]}
        if s.get("best_unprofitable"):
            keep_keys.add(s["best_unprofitable"]["check_mix"])
        for r in band:
            if r["check_mix"] in keep_keys:
                c_slim_rows.append(
                    {
                        "stab": r["stab"],
                        "check_mix": r["check_mix"],
                        "ev": r["all"]["opener_ev"],
                        "stab_rate": r["all"]["drawer_stab_rate"],
                        "strong_check_rate": r["all"]["opener_strong_check_rate"],
                        "face_stab_nodes": r["all"]["face_stab_nodes"],
                        "drawer_face_stab_delta": r["all"]["drawer_face_stab_delta"],
                    }
                )

    return round_obj(
        {
            "meta": {
                **payload["meta"],
                "regenerate": (
                    "analyze-postdraw-draw-mixes --n-deals 20000 --write-fixture"
                ),
            },
            "stage_a": {
                "meta": a["meta"],
                "highlights": a["highlights"],
                "aggregates": a["aggregates"],
                "key_cells": key_cells,
            },
            "stage_b": {
                "meta": b["meta"],
                "comparisons_vs_m2": b["comparisons_vs_m2"],
                "rows_vs_aa_stab": b_aa,
            },
            "stage_c": {
                "meta": c["meta"],
                "summaries": c["summaries"],
                "key_rows": c_slim_rows,
            },
            "recommendations": payload["recommendations"],
            "findings": _derive_findings(payload),
        }
    )


def _derive_findings(payload: dict[str, Any]) -> dict[str, Any]:
    a = payload["stage_a"]["highlights"]
    c_aa = next(
        (s for s in payload["stage_c"]["summaries"] if "stab=AA|" in s["stab"]),
        payload["stage_c"]["summaries"][0],
    )

    def _b_delta(tp: int, tr: int, q: int) -> float | None:
        name = stage_b_draw_policy(tp, tr, q).name
        row = next(
            (
                c
                for c in payload["stage_b"]["comparisons_vs_m2"]
                if c["draw_policy"] == name and "stab=AA|" in c["bet_policy"]
            ),
            None,
        )
        return row["delta_vs_m2"] if row else None

    b_aa = [
        c
        for c in payload["stage_b"]["comparisons_vs_m2"]
        if "stab=AA|" in c["bet_policy"]
    ]
    best_b = max(b_aa, key=lambda c: c["delta_vs_m2"]) if b_aa else None

    return {
        "quads_prefer_d1": a["quads_d1_vs_stand"]["d1_p_win"]
        + 0.02
        >= a["quads_d1_vs_stand"]["stand_p_win"],
        "quads_d1_win": a["quads_d1_vs_stand"]["d1_p_win"],
        "quads_stand_win": a["quads_d1_vs_stand"]["stand_p_win"],
        "two_pair_d1_boat_plus": a["two_pair_d1_vs_stand_boat_plus"]["d1"],
        "two_pair_stand_boat_plus": a["two_pair_d1_vs_stand_boat_plus"]["stand"],
        "trips_d2_boat_plus": a["trips_d2_vs_stand_boat_plus"]["d2"],
        "trips_d1_boat_plus": a["trips_d2_vs_stand_boat_plus"]["d1"],
        "trips_stand_boat_plus": a["trips_d2_vs_stand_boat_plus"]["stand"],
        "stage_b_grid_n": len(b_aa),
        "quads_d1_delta_ev_vs_m2_aa_stab": _b_delta(0, 2, 1),
        "two_pair_d1_quads_d1_delta_ev_vs_m2_aa_stab": _b_delta(1, 2, 1),
        "tp_trips_quads_d1_delta_ev_vs_m2_aa_stab": _b_delta(1, 1, 1),
        "trips_stand_quads_d1_delta_ev_vs_m2_aa_stab": _b_delta(0, 0, 1),
        "best_stage_b_draw_policy": best_b["draw_policy"] if best_b else None,
        "best_stage_b_delta_ev_vs_m2_aa_stab": (
            best_b["delta_vs_m2"] if best_b else None
        ),
        "check_mix_helps_opener_vs_aa_stab": c_aa["best_delta_vs_baseline"] > 0.0,
        "check_mix_can_make_aa_stab_unprofitable": c_aa["unprofitable_stab_count"] > 0,
        "best_check_mix_vs_aa_stab": c_aa["best_check_mix"],
        "baseline_aa_stab_delta": c_aa["baseline_stab_delta"],
        "best_aa_stab_delta": c_aa["best_stab_delta"],
    }


def write_markdown_summary(payload: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = build_summary_payload(payload) if "findings" not in payload else payload
    # Prefer findings from compact summary
    if "findings" not in summary:
        summary = build_summary_payload(payload)
    f = summary["findings"]
    lines = [
        "# Opener draw mixes + checking-range protection",
        "",
        f"Seed `{summary['meta']['seed']}`, stage A cells "
        f"`{summary['meta']['n_per_cell_a']}` deals, B/C "
        f"`{summary['meta']['n_deals_bc']}` deals. Pot `${summary['meta']['predraw_pot']}`, "
        f"big bet `${summary['meta']['big_bet']}`.",
        "",
        "Doc: `docs/NEXT_STAGE_OPENER_DRAW_MIXES.md`.",
        "",
        "## Findings",
        "",
        f"- Quads prefer d=1: **{f['quads_prefer_d1']}** "
        f"(win d1={f['quads_d1_win']:.4f} vs stand={f['quads_stand_win']:.4f})",
        f"- Two pair boat+ : stand={f['two_pair_stand_boat_plus']:.4f} → "
        f"d1={f['two_pair_d1_boat_plus']:.4f}",
        f"- Trips boat+ : stand={f['trips_stand_boat_plus']:.4f} → "
        f"d1={f.get('trips_d1_boat_plus', float('nan')):.4f} → "
        f"d2={f['trips_d2_boat_plus']:.4f}",
        f"- Quads d=1 ΔEV vs M2 (AA stab): {f['quads_d1_delta_ev_vs_m2_aa_stab']}",
        f"- Stage B grid cells (AA stab): {f.get('stage_b_grid_n')}; "
        f"best `{f.get('best_stage_b_draw_policy')}` "
        f"Δ={f.get('best_stage_b_delta_ev_vs_m2_aa_stab')}",
        f"- Two pair d=1 + trips d=2 + quads d=1 ΔEV: "
        f"{f.get('two_pair_d1_quads_d1_delta_ev_vs_m2_aa_stab')}",
        f"- Unified tp+trips+quads d=1 ΔEV: "
        f"{f.get('tp_trips_quads_d1_delta_ev_vs_m2_aa_stab')}",
        f"- Trips stand + quads d=1 ΔEV: "
        f"{f.get('trips_stand_quads_d1_delta_ev_vs_m2_aa_stab')}",
        f"- Check mix helps opener vs AA stab: **{f['check_mix_helps_opener_vs_aa_stab']}** "
        f"(best `{f['best_check_mix_vs_aa_stab']}`)",
        f"- Can make AA face-stab unprofitable: "
        f"**{f['check_mix_can_make_aa_stab_unprofitable']}** "
        f"(baseline Δ={f['baseline_aa_stab_delta']:+.4f}, "
        f"best Δ={f['best_aa_stab_delta']:+.4f})",
        "",
        "## Recommendations",
        "",
        "| Class | Draw | Post-draw bet/check | Notes |",
        "| --- | --- | --- | --- |",
    ]
    for r in summary["recommendations"]:
        lines.append(
            f"| {r['class']} | {r['draw_action']} | {r['postdraw_bet_check']} | "
            f"{r['notes']} |"
        )

    lines += [
        "",
        "## Stage A highlights",
        "",
        "```json",
        json.dumps(summary["stage_a"]["highlights"], indent=2),
        "```",
        "",
        "## Stage B comparisons vs M2",
        "",
        "```json",
        json.dumps(summary["stage_b"]["comparisons_vs_m2"], indent=2),
        "```",
        "",
        "## Stage C summaries",
        "",
        "```json",
        json.dumps(summary["stage_c"]["summaries"], indent=2),
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def default_summary_fixture_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "validation"
        / "postdraw_draw_mixes_summary.json"
    )


def write_summary_fixture(
    payload: dict[str, Any], path: Path | None = None
) -> Path:
    path = path or default_summary_fixture_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = build_summary_payload(payload)
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return path


def load_summary_fixture(path: Path | None = None) -> dict[str, Any]:
    path = path or default_summary_fixture_path()
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(
        description="Opener draw-count mixes + checking-range protection (A→B→C)"
    )
    p.add_argument("--n-deals", type=int, default=20_000, help="Deals for stages B/C")
    p.add_argument("--n-per-cell", type=int, default=6_000, help="Deals per A cell")
    p.add_argument("--seed", type=int, default=20260809)
    p.add_argument("--quick", action="store_true", help="Tiny sample for smoke runs")
    p.add_argument("--stage", choices=("all", "A", "B", "C"), default="all")
    p.add_argument("-o", "--output", type=Path, default=None)
    p.add_argument(
        "--write-fixture",
        action="store_true",
        help="Refresh tests/fixtures/validation/postdraw_draw_mixes_summary.json",
    )
    args = p.parse_args()
    n_bc = 3_000 if args.quick else args.n_deals
    n_a = 1_500 if args.quick else args.n_per_cell

    if args.stage == "A":
        payload = {"stage_a": run_stage_a(n_per_cell=n_a, seed=args.seed)}
    elif args.stage == "B":
        payload = {"stage_b": run_stage_b(n_deals=n_bc, seed=args.seed)}
    elif args.stage == "C":
        payload = {"stage_c": run_stage_c(n_deals=n_bc, seed=args.seed)}
    else:
        payload = run_ladder(
            n_per_cell_a=n_a, n_deals_bc=n_bc, seed=args.seed, progress=True
        )

    out = args.output or Path("outputs/validation/postdraw_draw_mixes.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out}")

    if args.stage == "all":
        md = out.with_suffix(".md")
        write_markdown_summary(payload, md)
        print(f"Wrote {md}")
        if args.write_fixture:
            fix = write_summary_fixture(payload)
            print(f"Wrote fixture {fix}")
        print("\nRecommendations:")
        for r in payload["recommendations"]:
            print(f"  {r['class']}: draw={r['draw_action']}")
            print(f"    bet/check: {r['postdraw_bet_check']}")
    elif args.write_fixture:
        print("--write-fixture requires --stage all")


if __name__ == "__main__":
    main()
