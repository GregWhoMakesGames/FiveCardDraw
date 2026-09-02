"""Post-draw cap (bet + 3 raises) when BN bets and the 2:1 caller raises.

The M2 / non-bluff street is **bet + one raise** (`max_raises=1`): BN value-bets
two pair+, caller raises straight+, BN calls. This module extends that node
with BN 3-bet / caller cap / BN call-cap under `max_raises=3`.

Does **not** re-run the class × d EV grid. Condition on the raise node
(BN two pair+ ∩ caller straight+). Bluff 3-bets with two pair / trips are
out of scope.

Doc: `docs/NEXT_STAGE_POSTDRAW_CAP.md`.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from fivecarddraw.cards import RANK_NAMES
from fivecarddraw.hand_rank import HandCategory, HandValue
from fivecarddraw.validation.postdraw_betting_m2 import (
    BIG,
    CAP_POT,
    PREDRAW_POT,
    CapPolicy,
    play_raise_node,
)
from fivecarddraw.validation.postdraw_nonbluff_ev import (
    CALLER_ALL,
    HONEST_POLICY,
    LOCKED_BN_DRAW,
    NonbluffDeal,
    caller_ev_from_bn,
    generate_locked_range_deals,
    generate_nonbluff_deals,
)
from fivecarddraw.validation.showdown_matrix import (
    OPENER_CLASSES,
    STRAIGHT_PLUS_CLASSES,
    TRIPS_CLASSES,
    TWO_PAIR_CLASSES,
    build_opener_inventory,
    load_call_2to1_hands,
)


DEFAULT_SEED = 20260902
DEFAULT_N_RANGE = 40_000
DEFAULT_N_PER_CLASS = 4_000
MIN_BUCKET_N = 50

# Unilateral-deviation holds (honest, from the handoff).
HOLD_CALLER = CapPolicy(
    opener_3bet_min=HandCategory.FLUSH,  # unused for caller-hold Δ
    drawer_cap_min=HandCategory.STRAIGHT_FLUSH,
    drawer_call_3bet_min=HandCategory.STRAIGHT,
)
HOLD_BN_FLUSH_PLUS = CapPolicy(
    opener_3bet_min=HandCategory.FLUSH,
    drawer_cap_min=HandCategory.STRAIGHT_FLUSH,
    drawer_call_3bet_min=HandCategory.STRAIGHT,
)
HOLD_BN_BOAT_PLUS = CapPolicy(
    opener_3bet_min=HandCategory.FULL_HOUSE,
    drawer_cap_min=HandCategory.STRAIGHT_FLUSH,
    drawer_call_3bet_min=HandCategory.STRAIGHT,
)

BN_3BET_GRID = (
    ("call_it_down", None),
    ("straight+", HandCategory.STRAIGHT),
    ("flush+", HandCategory.FLUSH),
    ("boat+", HandCategory.FULL_HOUSE),
)
CALLER_CAP_GRID = (
    ("call_no_cap", None, HandCategory.STRAIGHT),
    ("cap_sf", HandCategory.STRAIGHT_FLUSH, HandCategory.STRAIGHT),
    ("cap_flush+", HandCategory.FLUSH, HandCategory.STRAIGHT),
    ("fold_straight_cap_sf", HandCategory.STRAIGHT_FLUSH, HandCategory.FLUSH),
)

# Extra deals: classes that always bet (two pair+) so the node is cheap to hit.
EXTRA_BN_CLASSES = TWO_PAIR_CLASSES + TRIPS_CLASSES + STRAIGHT_PLUS_CLASSES


def on_raise_node(deal: NonbluffDeal) -> bool:
    """BN value-bets (two pair+) and caller raises (straight+)."""
    return bool(deal.opener_two_pair_plus and deal.drawer_straight_plus)


def fine_bucket(v: HandValue) -> str:
    """HandValue.category + high card; merge rare low flushes."""
    cat = v.category
    if cat == HandCategory.STRAIGHT:
        return f"straight_{RANK_NAMES[v.tiebreak[0]]}"
    if cat == HandCategory.FLUSH:
        high = v.tiebreak[0]
        if high < 11:
            return "flush_low"
        return f"flush_{RANK_NAMES[high]}"
    if cat == HandCategory.STRAIGHT_FLUSH:
        return "straight_flush"
    if cat == HandCategory.TWO_PAIR:
        return "two_pair"
    if cat == HandCategory.THREE_OF_A_KIND:
        return "three_of_a_kind"
    if cat == HandCategory.FULL_HOUSE:
        return "full_house"
    if cat == HandCategory.FOUR_OF_A_KIND:
        return "four_of_a_kind"
    if cat == HandCategory.FIVE_ACES:
        return "five_aces"
    if cat == HandCategory.ONE_PAIR:
        return f"one_pair_{RANK_NAMES[v.tiebreak[0]]}"
    return f"cat_{int(cat)}"


def family_bucket(v: HandValue) -> str:
    cat = v.category
    if cat < HandCategory.TWO_PAIR:
        return "pair_or_worse"
    if cat < HandCategory.STRAIGHT:
        return "two_pair_or_trips"
    if cat == HandCategory.STRAIGHT:
        return "straight"
    if cat == HandCategory.FLUSH:
        return "flush"
    return "boat_plus"


def _policy(bn_3bet_min: int | None, cap_min: int | None, call3_min: int) -> CapPolicy:
    return CapPolicy(
        opener_3bet_min=bn_3bet_min,
        drawer_cap_min=cap_min,
        drawer_call_3bet_min=call3_min,
    )


@dataclass(slots=True)
class NodeAccum:
    n: float = 0.0
    ev_bn: float = 0.0
    ev_caller: float = 0.0
    bn_wins: float = 0.0
    ties: float = 0.0
    three_bet: float = 0.0
    cap: float = 0.0
    fold_3bet: float = 0.0

    def add(
        self,
        deal: NonbluffDeal,
        ev_bn: float,
        flags: dict[str, bool],
    ) -> None:
        self.n += 1.0
        self.ev_bn += ev_bn
        self.ev_caller += caller_ev_from_bn(ev_bn)
        if deal.opener_final > deal.drawer_final:
            self.bn_wins += 1.0
        elif deal.opener_final == deal.drawer_final:
            self.ties += 1.0
        if flags.get("opener_3bet"):
            self.three_bet += 1.0
        if flags.get("drawer_cap"):
            self.cap += 1.0
        if flags.get("drawer_fold_to_3bet"):
            self.fold_3bet += 1.0

    def as_dict(self) -> dict[str, Any]:
        n = self.n or 1.0
        return {
            "n": self.n,
            "ev_bn": round(self.ev_bn / n, 5),
            "ev_caller": round(self.ev_caller / n, 5),
            "p_bn_wins": round(self.bn_wins / n, 5),
            "p_tie": round(self.ties / n, 5),
            "p_3bet": round(self.three_bet / n, 5),
            "p_cap": round(self.cap / n, 5),
            "p_caller_fold_3bet": round(self.fold_3bet / n, 5),
        }


@dataclass(slots=True)
class DeltaAccum:
    n: float = 0.0
    ev_call: float = 0.0
    ev_3bet: float = 0.0
    ev_fold: float = 0.0
    ev_cap: float = 0.0
    bn_wins: float = 0.0
    by_start: dict[str, float] = field(default_factory=lambda: defaultdict(float))

    def as_bn_row(self, bucket: str) -> dict[str, Any]:
        n = self.n or 1.0
        ev_call = self.ev_call / n
        ev_3bet = self.ev_3bet / n
        return {
            "bucket": bucket,
            "n": self.n,
            "p_bn_wins": round(self.bn_wins / n, 5),
            "ev_bn_call": round(ev_call, 5),
            "ev_bn_3bet": round(ev_3bet, 5),
            "delta_3bet_vs_call": round(ev_3bet - ev_call, 5),
            "recommend": "three_bet" if (ev_3bet - ev_call) > 0.05 else "call",
        }

    def as_caller_row(self, bucket: str) -> dict[str, Any]:
        n = self.n or 1.0
        # Stored values are EV_bn; convert to EV_caller = PREDRAW_POT - EV_bn.
        ev_fold_c = PREDRAW_POT - self.ev_fold / n
        ev_call_c = PREDRAW_POT - self.ev_call / n
        ev_cap_c = PREDRAW_POT - self.ev_cap / n
        best = max(
            (("fold", ev_fold_c), ("call", ev_call_c), ("cap", ev_cap_c)),
            key=lambda kv: kv[1],
        )
        return {
            "bucket": bucket,
            "n": self.n,
            "p_bn_wins": round(self.bn_wins / n, 5),
            "ev_caller_fold": round(ev_fold_c, 5),
            "ev_caller_call": round(ev_call_c, 5),
            "ev_caller_cap": round(ev_cap_c, 5),
            "delta_cap_vs_call": round(ev_cap_c - ev_call_c, 5),
            "delta_fold_vs_call": round(ev_fold_c - ev_call_c, 5),
            "recommend": best[0],
        }


def play_node_with_policy(
    deal: NonbluffDeal, cap: CapPolicy, *, max_raises: int = 3
) -> tuple[float, dict[str, bool]]:
    bn_act = "three_bet" if cap.opener_three_bets(deal.opener_final) else "call"
    caller_act = (
        cap.caller_vs_three_bet(deal.drawer_final) if bn_act == "three_bet" else "call"
    )
    bn_cap = "call" if cap.opener_calls_cap(deal.opener_final) else "fold"
    return play_raise_node(
        deal,  # type: ignore[arg-type]
        bn_vs_raise=bn_act,
        caller_vs_3bet=caller_act,
        bn_vs_cap=bn_cap,
        max_raises=max_raises,
    )


def evaluate_policy_on_node(
    deals: Sequence[NonbluffDeal], cap: CapPolicy
) -> NodeAccum:
    acc = NodeAccum()
    for deal in deals:
        ev, flags = play_node_with_policy(deal, cap)
        acc.add(deal, ev, flags)
    return acc


def bn_unilateral_rows(
    deals: Sequence[NonbluffDeal],
    *,
    caller: CapPolicy,
    key_fn,
) -> list[dict[str, Any]]:
    """Δ EV_bn of always-3-bet vs always-call, holding caller's vs-3-bet policy."""
    buckets: dict[str, DeltaAccum] = defaultdict(DeltaAccum)
    for deal in deals:
        b = key_fn(deal.opener_final)
        acc = buckets[b]
        ev_call, _ = play_raise_node(deal, bn_vs_raise="call")  # type: ignore[arg-type]
        caller_act = caller.caller_vs_three_bet(deal.drawer_final)
        ev_3, _ = play_raise_node(  # type: ignore[arg-type]
            deal,
            bn_vs_raise="three_bet",
            caller_vs_3bet=caller_act,
            bn_vs_cap="call",
        )
        acc.n += 1.0
        acc.ev_call += ev_call
        acc.ev_3bet += ev_3
        acc.by_start[deal.opener_class] += 1.0
        if deal.opener_final > deal.drawer_final:
            acc.bn_wins += 1.0
    rows = [acc.as_bn_row(name) for name, acc in buckets.items()]
    rows.sort(key=lambda r: (-r["n"], r["bucket"]))
    return rows


