"""Non-bluff max-EV grid: BN class × draw count vs 2:1 caller.

Heads-up laboratory (docs/NEXT_STAGE_NONBLUFF_EV.md):
  BN (seat 8) opened; one 2:1 drawing caller called (no pre-draw raise).
  Pot $6 into the draw; big bet $4 post-draw; opener acts first.

This module does **not** implement bluffing or check-protection mixes.
It pins an honest post-draw line and reports combo-weighted EV for each
legal (class, d) cell so later work can measure a bluff delta against
this baseline.

Honest policy (no bluffs / no sandbagging) — this is the **pre-C cell**:
  BN: always value-bet two pair+; check one pair JJ–AA (M2 default);
      never check-mix strong hands. Thin AA lead is a sensitivity only.
  Forward street after Stage C checks two pair (`STAGE_C_POLICY` / cap node).
  Do not rewrite this grid to absorb that mix.
  Caller: always bet/raise straight+ for value; when checked, stab AA
      (narrow value vs a checking pair); never raise a face pair into a
      two-pair+ betting range. Misses check or fold.
  Face-pair *calls* of a BN value-bet follow the M2 street (any J+ pair
      calls a bet) — folding that node is a later response-line knob.

Reuse: opener_draw_plan_for_action + M2 play_deal + showdown case ids 1–8c.
"""

from __future__ import annotations

import json
import random
import zlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from fivecarddraw.cards import card_from_id
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
from fivecarddraw.validation.postdraw_draw_mixes import (
    KEEP_RULE_NOTES,
    LEGAL_DRAW_COUNTS,
    DrawPolicy,
    legal_actions_for_class,
    opener_draw_plan_for_action,
)
from fivecarddraw.validation.showdown_matrix import (
    CASE_DESCRIPTIONS,
    OPENER_CLASSES,
    PAIR_CLASSES,
    STRAIGHT_PLUS_CLASSES,
    TRIPS_CLASSES,
    TWO_PAIR_CLASSES,
    _CASE_IDS,
    _PAIR_RANK,
    _case_hits,
    build_opener_inventory,
    load_call_2to1_hands,
)


DEFAULT_SEED = 20260901
DEFAULT_N_PER_CELL = 4_000

# Post-B locked draws for the caller-vs-range slice (not a search).
LOCKED_BN_DRAW = DrawPolicy(
    name="tp1_tr2_q1",
    pair_d=3,
    two_pair_d=1,
    trips_d=2,
    quads_d=1,
)

# Honest joint line. CheckMix is implicitly all-bet-strong via m2_play_deal.
HONEST_POLICY = M2Policy(
    opener_lead_min=None,  # check JJ–AA
    drawer_stab_min=14,  # AA value-stab when checked to
    drawer_raise_min=None,  # no face-pair raise; straight+ still raises
)
HONEST_POLICY_PASSIVE = M2Policy(None, None, None)  # straight+ only
HONEST_POLICY_LEAD_AA = M2Policy(14, 14, None)  # thin AA lead vs AA stab

CALLER_DRAW_CLASSES = (
    "bug_straight_draw",
    "bug_sf_draw",
    "four_flush_straight",
)
CALLER_ALL = "all_2to1"
# 2:1 keeps: d=1 is the non-breaking line; d=0 = stand with the dealt five.
CALLER_LEGAL_DRAW_COUNTS: dict[str, tuple[int, ...]] = {
    CALLER_ALL: (0, 1),
    **{c: (0, 1) for c in CALLER_DRAW_CLASSES},
}

# BN classes used for the caller d=0 vs d=1 fork (locked BN d).
CALLER_D_FORK_BN_CLASSES = (
    "pair_A",
    "pair_J",
    "two_pair",
    "trips",
    "straight",
)

POLICY_NOTES = (
    "No bluffs: BN never bets a weak final as two pair+; never checks two pair+ "
    "for deception (Stage C / later). Caller never bets a miss; never raises a "
    "face pair as if it were straight+.",
    "Value: BN bets two pair+; caller bets/raises straight+; caller stabs AA "
    "when checked (value vs a checking pair range).",
    "Behind: BN checks JJ–AA (M2); folds a one-pair hand to a straight+ stab "
    "unless the pair meets the matched call-down (AA vs AA stab).",
    "Bluff delta is out of scope — next after this EV table.",
)


# --- Deal generation (extends draw-mixes / M2 generator) ------------------------


@dataclass(slots=True)
class NonbluffDeal:
    """Duck-compatible with M2 Deal for play_deal; extra fields for cases."""

    opener_class: str
    caller_class: str
    d: int  # BN public draw count (M2 Deal field name)
    caller_d: int
    opener_start_pair: int | None
    opener_final: HandValue
    drawer_final: HandValue
    opener_final_pair: int | None
    drawer_final_pair: int | None
    drawer_straight_plus: bool
    opener_two_pair_plus: bool