def caller_unilateral_rows(
    deals: Sequence[NonbluffDeal],
    *,
    bn: CapPolicy,
    key_fn,
) -> list[dict[str, Any]]:
    """Δ EV_caller of fold / call / cap vs a BN 3-bet, holding BN's 3-bet range."""
    buckets: dict[str, DeltaAccum] = defaultdict(DeltaAccum)
    for deal in deals:
        if not bn.opener_three_bets(deal.opener_final):
            continue
        b = key_fn(deal.drawer_final)
        acc = buckets[b]
        ev_fold, _ = play_raise_node(  # type: ignore[arg-type]
            deal, bn_vs_raise="three_bet", caller_vs_3bet="fold"
        )
        ev_call, _ = play_raise_node(  # type: ignore[arg-type]
            deal, bn_vs_raise="three_bet", caller_vs_3bet="call"
        )
        ev_cap, _ = play_raise_node(  # type: ignore[arg-type]
            deal, bn_vs_raise="three_bet", caller_vs_3bet="cap", bn_vs_cap="call"
        )
        acc.n += 1.0
        acc.ev_fold += ev_fold
        acc.ev_call += ev_call
        acc.ev_cap += ev_cap
        if deal.opener_final > deal.drawer_final:
            acc.bn_wins += 1.0
    rows = [acc.as_caller_row(name) for name, acc in buckets.items()]
    rows.sort(key=lambda r: (-r["n"], r["bucket"]))
    return rows