def _pair_rank_from_class(cls: str) -> int | None:
    return _PAIR_RANK.get(cls)


def _cell_seed(base: int, *parts: object) -> int:
    payload = "|".join(str(p) for p in parts)
    return (base + (zlib.adler32(payload.encode("utf-8")) % 1_000_003)) % (2**31)


def group_callers_by_class(
    callers: Sequence[DrawHandResult],
) -> dict[str, list[DrawHandResult]]:
    groups: dict[str, list[DrawHandResult]] = {CALLER_ALL: list(callers)}
    for cls in CALLER_DRAW_CLASSES:
        groups[cls] = [h for h in callers if h.draw_class == cls]
    return groups


def generate_nonbluff_deals(
    inventory: dict[str, list[tuple[int, ...]]],
    callers: Sequence[DrawHandResult],
    opener_class: str,
    bn_d: int,
    *,
    caller_d: int = 1,
    caller_class: str = CALLER_ALL,
    n_deals: int,
    seed: int,
) -> list[NonbluffDeal]:
    """BN of `opener_class` uses `bn_d`; callers use keep-4 (`caller_d=1`) or stand."""
    if bn_d not in LEGAL_DRAW_COUNTS.get(opener_class, (0,)):
        raise ValueError(f"illegal BN draw: {opener_class=} {bn_d=}")
    if caller_d not in (0, 1):
        raise ValueError(f"illegal caller draw (2:1 keep-4 set): {caller_d=}")
    hands = inventory.get(opener_class, [])
    if not hands or not callers:
        return []
    rng = random.Random(seed)
    deals: list[NonbluffDeal] = []
    tries = 0
    while len(deals) < n_deals and tries < n_deals * 20:
        tries += 1
        ids = hands[rng.randrange(len(hands))]
        blocked = set(ids)
        caller = _sample_disjoint_caller(callers, blocked, rng)
        if caller is None:
            continue
        cards = tuple(card_from_id(i) for i in ids)
        plan = opener_draw_plan_for_action(cards, opener_class, bn_d)
        rem = [
            i
            for i in range(53)
            if i not in blocked and i not in {c.card_id for c in caller.cards}
        ]
        need = plan.n_draw + (1 if caller_d == 1 else 0)
        if len(rem) < need:
            continue
        if need:
            rng.shuffle(rem)
        if caller_d == 1:
            c_card = rem[0]
            d_cards = rem[1 : 1 + plan.n_draw]
            drawer_final = evaluate_hand((*caller.keep, card_from_id(c_card)))
        else:
            d_cards = rem[: plan.n_draw]
            drawer_final = evaluate_hand(caller.cards)
        opener_final = evaluate_hand(
            (*plan.keep, *(card_from_id(i) for i in d_cards))
        )
        deals.append(
            NonbluffDeal(
                opener_class=opener_class,
                caller_class=caller_class,
                d=plan.n_draw,
                caller_d=caller_d,
                opener_start_pair=_pair_rank_from_class(opener_class),
                opener_final=opener_final,
                drawer_final=drawer_final,
                opener_final_pair=_one_pair_rank(opener_final),
                drawer_final_pair=_face_pair_rank(drawer_final),
                drawer_straight_plus=drawer_final.category >= HandCategory.STRAIGHT,
                opener_two_pair_plus=opener_final.category >= HandCategory.TWO_PAIR,
            )
        )
    return deals


def generate_locked_range_deals(
    inventory: dict[str, list[tuple[int, ...]]],
    callers: Sequence[DrawHandResult],
    *,
    caller_d: int = 1,
    caller_class: str = CALLER_ALL,
    n_deals: int,
    seed: int,
    draw_policy: DrawPolicy = LOCKED_BN_DRAW,
    classes: Sequence[str] | None = None,
) -> list[NonbluffDeal]:
    """Combo-weighted BN range under a fixed draw policy vs one caller set."""
    rng = random.Random(seed)
    use = list(classes) if classes else list(OPENER_CLASSES)
    weights = [len(inventory[c]) for c in use]
    if sum(weights) == 0 or not callers:
        return []
    deals: list[NonbluffDeal] = []
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
        need = plan.n_draw + (1 if caller_d == 1 else 0)
        if len(rem) < need:
            continue
        if need:
            rng.shuffle(rem)
        if caller_d == 1:
            c_card = rem[0]
            d_cards = rem[1 : 1 + plan.n_draw]
            drawer_final = evaluate_hand((*caller.keep, card_from_id(c_card)))
        else:
            d_cards = rem[: plan.n_draw]
            drawer_final = evaluate_hand(caller.cards)
        opener_final = evaluate_hand(
            (*plan.keep, *(card_from_id(i) for i in d_cards))
        )
        deals.append(
            NonbluffDeal(
                opener_class=cls,
                caller_class=caller_class,
                d=plan.n_draw,
                caller_d=caller_d,
                opener_start_pair=_pair_rank_from_class(cls),
                opener_final=opener_final,
                drawer_final=drawer_final,
                opener_final_pair=_one_pair_rank(opener_final),
                drawer_final_pair=_face_pair_rank(drawer_final),
                drawer_straight_plus=drawer_final.category >= HandCategory.STRAIGHT,
                opener_two_pair_plus=opener_final.category >= HandCategory.TWO_PAIR,
            )
        )
    return deals