def node_mass_by_class(
    deals: Sequence[NonbluffDeal],
) -> list[dict[str, Any]]:
    n_all: dict[str, float] = defaultdict(float)
    n_node: dict[str, float] = defaultdict(float)
    n_bn_bet: dict[str, float] = defaultdict(float)
    n_caller_sp: dict[str, float] = defaultdict(float)
    for deal in deals:
        cls = deal.opener_class
        n_all[cls] += 1.0
        if deal.opener_two_pair_plus:
            n_bn_bet[cls] += 1.0
        if deal.drawer_straight_plus:
            n_caller_sp[cls] += 1.0
        if on_raise_node(deal):
            n_node[cls] += 1.0
    total = sum(n_all.values()) or 1.0
    node_total = sum(n_node.values()) or 1.0
    order = {c: i for i, c in enumerate(OPENER_CLASSES)}
    rows = []
    for cls in sorted(n_all, key=lambda c: order.get(c, 99)):
        n = n_all[cls]
        rows.append(
            {
                "opener_class": cls,
                "n": n,
                "p_class": round(n / total, 5),
                "p_bn_bets": round(n_bn_bet[cls] / n, 5),
                "p_caller_straight_plus": round(n_caller_sp[cls] / n, 5),
                "p_raise_node": round(n_node[cls] / n, 5),
                "p_class_given_node": round(n_node[cls] / node_total, 5),
                "n_node": n_node[cls],
            }
        )
    return rows


def policy_grid(deals: Sequence[NonbluffDeal]) -> list[dict[str, Any]]:
    rows = []
    for bn_name, bn_min in BN_3BET_GRID:
        for c_name, cap_min, call3 in CALLER_CAP_GRID:
            cap = _policy(bn_min, cap_min, call3)
            acc = evaluate_policy_on_node(deals, cap)
            row = {
                "bn_3bet": bn_name,
                "caller_vs_3bet": c_name,
                "policy": cap.key,
                **acc.as_dict(),
            }
            rows.append(row)
    # Δ vs call-it-down (same caller response does not apply; compare each
    # BN 3-bet line vs call_it_down × call_no_cap).
    baseline = next(
        r
        for r in rows
        if r["bn_3bet"] == "call_it_down" and r["caller_vs_3bet"] == "call_no_cap"
    )
    for r in rows:
        r["delta_ev_bn_vs_call_it_down"] = round(r["ev_bn"] - baseline["ev_bn"], 5)
    return rows


def _apply_sparse_recommend(rows: list[dict[str, Any]], family_rows: list[dict[str, Any]]) -> None:
    fam = {r["bucket"]: r for r in family_rows}
    for r in rows:
        if r["n"] >= MIN_BUCKET_N:
            continue
        fam_key = _family_from_fine(r["bucket"])
        if fam_key in fam:
            r["recommend"] = fam[fam_key]["recommend"]
            r["recommend_source"] = f"family:{fam_key} (n<{MIN_BUCKET_N})"
        else:
            r["recommend_source"] = "sparse_unmerged"


def _family_from_fine(bucket: str) -> str:
    if bucket.startswith("straight_"):
        return "straight"
    if bucket.startswith("flush"):
        return "flush"
    if bucket in {"full_house", "four_of_a_kind", "straight_flush", "five_aces"}:
        return "boat_plus"
    if bucket in {"two_pair", "three_of_a_kind"}:
        return "two_pair_or_trips"
    return "pair_or_worse"


def _derive_findings(
    *,
    mass: list[dict[str, Any]],
    grid: list[dict[str, Any]],
    bn_family: list[dict[str, Any]],
    bn_fine: list[dict[str, Any]],
    caller_family_flush: list[dict[str, Any]],
    caller_family_boat: list[dict[str, Any]],
    n_range: int,
    n_node_weighted: int,
) -> dict[str, Any]:
    by_fam = {r["bucket"]: r for r in bn_family}
    by_grid = {(r["bn_3bet"], r["caller_vs_3bet"]): r for r in grid}

    def rec(name: str) -> str | None:
        row = by_fam.get(name)
        return None if row is None else row["recommend"]

    best_grid = max(grid, key=lambda r: r["ev_bn"])
    call_down = by_grid[("call_it_down", "call_no_cap")]
    flush_sf = by_grid[("flush+", "cap_sf")]
    boat_sf = by_grid[("boat+", "cap_sf")]
    straight_sf = by_grid[("straight+", "cap_sf")]

    caller_vs_flush = {r["bucket"]: r for r in caller_family_flush}
    caller_vs_boat = {r["bucket"]: r for r in caller_family_boat}

    node_mass = sum(r["n_node"] for r in mass) / max(n_range, 1)

    def caller_rec(table: dict[str, dict[str, Any]], bucket: str) -> str | None:
        row = table.get(bucket)
        return None if row is None else row["recommend"]

    return {
        "p_raise_node_locked_range": round(node_mass, 5),
        "n_range": n_range,
        "n_node_weighted": n_node_weighted,
        "bn_straight_recommend": rec("straight"),
        "bn_flush_recommend": rec("flush"),
        "bn_boat_plus_recommend": rec("boat_plus"),
        "bn_two_pair_or_trips_recommend": rec("two_pair_or_trips"),
        "bn_straight_delta": None
        if "straight" not in by_fam
        else by_fam["straight"]["delta_3bet_vs_call"],
        "bn_flush_delta": None
        if "flush" not in by_fam
        else by_fam["flush"]["delta_3bet_vs_call"],
        "bn_boat_plus_delta": None
        if "boat_plus" not in by_fam
        else by_fam["boat_plus"]["delta_3bet_vs_call"],
        "bn_two_pair_or_trips_delta": None
        if "two_pair_or_trips" not in by_fam
        else by_fam["two_pair_or_trips"]["delta_3bet_vs_call"],
        "hypothesis_straight_calls": rec("straight") == "call",
        "hypothesis_flush_3bets": rec("flush") == "three_bet",
        "hypothesis_boat_3bets": rec("boat_plus") == "three_bet",
        "hypothesis_two_pair_trips_call": rec("two_pair_or_trips") == "call",
        "best_joint_on_node": {
            "bn_3bet": best_grid["bn_3bet"],
            "caller_vs_3bet": best_grid["caller_vs_3bet"],
            "ev_bn": best_grid["ev_bn"],
            "delta_vs_call_it_down": best_grid["delta_ev_bn_vs_call_it_down"],
        },
        "call_it_down_ev_bn": call_down["ev_bn"],
        "flush_plus_cap_sf_ev_bn": flush_sf["ev_bn"],
        "boat_plus_cap_sf_ev_bn": boat_sf["ev_bn"],
        "straight_plus_cap_sf_ev_bn": straight_sf["ev_bn"],
        "caller_vs_bn_flush_plus": {
            k: caller_rec(caller_vs_flush, k)
            for k in ("straight", "flush", "boat_plus")
            if k in caller_vs_flush
        },
        "caller_vs_bn_boat_plus": {
            k: caller_rec(caller_vs_boat, k)
            for k in ("straight", "flush", "boat_plus")
            if k in caller_vs_boat
        },
        "nonbluff_grid_excludes_cap": True,
        "caller_should_not_cap_non_sf_vs_boat": (
            caller_rec(caller_vs_boat, "straight") != "cap"
            and caller_rec(caller_vs_boat, "flush") != "cap"
        ),
    }