# --- Accounting -----------------------------------------------------------------


def caller_ev_from_bn(ev_bn: float) -> float:
    """Post-draw incremental chips: BN + caller = predraw pot (sunk $6)."""
    return PREDRAW_POT - ev_bn


def play_honest_deal(
    deal: NonbluffDeal, policy: M2Policy = HONEST_POLICY
) -> tuple[float, float, dict[str, bool]]:
    ev_bn, flags = m2_play_deal(deal, policy)  # type: ignore[arg-type]
    return ev_bn, caller_ev_from_bn(ev_bn), flags


def case_ids_for_deal(deal: NonbluffDeal) -> list[str]:
    if deal.opener_final > deal.drawer_final:
        cmp = 1
    elif deal.opener_final < deal.drawer_final:
        cmp = -1
    else:
        cmp = 0
    return _case_hits(
        opener_class=deal.opener_class,
        dealer_started_straight_plus=deal.opener_class in STRAIGHT_PLUS_CLASSES,
        dealer_started_two_pair_or_trips=(
            deal.opener_class in TWO_PAIR_CLASSES
            or deal.opener_class in TRIPS_CLASSES
        ),
        dealer_pair_rank=_PAIR_RANK.get(deal.opener_class),
        dealer_final=deal.opener_final,
        caller_final=deal.drawer_final,
        cmp=cmp,
    )


@dataclass(slots=True)
class CellAccum:
    n: float = 0.0
    ev_bn: float = 0.0
    ev_caller: float = 0.0
    sd_win: float = 0.0
    sd_tie: float = 0.0
    sd_lose: float = 0.0
    showdown: float = 0.0
    cases: Counter = field(default_factory=Counter)
    p_drawer_straight_plus: float = 0.0
    p_bn_two_pair_plus: float = 0.0

    def add(
        self,
        deal: NonbluffDeal,
        ev_bn: float,
        ev_caller: float,
        flags: dict[str, bool],
    ) -> None:
        self.n += 1.0
        self.ev_bn += ev_bn
        self.ev_caller += ev_caller
        if deal.opener_final > deal.drawer_final:
            self.sd_win += 1.0
        elif deal.opener_final < deal.drawer_final:
            self.sd_lose += 1.0
        else:
            self.sd_tie += 1.0
        if flags.get("showdown"):
            self.showdown += 1.0
        if deal.drawer_straight_plus:
            self.p_drawer_straight_plus += 1.0
        if deal.opener_two_pair_plus:
            self.p_bn_two_pair_plus += 1.0
        for cid in case_ids_for_deal(deal):
            self.cases[cid] += 1.0

    def as_dict(self) -> dict[str, Any]:
        n = self.n or 1.0
        return {
            "n": self.n,
            "ev_bn": round(self.ev_bn / n, 5),
            "ev_caller": round(self.ev_caller / n, 5),
            "p_bn_wins_final": round(self.sd_win / n, 5),
            "p_tie_final": round(self.sd_tie / n, 5),
            "p_caller_wins_final": round(self.sd_lose / n, 5),
            "showdown_rate": round(self.showdown / n, 5),
            "p_drawer_straight_plus": round(self.p_drawer_straight_plus / n, 5),
            "p_bn_two_pair_plus": round(self.p_bn_two_pair_plus / n, 5),
            "cases": {cid: round(self.cases.get(cid, 0.0) / n, 5) for cid in _CASE_IDS},
        }


def evaluate_deals(
    deals: Sequence[NonbluffDeal], policy: M2Policy = HONEST_POLICY
) -> CellAccum:
    acc = CellAccum()
    for deal in deals:
        ev_bn, ev_caller, flags = play_honest_deal(deal, policy)
        acc.add(deal, ev_bn, ev_caller, flags)
    return acc


# --- Grid -----------------------------------------------------------------------


def _cell_row(
    *,
    opener_class: str,
    bn_d: int,
    caller_class: str,
    caller_d: int,
    inventory_size: int,
    acc: CellAccum,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "opener_class": opener_class,
        "bn_d": bn_d,
        "caller_class": caller_class,
        "caller_d": caller_d,
        "inventory_size": inventory_size,
        **acc.as_dict(),
    }
    if extra:
        row.update(extra)
    return row