def build_recommendations(findings: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "side": "BN",
            "final": "two pair / trips",
            "vs_raise": "call (no 3-bet; bluff 3-bet out of scope)",
            "notes": (
                f"Δ 3-bet vs call={findings['bn_two_pair_or_trips_delta']} "
                "behind a raising straight+ range."
            ),
        },
        {
            "side": "BN",
            "final": "straight",
            "vs_raise": findings["bn_straight_recommend"] or "call",
            "notes": (
                f"Δ={findings['bn_straight_delta']}. "
                "Caller raise range is straight/flush/SF (flush-heavy 2:1 keeps)."
            ),
        },
        {
            "side": "BN",
            "final": "flush",
            "vs_raise": findings["bn_flush_recommend"] or "three_bet",
            "notes": (
                f"Δ={findings['bn_flush_delta']}. "
                "Value vs caller straights; still loses to SF (case 2)."
            ),
        },
        {
            "side": "BN",
            "final": "boat / quads / SF / five aces",
            "vs_raise": findings["bn_boat_plus_recommend"] or "three_bet",
            "notes": f"Δ={findings['bn_boat_plus_delta']}. Always ahead of caller straights.",
        },
        {
            "side": "caller",
            "final": "straight vs BN flush+ 3-bet",
            "vs_3bet": (findings["caller_vs_bn_flush_plus"].get("straight") or "call"),
            "notes": "Often behind a flush+ 3-bet range.",
        },
        {
            "side": "caller",
            "final": "flush vs BN flush+ 3-bet",
            "vs_3bet": (findings["caller_vs_bn_flush_plus"].get("flush") or "call"),
            "notes": "Ahead of BN straights (if those 3-bet) / some flushes; behind boats.",
        },
        {
            "side": "caller",
            "final": "non-SF vs BN boat+ 3-bet",
            "vs_3bet": (
                "fold/call, do not cap"
                if findings.get("caller_should_not_cap_non_sf_vs_boat")
                else "see table"
            ),
            "notes": f"vs boat+ 3-bet: {findings['caller_vs_bn_boat_plus']}",
        },
        {
            "side": "caller",
            "final": "straight flush",
            "vs_3bet": "cap",
            "notes": "Value vs BN flushes and boats; loses only to quads / five aces / better SF.",
        },
    ]


def run_analysis(
    *,
    n_range: int = DEFAULT_N_RANGE,
    n_per_class: int = DEFAULT_N_PER_CLASS,
    seed: int = DEFAULT_SEED,
    progress: bool = True,
    extra_classes: Sequence[str] | None = EXTRA_BN_CLASSES,
) -> dict[str, Any]:
    if progress:
        print("Loading 2:1 callers + BN opener inventory…")
    callers = load_call_2to1_hands(progress=progress)
    inventory = build_opener_inventory(progress=progress)

    if progress:
        print(f"Combo-weighted locked range ({n_range} deals, {LOCKED_BN_DRAW.name})…")
    weighted = generate_locked_range_deals(
        inventory,
        callers,
        caller_d=1,
        caller_class=CALLER_ALL,
        n_deals=n_range,
        seed=seed,
        draw_policy=LOCKED_BN_DRAW,
    )
    mass = node_mass_by_class(weighted)
    node_weighted = [d for d in weighted if on_raise_node(d)]
    if progress:
        print(f"  raise-node deals: {len(node_weighted)} / {len(weighted)}")

    extra: list[NonbluffDeal] = []
    use_extra = list(extra_classes) if extra_classes else []
    for cls in use_extra:
        if progress:
            print(f"  extra {cls} ({n_per_class} deals)…")
        extra.extend(
            generate_nonbluff_deals(
                inventory,
                callers,
                cls,
                LOCKED_BN_DRAW.n_draw_for(cls),
                caller_d=1,
                caller_class=CALLER_ALL,
                n_deals=n_per_class,
                seed=seed + 17 + sum(ord(c) for c in cls),
            )
        )
    node_extra = [d for d in extra if on_raise_node(d)]
    node_for_buckets = node_weighted + node_extra

    if progress:
        print(f"Policy grid on {len(node_weighted)} weighted node deals…")
    grid = policy_grid(node_weighted)

    bn_family = bn_unilateral_rows(
        node_for_buckets, caller=HOLD_CALLER, key_fn=family_bucket
    )
    bn_fine = bn_unilateral_rows(
        node_for_buckets, caller=HOLD_CALLER, key_fn=fine_bucket
    )
    _apply_sparse_recommend(bn_fine, bn_family)
    # Two pair / trips: never recommend 3-bet (bluff, out of scope).
    for row in bn_family + bn_fine:
        fam = row["bucket"] if row["bucket"] in {
            "two_pair_or_trips",
            "two_pair",
            "three_of_a_kind",
        } else _family_from_fine(row["bucket"])
        if fam == "two_pair_or_trips" or row["bucket"] in {
            "two_pair_or_trips",
            "two_pair",
            "three_of_a_kind",
        }:
            row["recommend"] = "call"
            row["bluff_3bet_out_of_scope"] = True

    caller_family_flush = caller_unilateral_rows(
        node_for_buckets, bn=HOLD_BN_FLUSH_PLUS, key_fn=family_bucket
    )
    caller_fine_flush = caller_unilateral_rows(
        node_for_buckets, bn=HOLD_BN_FLUSH_PLUS, key_fn=fine_bucket
    )
    _apply_sparse_recommend(caller_fine_flush, caller_family_flush)
    caller_family_boat = caller_unilateral_rows(
        node_for_buckets, bn=HOLD_BN_BOAT_PLUS, key_fn=family_bucket
    )
    caller_fine_boat = caller_unilateral_rows(
        node_for_buckets, bn=HOLD_BN_BOAT_PLUS, key_fn=fine_bucket
    )
    _apply_sparse_recommend(caller_fine_boat, caller_family_boat)

    findings = _derive_findings(
        mass=mass,
        grid=grid,
        bn_family=bn_family,
        bn_fine=bn_fine,
        caller_family_flush=caller_family_flush,
        caller_family_boat=caller_family_boat,
        n_range=len(weighted),
        n_node_weighted=len(node_weighted),
    )
    recs = build_recommendations(findings)

    # Sanity: call-it-down on the node via play_deal max_raises=1 matches
    # play_raise_node call (used as the non-bluff baseline).
    return {
        "meta": {
            "seed": seed,
            "n_range": len(weighted),
            "n_per_class_extra": n_per_class,
            "n_node_weighted": len(node_weighted),
            "n_node_with_extra": len(node_for_buckets),
            "predraw_pot": PREDRAW_POT,
            "big_bet": BIG,
            "cap_pot": CAP_POT,
            "max_raises_default_m2": 1,
            "max_raises_this_module": 3,
            "matchup": "BN (seat 8) opener vs one 2:1 drawing caller",
            "predraw": "open + call only (no raise)",
            "honest_m2_policy": HONEST_POLICY.key,
            "locked_bn_draw": {
                "name": LOCKED_BN_DRAW.name,
                "pair_d": LOCKED_BN_DRAW.pair_d,
                "two_pair_d": LOCKED_BN_DRAW.two_pair_d,
                "trips_d": LOCKED_BN_DRAW.trips_d,
                "quads_d": LOCKED_BN_DRAW.quads_d,
            },
            "hold_caller_vs_3bet": HOLD_CALLER.key,
            "node": "BN two_pair+ (bets) ∩ caller straight+ (raises)",
            "bluff_3bet_two_pair_trips": "out of scope",
            "doc": "docs/NEXT_STAGE_POSTDRAW_CAP.md",
            "regenerate": (
                "analyze-postdraw-cap --n-range 40000 --n-per-class 4000 --write-fixture"
            ),
            "notes": [
                "M2 / non-bluff EV tables stay bet+1 (call the raise). This module "
                "does not rewrite those cells.",
                "Unilateral BN Δ holds caller at cap SF / call rest.",
                "Unilateral caller Δ is reported vs BN flush+ 3-bet and vs BN boat+ 3-bet.",
            ],
        },
        "node_mass_by_class": mass,
        "policy_grid": grid,
        "bn_family": bn_family,
        "bn_fine": bn_fine,
        "caller_family_vs_bn_flush_plus": caller_family_flush,
        "caller_fine_vs_bn_flush_plus": caller_fine_flush,
        "caller_family_vs_bn_boat_plus": caller_family_boat,
        "caller_fine_vs_bn_boat_plus": caller_fine_boat,
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

    def slim_delta(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        keep = (
            "bucket",
            "n",
            "p_bn_wins",
            "ev_bn_call",
            "ev_bn_3bet",
            "delta_3bet_vs_call",
            "ev_caller_fold",
            "ev_caller_call",
            "ev_caller_cap",
            "delta_cap_vs_call",
            "delta_fold_vs_call",
            "recommend",
            "recommend_source",
            "bluff_3bet_out_of_scope",
        )
        out = []
        for r in rows:
            out.append({k: r[k] for k in keep if k in r})
        return out

    return round_obj(
        {
            "meta": payload["meta"],
            "node_mass_by_class": payload["node_mass_by_class"],
            "policy_grid": payload["policy_grid"],
            "bn_family": slim_delta(payload["bn_family"]),
            "bn_fine": slim_delta(payload["bn_fine"]),
            "caller_family_vs_bn_flush_plus": slim_delta(
                payload["caller_family_vs_bn_flush_plus"]
            ),
            "caller_fine_vs_bn_flush_plus": slim_delta(
                payload["caller_fine_vs_bn_flush_plus"]
            ),
            "caller_family_vs_bn_boat_plus": slim_delta(
                payload["caller_family_vs_bn_boat_plus"]
            ),
            "caller_fine_vs_bn_boat_plus": slim_delta(
                payload["caller_fine_vs_bn_boat_plus"]
            ),
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
        "# Post-draw cap (bet + 3 raises) on the BN-bet ∩ caller-straight+ node",
        "",
        f"BN vs one 2:1 caller. Seed `{meta['seed']}`, `{meta['n_range']}` "
        f"combo-weighted deals ({meta['n_node_weighted']} on the raise node). "
        f"Pot into draw `${meta['predraw_pot']}`, big bet `${meta['big_bet']}`, "
        f"full cap pot `${meta['cap_pot']}`.",
        "",
        "The non-bluff class × d table is **bet+1** (call the raise). These "
        "numbers are the 3-bet / cap extension of that node, not a replacement.",
        "",
        "Doc: `docs/NEXT_STAGE_POSTDRAW_CAP.md`.",
        "",
        "## Node mass (locked BN draws, combo-weighted)",
        "",
        f"P(raise node) = **{f['p_raise_node_locked_range']:.4f}** "
        f"({meta['n_node_weighted']} / {meta['n_range']}).",
        "",
        "| BN class | P(class) | P(BN bets) | P(caller straight+) | P(node) | P(class given node) |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in summary["node_mass_by_class"]:
        lines.append(
            f"| {r['opener_class']} | {r['p_class']:.4f} | {r['p_bn_bets']:.3f} | "
            f"{r['p_caller_straight_plus']:.3f} | {r['p_raise_node']:.3f} | "
            f"{r['p_class_given_node']:.3f} |"
        )
    lines += [
        "",
        "## BN 3-bet vs call (unilateral; caller caps SF, calls rest)",
        "",
        "| BN final | n | P(win) | EV call | EV 3-bet | Δ | Recommend |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for r in summary["bn_family"]:
        lines.append(
            f"| {r['bucket']} | {r['n']:.0f} | {r['p_bn_wins']:.3f} | "
            f"{r['ev_bn_call']:.3f} | {r['ev_bn_3bet']:.3f} | "
            f"{r['delta_3bet_vs_call']:+.3f} | {r['recommend']} |"
        )
    lines += [
        "",
        "Fine buckets (n < 50 inherit the family recommendation):",
        "",
        "| BN final | n | P(win) | Δ 3-bet vs call | Recommend |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for r in summary["bn_fine"]:
        src = r.get("recommend_source", "")
        rec = r["recommend"] + (f" ({src})" if src else "")
        lines.append(
            f"| {r['bucket']} | {r['n']:.0f} | {r['p_bn_wins']:.3f} | "
            f"{r['delta_3bet_vs_call']:+.3f} | {rec} |"
        )
    lines += [
        "",
        "## Caller vs BN 3-bet (unilateral)",
        "",
        "### Vs BN flush+ 3-bet",
        "",
        "| Caller final | n | fold | call | cap | Δ cap vs call | Recommend |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for r in summary["caller_family_vs_bn_flush_plus"]:
        lines.append(
            f"| {r['bucket']} | {r['n']:.0f} | {r['ev_caller_fold']:.3f} | "
            f"{r['ev_caller_call']:.3f} | {r['ev_caller_cap']:.3f} | "
            f"{r['delta_cap_vs_call']:+.3f} | {r['recommend']} |"
        )
    lines += [
        "",
        "### Vs BN boat+ 3-bet",
        "",
        "| Caller final | n | fold | call | cap | Δ cap vs call | Recommend |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for r in summary["caller_family_vs_bn_boat_plus"]:
        lines.append(
            f"| {r['bucket']} | {r['n']:.0f} | {r['ev_caller_fold']:.3f} | "
            f"{r['ev_caller_call']:.3f} | {r['ev_caller_cap']:.3f} | "
            f"{r['delta_cap_vs_call']:+.3f} | {r['recommend']} |"
        )
    lines += [
        "",
        "## Joint policy EV on the node (combo-weighted)",
        "",
        "| BN 3-bet | Caller vs 3-bet | EV_bn | EV_caller | P(3-bet) | P(cap) | Δ vs call-it-down |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in summary["policy_grid"]:
        lines.append(
            f"| {r['bn_3bet']} | {r['caller_vs_3bet']} | {r['ev_bn']:.3f} | "
            f"{r['ev_caller']:.3f} | {r['p_3bet']:.3f} | {r['p_cap']:.3f} | "
            f"{r['delta_ev_bn_vs_call_it_down']:+.3f} |"
        )
    lines += [
        "",
        "## Recommendations",
        "",
        "| Side | Hand | Action | Notes |",
        "| --- | --- | --- | --- |",
    ]
    for r in summary["recommendations"]:
        action = r.get("vs_raise") or r.get("vs_3bet") or ""
        lines.append(
            f"| {r['side']} | {r['final']} | {action} | {r['notes']} |"
        )
    lines += [
        "",
        "## Hypotheses",
        "",
        f"- BN straight calls (does not auto-3-bet): **{f['hypothesis_straight_calls']}** "
        f"(Δ={f['bn_straight_delta']})",
        f"- BN flush 3-bets: **{f['hypothesis_flush_3bets']}** (Δ={f['bn_flush_delta']})",
        f"- BN boat+ 3-bets: **{f['hypothesis_boat_3bets']}** (Δ={f['bn_boat_plus_delta']})",
        f"- Two pair/trips call only: **{f['hypothesis_two_pair_trips_call']}**",
        f"- Caller should not cap non-SF into boat+: **{f['caller_should_not_cap_non_sf_vs_boat']}**",
        "",
        "Call-it-down **does not** include this cap EV. Flush+ 3-bets move node "
        f"EV_bn from {f['call_it_down_ev_bn']} (call-it-down) toward "
        f"{f['flush_plus_cap_sf_ev_bn']} (flush+ / cap SF).",
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
        / "postdraw_cap_summary.json"
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
        description="Post-draw cap: BN 3-bet vs call when caller raises straight+"
    )
    p.add_argument("--n-range", type=int, default=DEFAULT_N_RANGE)
    p.add_argument("--n-per-class", type=int, default=DEFAULT_N_PER_CLASS)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--quick", action="store_true", help="Tiny sample for smoke runs")
    p.add_argument("-o", "--output", type=Path, default=None)
    p.add_argument(
        "--write-fixture",
        action="store_true",
        help="Refresh tests/fixtures/validation/postdraw_cap_summary.json",
    )
    args = p.parse_args()
    n_range = 2_000 if args.quick else args.n_range
    n_class = 400 if args.quick else args.n_per_class
    extra = EXTRA_BN_CLASSES if not args.quick else STRAIGHT_PLUS_CLASSES
    payload = run_analysis(
        n_range=n_range,
        n_per_class=n_class,
        seed=args.seed,
        progress=True,
        extra_classes=extra,
    )
    out = args.output or Path("outputs/validation/postdraw_cap.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out}")
    md = out.with_suffix(".md")
    write_markdown_summary(payload, md)
    print(f"Wrote {md}")
    if args.write_fixture:
        fix = write_summary_fixture(payload)
        print(f"Wrote fixture {fix}")
    print()
    f = payload["findings"]
    print(
        f"P(raise node)={f['p_raise_node_locked_range']:.4f}  "
        f"straight Δ={f['bn_straight_delta']} ({f['bn_straight_recommend']})  "
        f"flush Δ={f['bn_flush_delta']} ({f['bn_flush_recommend']})  "
        f"boat+ Δ={f['bn_boat_plus_delta']} ({f['bn_boat_plus_recommend']})"
    )


if __name__ == "__main__":
    main()