def run_bn_draw_grid(
    inventory: dict[str, list[tuple[int, ...]]],
    callers: Sequence[DrawHandResult],
    *,
    n_per_cell: int,
    seed: int,
    progress: bool = True,
    classes: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Every BN class × legal d vs all 2:1 callers at keep-4 d=1."""
    use = list(classes) if classes else list(OPENER_CLASSES)
    rows: list[dict[str, Any]] = []
    for cls in use:
        for bn_d in legal_actions_for_class(cls):
            if progress:
                print(f"  BN {cls} d={bn_d} vs {CALLER_ALL} d=1…")
            deals = generate_nonbluff_deals(
                inventory,
                callers,
                cls,
                bn_d,
                caller_d=1,
                caller_class=CALLER_ALL,
                n_deals=n_per_cell,
                seed=_cell_seed(seed, cls, bn_d, CALLER_ALL, 1),
            )
            acc = evaluate_deals(deals, HONEST_POLICY)
            extra: dict[str, Any] = {}
            if cls in PAIR_CLASSES and bn_d == 3:
                acc_aa = evaluate_deals(deals, HONEST_POLICY_LEAD_AA)
                extra["ev_bn_lead_AA"] = acc_aa.as_dict()["ev_bn"]
                extra["ev_caller_lead_AA"] = acc_aa.as_dict()["ev_caller"]
                acc_pas = evaluate_deals(deals, HONEST_POLICY_PASSIVE)
                extra["ev_bn_passive_stab"] = acc_pas.as_dict()["ev_bn"]
            rows.append(
                _cell_row(
                    opener_class=cls,
                    bn_d=bn_d,
                    caller_class=CALLER_ALL,
                    caller_d=1,
                    inventory_size=len(inventory.get(cls, [])),
                    acc=acc,
                    extra=extra,
                )
            )
    return rows


def run_caller_class_slice(
    inventory: dict[str, list[tuple[int, ...]]],
    groups: dict[str, list[DrawHandResult]],
    *,
    n_per_cell: int,
    seed: int,
    progress: bool = True,
) -> list[dict[str, Any]]:
    """Locked BN draws vs each 2:1 subclass (caller d=1)."""
    rows: list[dict[str, Any]] = []
    for caller_cls in CALLER_DRAW_CLASSES:
        subset = groups.get(caller_cls, [])
        if progress:
            print(f"  locked BN range vs {caller_cls} (n={len(subset)})…")
        deals = generate_locked_range_deals(
            inventory,
            subset,
            caller_d=1,
            caller_class=caller_cls,
            n_deals=n_per_cell,
            seed=_cell_seed(seed, "locked", caller_cls, 1),
        )
        acc = evaluate_deals(deals, HONEST_POLICY)
        by_bn: dict[str, CellAccum] = defaultdict(CellAccum)
        for deal in deals:
            ev_bn, ev_caller, flags = play_honest_deal(deal, HONEST_POLICY)
            by_bn[deal.opener_class].add(deal, ev_bn, ev_caller, flags)
        rows.append(
            {
                "slice": "caller_class_vs_locked_bn_range",
                "caller_class": caller_cls,
                "caller_d": 1,
                "bn_draw_policy": LOCKED_BN_DRAW.name,
                "inventory_size": len(subset),
                **acc.as_dict(),
                "by_bn_class": {
                    cls: a.as_dict()
                    for cls, a in sorted(by_bn.items(), key=lambda kv: kv[0])
                    if a.n >= 20
                },
            }
        )
    return rows


def run_caller_d_fork(
    inventory: dict[str, list[tuple[int, ...]]],
    callers: Sequence[DrawHandResult],
    *,
    n_per_cell: int,
    seed: int,
    progress: bool = True,
) -> list[dict[str, Any]]:
    """Caller stand (d=0) vs keep-4 (d=1) against representative BN classes."""
    rows: list[dict[str, Any]] = []
    for cls in CALLER_D_FORK_BN_CLASSES:
        bn_d = LOCKED_BN_DRAW.n_draw_for(cls)
        for caller_d in (0, 1):
            if progress:
                print(f"  caller d={caller_d} vs BN {cls} d={bn_d}…")
            deals = generate_nonbluff_deals(
                inventory,
                callers,
                cls,
                bn_d,
                caller_d=caller_d,
                caller_class=CALLER_ALL,
                n_deals=n_per_cell,
                seed=_cell_seed(seed, "cfork", cls, bn_d, caller_d),
            )
            acc = evaluate_deals(deals, HONEST_POLICY)
            rows.append(
                _cell_row(
                    opener_class=cls,
                    bn_d=bn_d,
                    caller_class=CALLER_ALL,
                    caller_d=caller_d,
                    inventory_size=len(inventory.get(cls, [])),
                    acc=acc,
                )
            )
    return rows


def best_bn_draw_rows(bn_grid: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Argmax EV_bn over legal d for each BN class (vs all_2to1, caller d=1)."""
    by_cls: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in bn_grid:
        if row["caller_class"] == CALLER_ALL and row["caller_d"] == 1:
            by_cls[row["opener_class"]].append(row)
    out = []
    for cls, rows in by_cls.items():
        ranked = sorted(rows, key=lambda r: r["ev_bn"], reverse=True)
        best = ranked[0]
        second = ranked[1] if len(ranked) > 1 else None
        out.append(
            {
                "opener_class": cls,
                "best_bn_d": best["bn_d"],
                "ev_bn": best["ev_bn"],
                "ev_caller": best["ev_caller"],
                "legal_d": [r["bn_d"] for r in sorted(rows, key=lambda r: r["bn_d"])],
                "ev_by_d": {str(r["bn_d"]): r["ev_bn"] for r in rows},
                "ev_caller_by_d": {str(r["bn_d"]): r["ev_caller"] for r in rows},
                "delta_vs_next": (
                    round(best["ev_bn"] - second["ev_bn"], 5) if second else None
                ),
                "next_d": second["bn_d"] if second else None,
            }
        )
    order = {c: i for i, c in enumerate(OPENER_CLASSES)}
    out.sort(key=lambda r: order.get(r["opener_class"], 99))
    return out


def _derive_findings(
    bn_grid: list[dict[str, Any]],
    best: list[dict[str, Any]],
    caller_fork: list[dict[str, Any]],
    caller_slice: list[dict[str, Any]],
) -> dict[str, Any]:
    def cell(cls: str, d: int) -> dict[str, Any] | None:
        return next(
            (
                r
                for r in bn_grid
                if r["opener_class"] == cls
                and r["bn_d"] == d
                and r["caller_class"] == CALLER_ALL
                and r["caller_d"] == 1
            ),
            None,
        )

    def family_best(classes: Sequence[str]) -> dict[str, Any]:
        rows = [r for r in best if r["opener_class"] in classes]
        return {
            "classes": list(classes),
            "best_d_votes": {str(r["opener_class"]): r["best_bn_d"] for r in rows},
        }

    def ev_by_d(cls: str, draws: tuple[int, ...]) -> dict[int, float]:
        out: dict[int, float] = {}
        for d in draws:
            row = cell(cls, d)
            if row is not None:
                out[d] = row["ev_bn"]
        return out

    pair_a = ev_by_d("pair_A", (0, 1, 2, 3))
    pair_j = ev_by_d("pair_J", (0, 1, 2, 3))
    tp = ev_by_d("two_pair", (0, 1))
    trips = ev_by_d("trips", (0, 1, 2))
    quads = ev_by_d("four_of_a_kind", (0, 1))

    def fork_ev(cls: str, caller_d: int) -> float | None:
        row = next(
            (
                r
                for r in caller_fork
                if r["opener_class"] == cls and r["caller_d"] == caller_d
            ),
            None,
        )
        return None if row is None else row["ev_caller"]

    caller_d1_beats_stand: dict[str, float] = {}
    for cls in CALLER_D_FORK_BN_CLASSES:
        a, b = fork_ev(cls, 1), fork_ev(cls, 0)
        if a is not None and b is not None:
            caller_d1_beats_stand[cls] = round(a - b, 5)

    def beats(table: dict[int, float], hi: int, lo: int, tol: float) -> bool | None:
        if hi not in table or lo not in table:
            return None
        return table[hi] >= table[lo] - tol

    aa_d3 = cell("pair_A", 3)
    return {
        "honest_policy": HONEST_POLICY.key,
        "pair_A_ev_by_d": pair_a,
        "pair_J_ev_by_d": pair_j,
        "pair_A_d3_beats_d2": beats(pair_a, 3, 2, 0.05),
        "pair_J_d3_beats_d2": beats(pair_j, 3, 2, 0.05),
        "pair_A_best_d": max(pair_a, key=pair_a.get) if pair_a else None,
        "pair_J_best_d": max(pair_j, key=pair_j.get) if pair_j else None,
        "pair_stand_is_chip_max": (
            bool(pair_a)
            and bool(pair_j)
            and max(pair_a, key=pair_a.get) == 0
            and max(pair_j, key=pair_j.get) == 0
        ),
        "pair_J_d0_p_win": None
        if cell("pair_J", 0) is None
        else cell("pair_J", 0)["p_bn_wins_final"],
        "pair_J_d3_p_win": None
        if cell("pair_J", 3) is None
        else cell("pair_J", 3)["p_bn_wins_final"],
        "two_pair_ev_by_d": tp,
        "two_pair_d1_beats_stand": beats(tp, 1, 0, 0.02),
        "trips_ev_by_d": trips,
        "trips_d2_beats_d1": beats(trips, 2, 1, 0.05),
        "trips_d2_beats_stand": beats(trips, 2, 0, 0.02),
        "quads_ev_by_d": quads,
        "quads_d1_vs_stand_delta": (
            round(quads[1] - quads[0], 5) if 0 in quads and 1 in quads else None
        ),
        "pair_A_d3_lead_AA_ev_bn": None if aa_d3 is None else aa_d3.get("ev_bn_lead_AA"),
        "pair_A_d3_check_ev_bn": None if aa_d3 is None else aa_d3["ev_bn"],
        "caller_d1_delta_vs_stand": caller_d1_beats_stand,
        "caller_keep4_beats_stand": (
            bool(caller_d1_beats_stand)
            and all(v > 0.0 for v in caller_d1_beats_stand.values())
        ),
        "best_d_by_class": {r["opener_class"]: r["best_bn_d"] for r in best},
        "family_pairs": family_best(PAIR_CLASSES),
        "caller_slice_ev_caller": {
            r["caller_class"]: r["ev_caller"] for r in caller_slice
        },
        "bluff_deferred": True,
    }


def build_recommendations(findings: dict[str, Any]) -> list[dict[str, str]]:
    pair_note = (
        f"pair_A EV by d={findings['pair_A_ev_by_d']}; "
        f"pair_J EV by d={findings['pair_J_ev_by_d']}. "
        "Standing wins more chips because d=3 two-pair+ auto-bets and pays "
        "off the caller’s ~34% straight+ (win rate can rise while EV falls). "
        "A/B still lock pairs at d=3 so they do not pollute public d=0 with "
        "pat straight+. Concealment (d≠3) is later."
    )
    return [
        {
            "side": "BN",
            "class": "pair JJ–AA",
            "nonbluff_d": (
                "stand (d=0) max chips; d=3 is the range-construction lock"
            ),
            "postdraw": "check one pair; value-bet two pair+ (no check mix)",
            "notes": pair_note,
        },
        {
            "side": "BN",
            "class": "two_pair",
            "nonbluff_d": "d=1" if findings["two_pair_d1_beats_stand"] else "stand",
            "postdraw": "always value-bet the final (two pair or boat)",
            "notes": f"EV by d={findings['two_pair_ev_by_d']}",
        },
        {
            "side": "BN",
            "class": "trips",
            "nonbluff_d": (
                "d=2 (primary)" if findings["trips_d2_beats_d1"] else "d=1"
            ),
            "postdraw": "always value-bet; d=1 remains the unified-line fork",
            "notes": f"EV by d={findings['trips_ev_by_d']}",
        },
        {
            "side": "BN",
            "class": "four_of_a_kind",
            "nonbluff_d": "d=1 (prefer; EV-neutral vs stand)",
            "postdraw": "always value-bet",
            "notes": f"Δ d=1 vs stand={findings['quads_d1_vs_stand_delta']:+.4f}",
        },
        {
            "side": "BN",
            "class": "other straight+",
            "nonbluff_d": "stand only",
            "postdraw": "always value-bet",
            "notes": "Cannot join d>0 without breaking the made hand.",
        },
        {
            "side": "caller",
            "class": "2:1 keep-4 (all subclasses)",
            "nonbluff_d": "d=1 (keep 4)",
            "postdraw": (
                "value-bet/raise straight+; AA stab when checked; "
                "no face-pair raise; miss check/fold"
            ),
            "notes": (
                f"keep4 vs stand ΔEV_caller={findings['caller_d1_delta_vs_stand']}. "
                "Bluff (miss bets / CO return-to-actor) comes next."
            ),
        },
    ]


def run_grid(
    *,
    n_per_cell: int = DEFAULT_N_PER_CELL,
    seed: int = DEFAULT_SEED,
    progress: bool = True,
    callers: Sequence[DrawHandResult] | None = None,
    inventory: dict[str, list[tuple[int, ...]]] | None = None,
    classes: Sequence[str] | None = None,
) -> dict[str, Any]:
    if callers is None or inventory is None:
        if progress:
            print("Loading 2:1 callers + BN opener inventory…")
        callers = callers or load_call_2to1_hands(progress=progress)
        inventory = inventory or build_opener_inventory(progress=progress)
    groups = group_callers_by_class(callers)

    if progress:
        print("BN class × d grid vs all 2:1 (caller d=1)…")
    bn_grid = run_bn_draw_grid(
        inventory,
        groups[CALLER_ALL],
        n_per_cell=n_per_cell,
        seed=seed,
        progress=progress,
        classes=classes,
    )
    if progress:
        print("Caller subclass slice vs locked BN draws…")
    caller_slice = run_caller_class_slice(
        inventory,
        groups,
        n_per_cell=n_per_cell,
        seed=seed,
        progress=progress,
    )
    if progress:
        print("Caller d=0 vs d=1 fork…")
    caller_fork = run_caller_d_fork(
        inventory,
        groups[CALLER_ALL],
        n_per_cell=n_per_cell,
        seed=seed,
        progress=progress,
    )
    best = best_bn_draw_rows(bn_grid)
    findings = _derive_findings(bn_grid, best, caller_fork, caller_slice)
    recs = build_recommendations(findings)
    return {
        "meta": {
            "seed": seed,
            "n_per_cell": n_per_cell,
            "predraw_pot": PREDRAW_POT,
            "big_bet": BIG,
            "matchup": "BN (seat 8) opener vs one 2:1 drawing caller",
            "predraw": "open + call only (no raise)",
            "honest_policy": HONEST_POLICY.key,
            "honest_policy_notes": list(POLICY_NOTES),
            "bn_keep_rules": KEEP_RULE_NOTES,
            "caller_keep": "d=1 keep-4 (fixture 2:1 keep); d=0 stand with dealt five",
            "locked_bn_draw_for_caller_slices": {
                "name": LOCKED_BN_DRAW.name,
                "pair_d": LOCKED_BN_DRAW.pair_d,
                "two_pair_d": LOCKED_BN_DRAW.two_pair_d,
                "trips_d": LOCKED_BN_DRAW.trips_d,
                "quads_d": LOCKED_BN_DRAW.quads_d,
            },
            "case_descriptions": CASE_DESCRIPTIONS,
            "bluffing": "deferred — this table is the non-bluff baseline",
            "doc": "docs/NEXT_STAGE_NONBLUFF_EV.md",
            "regenerate": (
                "analyze-postdraw-nonbluff-ev --n-per-cell 4000 --write-fixture"
            ),
        },
        "bn_grid": bn_grid,
        "best_bn_draw": best,
        "caller_class_slice": caller_slice,
        "caller_d_fork": caller_fork,
        "findings": findings,
        "recommendations": recs,
    }


def build_summary_payload(payload: dict[str, Any]) -> dict[str, Any]:
    def round_obj(obj: Any) -> Any:
        if isinstance(obj, float):
            return round(obj, 4)
        if isinstance(obj, dict):
            return {k: round_obj(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [round_obj(x) for x in obj]
        return obj

    slim_grid = []
    for r in payload["bn_grid"]:
        slim = {
            "opener_class": r["opener_class"],
            "bn_d": r["bn_d"],
            "caller_class": r["caller_class"],
            "caller_d": r["caller_d"],
            "inventory_size": r["inventory_size"],
            "n": r["n"],
            "ev_bn": r["ev_bn"],
            "ev_caller": r["ev_caller"],
            "p_bn_wins_final": r["p_bn_wins_final"],
            "p_tie_final": r["p_tie_final"],
            "p_caller_wins_final": r["p_caller_wins_final"],
            "p_drawer_straight_plus": r["p_drawer_straight_plus"],
            "cases_focus": {
                k: r["cases"][k]
                for k in ("1", "2", "1b", "3", "3b", "4", "4b", "5", "5c", "8c")
                if r["cases"].get(k, 0.0) > 0.0
            },
        }
        for k in ("ev_bn_lead_AA", "ev_caller_lead_AA", "ev_bn_passive_stab"):
            if k in r:
                slim[k] = r[k]
        slim_grid.append(slim)

    slim_slice = []
    for r in payload["caller_class_slice"]:
        slim_slice.append(
            {
                "caller_class": r["caller_class"],
                "caller_d": r["caller_d"],
                "n": r["n"],
                "ev_bn": r["ev_bn"],
                "ev_caller": r["ev_caller"],
                "p_bn_wins_final": r["p_bn_wins_final"],
                "p_caller_wins_final": r["p_caller_wins_final"],
                "p_drawer_straight_plus": r["p_drawer_straight_plus"],
            }
        )

    return round_obj(
        {
            "meta": payload["meta"],
            "bn_grid": slim_grid,
            "best_bn_draw": payload["best_bn_draw"],
            "caller_class_slice": slim_slice,
            "caller_d_fork": [
                {
                    "opener_class": r["opener_class"],
                    "bn_d": r["bn_d"],
                    "caller_d": r["caller_d"],
                    "n": r["n"],
                    "ev_bn": r["ev_bn"],
                    "ev_caller": r["ev_caller"],
                    "p_caller_wins_final": r["p_caller_wins_final"],
                }
                for r in payload["caller_d_fork"]
            ],
            "findings": payload["findings"],
            "recommendations": payload["recommendations"],
        }
    )


def write_markdown_summary(payload: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = payload if "findings" in payload else build_summary_payload(payload)
    f = summary["findings"]
    meta = summary["meta"]
    lines = [
        "# Non-bluff max-EV by hand type × draw count",
        "",
        f"BN (seat 8) vs one 2:1 caller. Seed `{meta['seed']}`, "
        f"`{meta['n_per_cell']}` deals/cell. Pot `${meta['predraw_pot']}`, "
        f"big bet `${meta['big_bet']}`. Honest policy `{meta['honest_policy']}`.",
        "",
        "Bluffing is **not** in this table. Use these cells as the non-bluff "
        "baseline; a later delta can measure stabs/leads/check-mixes.",
        "",
        "Doc: `docs/NEXT_STAGE_NONBLUFF_EV.md`. Cases 1–8c: "
        "`docs/NEXT_STAGE_SHOWDOWN_MATRIX.md`.",
        "",
        "## Best non-bluff draw (BN EV vs all 2:1, caller d=1)",
        "",
        "| BN class | Best d | EV_bn | EV_caller | EV by d |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for r in summary["best_bn_draw"]:
        by_d = ", ".join(
            f"d={k}:{v:.3f}"
            for k, v in sorted(r["ev_by_d"].items(), key=lambda kv: int(kv[0]))
        )
        lines.append(
            f"| {r['opener_class']} | {r['best_bn_d']} | {r['ev_bn']:.4f} | "
            f"{r['ev_caller']:.4f} | {by_d} |"
        )
    lines += [
        "",
        "## Highlights",
        "",
        f"- Pair AA best d={f['pair_A_best_d']}; EV by d={f['pair_A_ev_by_d']}",
        f"- Pair JJ best d={f['pair_J_best_d']}; EV by d={f['pair_J_ev_by_d']}",
        f"- Pair stand is chip-max (honest betting): **{f.get('pair_stand_is_chip_max')}** "
        f"(JJ P(win) d=0={f.get('pair_J_d0_p_win')} vs d=3={f.get('pair_J_d3_p_win')})",
        f"- Two pair d=1 beats stand: **{f['two_pair_d1_beats_stand']}** "
        f"{f['two_pair_ev_by_d']}",
        f"- Trips d=2 vs d=1 vs stand: {f['trips_ev_by_d']}",
        f"- Quads d=1 vs stand Δ={f['quads_d1_vs_stand_delta']}",
        f"- Caller keep-4 vs stand ΔEV_caller: {f['caller_d1_delta_vs_stand']}",
        f"- Caller subclass EV_caller vs locked BN range: "
        f"{f['caller_slice_ev_caller']}",
        "",
        "## Recommendations",
        "",
        "| Side | Class | Non-bluff d | Post-draw | Notes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in summary["recommendations"]:
        lines.append(
            f"| {r['side']} | {r['class']} | {r['nonbluff_d']} | "
            f"{r['postdraw']} | {r['notes']} |"
        )
    lines += [
        "",
        "## Next: bluff delta",
        "",
        "With this table, later work can add (a) miss/face-pair bluff stabs, "
        "(b) BN check-mixes of two pair+ (Stage C), (c) pair d≠3 concealment, "
        "and report ΔEV vs the honest cell — not a new baseline.",
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
        / "postdraw_nonbluff_ev_summary.json"
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
        description="Non-bluff max-EV by BN class × draw count vs 2:1 caller"
    )
    p.add_argument("--n-per-cell", type=int, default=DEFAULT_N_PER_CELL)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--quick", action="store_true", help="Tiny sample for smoke runs")
    p.add_argument(
        "--classes",
        type=str,
        default=None,
        help="Comma-separated BN classes (default: all)",
    )
    p.add_argument("-o", "--output", type=Path, default=None)
    p.add_argument(
        "--write-fixture",
        action="store_true",
        help="Refresh tests/fixtures/validation/postdraw_nonbluff_ev_summary.json",
    )
    args = p.parse_args()
    n = 400 if args.quick else args.n_per_cell
    classes = (
        [c.strip() for c in args.classes.split(",") if c.strip()]
        if args.classes
        else None
    )
    payload = run_grid(n_per_cell=n, seed=args.seed, progress=True, classes=classes)
    out = args.output or Path("outputs/validation/postdraw_nonbluff_ev.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out}")
    md = out.with_suffix(".md")
    write_markdown_summary(payload, md)
    print(f"Wrote {md}")
    if args.write_fixture:
        if classes:
            print("--write-fixture requires the full class set (omit --classes)")
        else:
            fix = write_summary_fixture(payload)
            print(f"Wrote fixture {fix}")
    print()
    print("Best non-bluff d (EV_bn / EV_caller):")
    for r in payload["best_bn_draw"]:
        print(
            f"  {r['opener_class']:<20} d={r['best_bn_d']}  "
            f"BN={r['ev_bn']:+.4f}  caller={r['ev_caller']:+.4f}  "
            f"by_d={r['ev_by_d']}"
        )


if __name__ == "__main__":
    main()
