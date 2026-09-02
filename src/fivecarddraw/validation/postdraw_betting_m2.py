"""M2 post-draw betting grid: opener-first face-pair knobs.

Assumptions (locked):
  - Pre-draw: open + call only; pot = $6 entering draw ($2 antes + $2 + $2).
  - Drawer always keep4 / draw 1 (2:1 range).
  - Opener non-breaking draws: pairs d=3, trips d=2, two pair stand, straight+ stand.
  - Post-draw: opener acts first; one street at big bet ($4).
  - Default max one bet + one raise (`max_raises=1`: drawer may raise; opener
    then call/fold). Pass `max_raises=3` plus a `CapPolicy` for BN 3-bet /
    caller cap (see `postdraw_cap.py`). Existing M2 / non-bluff CLIs stay at 1.

Knobs searched:
  - opener_lead_min: bet one-pair finals with pair rank >= this (None = never lead pairs)
  - drawer_stab_min: when checked to, bet face-pair finals with rank >= this
  - drawer_raise_min: when bet into, raise face-pair finals with rank >= this

Pinned non-knob behavior:
  - Default (`opener_auto_bet_min=TWO_PAIR`): opener always leads two pair+
    (historical M2 / non-bluff honest cell).
  - Stage C street (`opener_auto_bet_min=THREE_OF_A_KIND`): check two pair;
    still auto-bet trips+. Cap / 3-bet work uses this. Do **not** rewrite
    the checked-in M2 / non-bluff fixtures.
  - Drawer always leads/raises straight+ for value; misses check/fold.
  - Opener vs stab/raise with one pair: call iff pair rank >= opponent's min
    aggression rank for that line (matched bluff-catch); always continue with
    two pair+.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any, Sequence

from fivecarddraw.cards import card_from_id
from fivecarddraw.hand_rank import CATEGORY_NAMES, HandCategory, HandValue, evaluate_hand
from fivecarddraw.rules import DEFAULT_CONFIG, StreetState
from fivecarddraw.validation.draw_call_odds import DrawHandResult
from fivecarddraw.validation.showdown_matrix import (
    OPENER_CLASSES,
    build_opener_inventory,
    dealer_draw_plan,
    load_call_2to1_hands,
)


ANTE_POT = DEFAULT_CONFIG.starting_pot  # 2.0
PREDRAW_POT = ANTE_POT + 2 * DEFAULT_CONFIG.small_bet  # 6.0 after open+call
BIG = DEFAULT_CONFIG.big_bet  # 4.0
# Full cap: bet + 3 raises = four $4 increments each → $6 + $32 = $38.
CAP_POT = PREDRAW_POT + 8 * BIG

LEAD_LABELS = {
    None: "never",
    14: "AA",
    13: "AA+KK",
    12: "AA..QQ",
    11: "AA..JJ",
}
STAB_LABELS = {
    None: "never",
    14: "AA",
    13: "AA+KK",
    11: "AA..JJ",
}
RAISE_LABELS = {
    None: "never",
    14: "AA",
    13: "AA+KK",
}


def _cat_plus_label(min_cat: int | None) -> str:
    if min_cat is None:
        return "never"
    return CATEGORY_NAMES[HandCategory(min_cat)] + "+"


@dataclass(frozen=True, slots=True)
class CapPolicy:
    """Honest 3-bet / cap thresholds when `max_raises >= 3`.

    Categories are `HandCategory` ints. `None` means never take that action.
    Two pair / trips never 3-bet unless `opener_3bet_min` is set that low
    (bluff 3-bets are out of scope for the cap study).
    """

    opener_3bet_min: int | None = None  # 3-bet a raise if category >= min
    drawer_cap_min: int | None = None  # cap a 3-bet if category >= min
    drawer_call_3bet_min: int | None = HandCategory.STRAIGHT  # fold below
    opener_call_cap_min: int | None = HandCategory.TWO_PAIR  # fold cap below

    @property
    def key(self) -> str:
        return (
            f"3bet={_cat_plus_label(self.opener_3bet_min)}|"
            f"cap={_cat_plus_label(self.drawer_cap_min)}|"
            f"call3={_cat_plus_label(self.drawer_call_3bet_min)}"
        )

    def opener_three_bets(self, v: HandValue) -> bool:
        return (
            self.opener_3bet_min is not None and v.category >= self.opener_3bet_min
        )

    def opener_calls_cap(self, v: HandValue) -> bool:
        return (
            self.opener_call_cap_min is not None
            and v.category >= self.opener_call_cap_min
        )

    def caller_vs_three_bet(self, v: HandValue) -> str:
        """Return 'fold', 'call', or 'cap' given the caller's final."""
        if (
            self.drawer_call_3bet_min is not None
            and v.category < self.drawer_call_3bet_min
        ):
            return "fold"
        if self.drawer_cap_min is not None and v.category >= self.drawer_cap_min:
            return "cap"
        return "call"


# Default: call the raise, never 3-bet / never cap (today's M2 street).
CALL_IT_DOWN = CapPolicy()


@dataclass(frozen=True, slots=True)
class Policy:
    opener_lead_min: int | None  # bet one-pair if rank >= min
    drawer_stab_min: int | None  # bet face-pair when checked to
    drawer_raise_min: int | None  # raise face-pair when bet into
    # Category at which BN auto-bets (not a one-pair lead). TWO_PAIR = honest
    # M2; THREE_OF_A_KIND = Stage C (check two pair).
    opener_auto_bet_min: int = int(HandCategory.TWO_PAIR)

    @property
    def key(self) -> str:
        base = (
            f"lead={LEAD_LABELS[self.opener_lead_min]}|"
            f"stab={STAB_LABELS[self.drawer_stab_min]}|"
            f"raise={RAISE_LABELS[self.drawer_raise_min]}"
        )
        if self.opener_auto_bet_min <= int(HandCategory.TWO_PAIR):
            return base
        return f"{base}|auto_bet={CATEGORY_NAMES[self.opener_auto_bet_min]}"


# Forward street after Stage C. M2 / non-bluff CLIs keep HONEST_POLICY (two pair bets).
STAGE_C_POLICY = Policy(
    opener_lead_min=None,
    drawer_stab_min=14,
    drawer_raise_min=None,
    opener_auto_bet_min=int(HandCategory.THREE_OF_A_KIND),
)


def bn_bets_stage_c(deal: Deal) -> bool:
    """Stage C first action: bet trips+; check two pair and one pair."""
    return deal.opener_final.category >= HandCategory.THREE_OF_A_KIND


@dataclass(slots=True)
class Deal:
    opener_class: str
    opener_start_pair: int | None  # if started as one pair
    d: int
    opener_final: HandValue
    drawer_final: HandValue
    opener_final_pair: int | None
    drawer_final_pair: int | None  # face pair only (J+) or None
    drawer_straight_plus: bool
    opener_two_pair_plus: bool


@dataclass(slots=True)
class StreetStats:
    n: float = 0.0
    opener_ev: float = 0.0
    # line frequencies (weight = deals)
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

    def add(self, ev: float, **flags: bool) -> None:
        self.n += 1.0
        self.opener_ev += ev
        for k, v in flags.items():
            if v and hasattr(self, k):
                setattr(self, k, getattr(self, k) + 1.0)

    def as_dict(self) -> dict[str, float]:
        n = self.n or 1.0
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
        }


def _face_pair_rank(v: HandValue) -> int | None:
    if v.category == HandCategory.ONE_PAIR and v.tiebreak[0] >= 11:
        return v.tiebreak[0]
    return None


def _one_pair_rank(v: HandValue) -> int | None:
    if v.category == HandCategory.ONE_PAIR:
        return v.tiebreak[0]
    return None


def _sample_disjoint_caller(
    callers: Sequence[DrawHandResult], blocked: set[int], rng: random.Random
) -> DrawHandResult | None:
    n = len(callers)
    for _ in range(60):
        c = callers[rng.randrange(n)]
        if blocked.isdisjoint(x.card_id for x in c.cards):
            return c
    start = rng.randrange(n)
    for k in range(n):
        c = callers[(start + k) % n]
        if blocked.isdisjoint(x.card_id for x in c.cards):
            return c
    return None


def generate_deals(
    inventory: dict[str, list[tuple[int, ...]]],
    callers: Sequence[DrawHandResult],
    *,
    n_deals: int,
    seed: int,
    classes: Sequence[str] | None = None,
) -> list[Deal]:
    """Combo-weighted MC deals through the draw (before betting)."""
    rng = random.Random(seed)
    use = list(classes) if classes else list(OPENER_CLASSES)
    weights = [len(inventory[c]) for c in use]
    if sum(weights) == 0:
        return []
    deals: list[Deal] = []
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
        plan = dealer_draw_plan(cards, cls)
        rem = [i for i in range(53) if i not in blocked and i not in {
            c.card_id for c in caller.cards
        }]
        need = plan.n_draw + 1
        if len(rem) < need:
            continue
        rng.shuffle(rem)
        # Drawer draws first (left of dealer), then opener.
        c_card = rem[0]
        d_cards = rem[1 : 1 + plan.n_draw]
        opener_final = evaluate_hand((*plan.keep, *(card_from_id(i) for i in d_cards)))
        drawer_final = evaluate_hand((*caller.keep, card_from_id(c_card)))
        start_pair = _PAIR_RANK_FROM_CLASS(cls)
        deals.append(
            Deal(
                opener_class=cls,
                opener_start_pair=start_pair,
                d=plan.n_draw,
                opener_final=opener_final,
                drawer_final=drawer_final,
                opener_final_pair=_one_pair_rank(opener_final),
                drawer_final_pair=_face_pair_rank(drawer_final),
                drawer_straight_plus=drawer_final.category >= HandCategory.STRAIGHT,
                opener_two_pair_plus=opener_final.category >= HandCategory.TWO_PAIR,
            )
        )
    return deals


def _PAIR_RANK_FROM_CLASS(cls: str) -> int | None:
    return {"pair_J": 11, "pair_Q": 12, "pair_K": 13, "pair_A": 14}.get(cls)


def postdraw_initial_state(max_raises: int = 1) -> StreetState:
    """Empty post-draw street: pot $6, nothing in yet."""
    return StreetState(
        pot=PREDRAW_POT,
        bet_size=BIG,
        amount_to_call=0.0,
        raises_used=0,
        max_raises=max_raises,
        opener_seat=None,
    )


def street_after_bet_and_raise(max_raises: int = 3) -> StreetState:
    """BN has bet $4, caller has raised. BN faces $4 into $18."""
    return postdraw_initial_state(max_raises).after_open(seat=7).after_raise()


def showdown_ev_bn(
    opener: HandValue, drawer: HandValue, o_in: float, pot: float
) -> float:
    if opener > drawer:
        return -o_in + pot
    if opener < drawer:
        return -o_in
    return -o_in + pot / 2.0


def play_raise_node(
    deal: Deal,
    *,
    bn_vs_raise: str,
    caller_vs_3bet: str = "call",
    bn_vs_cap: str = "call",
    max_raises: int = 3,
) -> tuple[float, dict[str, bool]]:
    """BN EV from post-draw start, given this deal is already a raise node.

    Chip path: BN already bet, caller already raised (`street_after_bet_and_raise`).
    `bn_vs_raise` is 'fold' | 'call' | 'three_bet'.
    `caller_vs_3bet` is 'fold' | 'call' | 'cap'.
    `bn_vs_cap` is 'fold' | 'call'.
    """
    flags = {
        "drawer_raise": True,
        "opener_fold_to_raise": False,
        "opener_call_raise": False,
        "opener_3bet": False,
        "drawer_fold_to_3bet": False,
        "drawer_call_3bet": False,
        "drawer_cap": False,
        "opener_fold_to_cap": False,
        "opener_call_cap": False,
        "showdown": False,
        "opener_wins_sd": False,
    }
    st = street_after_bet_and_raise(max_raises)
    o_in = BIG

    if bn_vs_raise == "fold":
        flags["opener_fold_to_raise"] = True
        return -o_in, flags

    if bn_vs_raise == "call":
        flags["opener_call_raise"] = True
        st = st.after_call()
        o_in += st.bet_size
        flags["showdown"] = True
        ev = showdown_ev_bn(deal.opener_final, deal.drawer_final, o_in, st.pot)
        flags["opener_wins_sd"] = deal.opener_final > deal.drawer_final
        return ev, flags

    if bn_vs_raise != "three_bet":
        raise ValueError(f"unknown bn_vs_raise: {bn_vs_raise}")
    if not st.can_raise:
        raise ValueError("cannot 3-bet: raise cap reached")

    flags["opener_3bet"] = True
    add = st.amount_to_call + st.bet_size
    st = st.after_raise()
    o_in += add

    if caller_vs_3bet == "fold":
        flags["drawer_fold_to_3bet"] = True
        return -o_in + st.pot, flags

    if caller_vs_3bet == "call":
        flags["drawer_call_3bet"] = True
        st = st.after_call()
        flags["showdown"] = True
        ev = showdown_ev_bn(deal.opener_final, deal.drawer_final, o_in, st.pot)
        flags["opener_wins_sd"] = deal.opener_final > deal.drawer_final
        return ev, flags

    if caller_vs_3bet != "cap":
        raise ValueError(f"unknown caller_vs_3bet: {caller_vs_3bet}")
    if not st.can_raise:
        raise ValueError("cannot cap: raise cap reached")

    flags["drawer_cap"] = True
    st = st.after_raise()

    if bn_vs_cap == "fold":
        flags["opener_fold_to_cap"] = True
        return -o_in, flags

    if bn_vs_cap != "call":
        raise ValueError(f"unknown bn_vs_cap: {bn_vs_cap}")
    flags["opener_call_cap"] = True
    st = st.after_call()
    o_in += st.bet_size
    flags["showdown"] = True
    ev = showdown_ev_bn(deal.opener_final, deal.drawer_final, o_in, st.pot)
    flags["opener_wins_sd"] = deal.opener_final > deal.drawer_final
    return ev, flags


def play_deal(
    deal: Deal,
    policy: Policy,
    *,
    max_raises: int = 1,
    cap_policy: CapPolicy | None = None,
) -> tuple[float, dict[str, bool]]:
    """Opener net chips from post-draw start (pot already PREDRAW_POT).

    Δ = -postdraw_invested + (pot if win) + (pot/2 if tie); folds award pot.

    `max_raises=1` (default) is the M2 / non-bluff street: bet + one raise,
    then call/fold. `max_raises=3` plus a `CapPolicy` enables BN 3-bet and
    caller cap. `cap_policy=None` is call-it-down (never 3-bet).
    """
    cap_policy = cap_policy or CALL_IT_DOWN
    flags = {
        "opener_pair_lead": False,
        "opener_pair_check": False,
        "drawer_stab": False,
        "drawer_raise": False,
        "opener_fold_to_stab": False,
        "opener_call_stab": False,
        "opener_fold_to_raise": False,
        "opener_call_raise": False,
        "opener_3bet": False,
        "drawer_fold_to_3bet": False,
        "drawer_call_3bet": False,
        "drawer_cap": False,
        "opener_fold_to_cap": False,
        "opener_call_cap": False,
        "showdown": False,
        "opener_wins_sd": False,
    }
    pot = PREDRAW_POT
    o_in = 0.0

    o_pair = deal.opener_final_pair
    d_face = deal.drawer_final_pair
    o_strong = deal.opener_two_pair_plus
    d_sp = deal.drawer_straight_plus
    is_job_pair = o_pair is not None and o_pair >= 11 and not o_strong

    opener_bets = False
    if deal.opener_final.category >= policy.opener_auto_bet_min:
        opener_bets = True
    elif is_job_pair:
        if policy.opener_lead_min is not None and o_pair >= policy.opener_lead_min:
            opener_bets = True
            flags["opener_pair_lead"] = True
        else:
            flags["opener_pair_check"] = True

    if opener_bets:
        o_in += BIG
        pot += BIG
        # Drawer: raise straight+ or face-pair >= raise_min; else call face pair; else fold
        if d_sp or (
            d_face is not None
            and policy.drawer_raise_min is not None
            and d_face >= policy.drawer_raise_min
        ):
            call = o_strong or (
                o_pair is not None
                and policy.drawer_raise_min is not None
                and o_pair >= policy.drawer_raise_min
            )
            if not call:
                flags["drawer_raise"] = True
                flags["opener_fold_to_raise"] = True
                return -o_in, flags
            three_bet = (
                max_raises > 1 and cap_policy.opener_three_bets(deal.opener_final)
            )
            bn_act = "three_bet" if three_bet else "call"
            caller_act = (
                cap_policy.caller_vs_three_bet(deal.drawer_final)
                if three_bet
                else "call"
            )
            bn_cap = (
                "call" if cap_policy.opener_calls_cap(deal.opener_final) else "fold"
            )
            ev, node_flags = play_raise_node(
                deal,
                bn_vs_raise=bn_act,
                caller_vs_3bet=caller_act,
                bn_vs_cap=bn_cap,
                max_raises=max_raises,
            )
            flags.update(node_flags)
            return ev, flags
        elif d_face is not None:
            pot += BIG
            flags["showdown"] = True
        else:
            return -o_in + pot, flags
    else:
        stab = d_sp or (
            d_face is not None
            and policy.drawer_stab_min is not None
            and d_face >= policy.drawer_stab_min
        )
        if stab:
            flags["drawer_stab"] = True
            pot += BIG
            call = o_strong or (
                o_pair is not None
                and policy.drawer_stab_min is not None
                and o_pair >= policy.drawer_stab_min
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


def evaluate_policy(
    deals: Sequence[Deal], policy: Policy, *, subset: str = "all"
) -> StreetStats:
    stats = StreetStats()
    for deal in deals:
        if subset == "pair_final_d3":
            if not (
                deal.d == 3
                and deal.opener_final_pair is not None
                and deal.opener_final_pair >= 11
                and not deal.opener_two_pair_plus
            ):
                continue
        elif subset == "started_pair":
            if deal.opener_start_pair is None:
                continue
        elif subset.startswith("class:"):
            if deal.opener_class != subset.split(":", 1)[1]:
                continue
        ev, flags = play_deal(deal, policy)
        stats.add(ev, **flags)
    return stats


def all_policies() -> list[Policy]:
    leads = [None, 14, 13, 12, 11]
    stabs = [None, 14, 13, 11]
    raises = [None, 14, 13]
    return [Policy(l, s, r) for l, s, r in product(leads, stabs, raises)]


def run_grid(
    *,
    n_deals: int = 20_000,
    seed: int = 20260808,
    progress: bool = True,
) -> dict[str, Any]:
    if progress:
        print("Loading callers + opener inventory…")
    callers = load_call_2to1_hands(progress=progress)
    inventory = build_opener_inventory(progress=progress)
    if progress:
        print(f"Generating {n_deals} deals…")
    deals = generate_deals(inventory, callers, n_deals=n_deals, seed=seed)
    policies = all_policies()
    if progress:
        print(f"Evaluating {len(policies)} policies on {len(deals)} deals…")

    subsets = (
        "all",
        "started_pair",
        "pair_final_d3",
        "class:pair_A",
        "class:pair_K",
        "class:pair_Q",
        "class:pair_J",
    )
    rows = []
    for pol in policies:
        row: dict[str, Any] = {
            "policy": pol.key,
            "opener_lead_min": pol.opener_lead_min,
            "drawer_stab_min": pol.drawer_stab_min,
            "drawer_raise_min": pol.drawer_raise_min,
            "lead": LEAD_LABELS[pol.opener_lead_min],
            "stab": STAB_LABELS[pol.drawer_stab_min],
            "raise": RAISE_LABELS[pol.drawer_raise_min],
        }
        for sub in subsets:
            st = evaluate_policy(deals, pol, subset=sub)
            row[sub] = st.as_dict()
        rows.append(row)

    # Rank by opener EV on pair_final_d3 and on all
    def top(sub: str, k: int = 8) -> list[dict[str, Any]]:
        ranked = sorted(rows, key=lambda r: r[sub]["opener_ev"], reverse=True)
        return [
            {
                "policy": r["policy"],
                "ev": r[sub]["opener_ev"],
                "n": r[sub]["n"],
                "lead_rate": r[sub]["opener_pair_lead_rate"],
                "stab_rate": r[sub]["drawer_stab_rate"],
                "raise_rate": r[sub]["drawer_raise_rate"],
            }
            for r in ranked[:k]
        ]

    # Marginal effects: fix two knobs at baseline, sweep one
    baseline = Policy(opener_lead_min=None, drawer_stab_min=None, drawer_raise_min=None)
    by_key = {r["policy"]: r for r in rows}

    def sweep(axis: str) -> list[dict[str, Any]]:
        out = []
        if axis == "lead":
            for lead in [None, 14, 13, 12, 11]:
                # average over all stab/raise, and also vs passive drawer
                passive = Policy(lead, None, None)
                r = by_key[passive.key]
                out.append(
                    {
                        "lead": LEAD_LABELS[lead],
                        "vs_passive_drawer_ev_d3": r["pair_final_d3"]["opener_ev"],
                        "vs_passive_drawer_ev_all": r["all"]["opener_ev"],
                        "vs_AA_stab_no_raise": by_key[Policy(lead, 14, None).key][
                            "pair_final_d3"
                        ]["opener_ev"],
                        "vs_AAJJ_stab_AAKK_raise": by_key[Policy(lead, 11, 13).key][
                            "pair_final_d3"
                        ]["opener_ev"],
                    }
                )
        elif axis == "stab":
            for stab in [None, 14, 13, 11]:
                # opener checks pairs (lead never)
                r0 = by_key[Policy(None, stab, None).key]
                r1 = by_key[Policy(14, stab, None).key]
                r2 = by_key[Policy(11, stab, None).key]
                out.append(
                    {
                        "stab": STAB_LABELS[stab],
                        "ev_d3_if_opener_never_leads": r0["pair_final_d3"]["opener_ev"],
                        "ev_d3_if_opener_leads_AA": r1["pair_final_d3"]["opener_ev"],
                        "ev_d3_if_opener_leads_J+": r2["pair_final_d3"]["opener_ev"],
                        "stab_rate_if_check": r0["pair_final_d3"]["drawer_stab_rate"],
                    }
                )
        elif axis == "raise":
            for raise_min in [None, 14, 13]:
                r_aa = by_key[Policy(14, None, raise_min).key]
                r_j = by_key[Policy(11, None, raise_min).key]
                out.append(
                    {
                        "raise": RAISE_LABELS[raise_min],
                        "ev_d3_lead_AA": r_aa["pair_final_d3"]["opener_ev"],
                        "ev_d3_lead_J+": r_j["pair_final_d3"]["opener_ev"],
                        "raise_rate_lead_AA": r_aa["pair_final_d3"]["drawer_raise_rate"],
                        "raise_rate_lead_J+": r_j["pair_final_d3"]["drawer_raise_rate"],
                    }
                )
        return out

    return {
        "meta": {
            "predraw_pot": PREDRAW_POT,
            "big_bet": BIG,
            "n_deals": len(deals),
            "seed": seed,
            "opener_first": True,
            "drawer_range": "call_2to1",
            "baseline_policy": baseline.key,
            "notes": [
                "Opener always value-bets two pair+",
                "Drawer always value-raises/bets straight+",
                "One-pair call-downs match the drawer's aggression min rank",
            ],
        },
        "top_by_pair_final_d3": top("pair_final_d3"),
        "top_by_all": top("all"),
        "bottom_by_pair_final_d3": sorted(
            (
                {
                    "policy": r["policy"],
                    "ev": r["pair_final_d3"]["opener_ev"],
                    "n": r["pair_final_d3"]["n"],
                }
                for r in rows
            ),
            key=lambda x: x["ev"],
        )[:8],
        "sweep_lead": sweep("lead"),
        "sweep_stab": sweep("stab"),
        "sweep_raise": sweep("raise"),
        "rows": rows,
    }


def write_markdown_summary(payload: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# M2 post-draw face-pair grid (opener first)",
        "",
        f"Deals: {payload['meta']['n_deals']}, pot into draw `${payload['meta']['predraw_pot']}`, "
        f"big bet `${payload['meta']['big_bet']}`.",
        "",
        "Narrative findings: `docs/POSTDRAW_M2_FACE_PAIR_GRID.md`.",
        "",
        "## Lead sweep (opener one-pair bet threshold)",
        "",
        "| Lead | EV d3 vs passive | EV d3 vs AA stab | EV d3 vs stab J+ & raise KK+ |",
        "| --- | ---: | ---: | ---: |",
    ]
    for r in payload["sweep_lead"]:
        lines.append(
            f"| {r['lead']} | {r['vs_passive_drawer_ev_d3']:.4f} | "
            f"{r['vs_AA_stab_no_raise']:.4f} | {r['vs_AAJJ_stab_AAKK_raise']:.4f} |"
        )
    lines += [
        "",
        "## Stab sweep (drawer bets face pair when checked to)",
        "",
        "| Stab | Stab rate | EV if opener never leads | EV if leads AA | EV if leads J+ |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for r in payload["sweep_stab"]:
        lines.append(
            f"| {r['stab']} | {r['stab_rate_if_check']:.3f} | "
            f"{r['ev_d3_if_opener_never_leads']:.4f} | "
            f"{r['ev_d3_if_opener_leads_AA']:.4f} | "
            f"{r['ev_d3_if_opener_leads_J+']:.4f} |"
        )
    lines += [
        "",
        "## Raise sweep (drawer raises face pair when bet into)",
        "",
        "| Raise | Rate vs AA lead | EV lead AA | Rate vs J+ lead | EV lead J+ |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for r in payload["sweep_raise"]:
        lines.append(
            f"| {r['raise']} | {r['raise_rate_lead_AA']:.3f} | {r['ev_d3_lead_AA']:.4f} | "
            f"{r['raise_rate_lead_J+']:.3f} | {r['ev_d3_lead_J+']:.4f} |"
        )
    lines += [
        "",
        "## Best policies on pair-final d=3 nodes",
        "",
        "| Policy | EV | Lead rate | Stab rate | Raise rate |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for r in payload["top_by_pair_final_d3"]:
        lines.append(
            f"| `{r['policy']}` | {r['ev']:.4f} | {r['lead_rate']:.3f} | "
            f"{r['stab_rate']:.3f} | {r['raise_rate']:.3f} |"
        )
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def default_summary_fixture_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "validation"
        / "postdraw_m2_grid_summary.json"
    )


def build_summary_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Compact checked-in summary (no per-policy row dump)."""
    by_lead = {r["lead"]: r for r in payload["sweep_lead"]}

    def round_row(row: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in row.items():
            if isinstance(v, float):
                out[k] = round(v, 4)
            else:
                out[k] = v
        return out

    return {
        "meta": {
            "predraw_pot": payload["meta"]["predraw_pot"],
            "big_bet": payload["meta"]["big_bet"],
            "n_deals": payload["meta"]["n_deals"],
            "seed": payload["meta"]["seed"],
            "opener_first": payload["meta"]["opener_first"],
            "drawer_range": payload["meta"]["drawer_range"],
            "doc": "docs/POSTDRAW_M2_FACE_PAIR_GRID.md",
            "regenerate": "analyze-postdraw-m2 --n-deals 25000 --write-fixture",
            "notes": payload["meta"]["notes"],
        },
        "findings": {
            "default_check_one_pair": True,
            "lead_aa_only_vs_passive_delta_d3": round(
                by_lead["AA"]["vs_passive_drawer_ev_d3"]
                - by_lead["never"]["vs_passive_drawer_ev_d3"],
                4,
            ),
            "lead_jplus_vs_passive_delta_d3": round(
                by_lead["AA..JJ"]["vs_passive_drawer_ev_d3"]
                - by_lead["never"]["vs_passive_drawer_ev_d3"],
                4,
            ),
            "lead_aa_vs_aa_stab_delta_d3": round(
                by_lead["AA"]["vs_AA_stab_no_raise"]
                - by_lead["never"]["vs_AA_stab_no_raise"],
                4,
            ),
        },
        "sweep_lead": [round_row(r) for r in payload["sweep_lead"]],
        "sweep_stab": [round_row(r) for r in payload["sweep_stab"]],
        "sweep_raise": [round_row(r) for r in payload["sweep_raise"]],
        "top_by_pair_final_d3": [round_row(r) for r in payload["top_by_pair_final_d3"]],
        "bottom_by_pair_final_d3": [
            round_row(r) for r in payload["bottom_by_pair_final_d3"]
        ],
    }


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

    p = argparse.ArgumentParser(description="M2 opener-first face-pair betting grid")
    p.add_argument("--n-deals", type=int, default=20_000)
    p.add_argument("--seed", type=int, default=20260808)
    p.add_argument("--quick", action="store_true")
    p.add_argument("-o", "--output", type=Path, default=None)
    p.add_argument(
        "--write-fixture",
        action="store_true",
        help="Also refresh tests/fixtures/validation/postdraw_m2_grid_summary.json",
    )
    args = p.parse_args()
    n = 4_000 if args.quick else args.n_deals
    payload = run_grid(n_deals=n, seed=args.seed, progress=True)
    out = args.output or Path("outputs/validation/postdraw_m2_grid.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md = out.with_suffix(".md")
    write_markdown_summary(payload, md)
    print(f"Wrote {out}")
    print(f"Wrote {md}")
    if args.write_fixture:
        fix = write_summary_fixture(payload)
        print(f"Wrote fixture {fix}")
    print()
    print("Lead sweep (EV on pair-final d=3):")
    for r in payload["sweep_lead"]:
        print(
            f"  lead={r['lead']:<7} passive={r['vs_passive_drawer_ev_d3']:+.4f}  "
            f"AA_stab={r['vs_AA_stab_no_raise']:+.4f}  "
            f"agg={r['vs_AAJJ_stab_AAKK_raise']:+.4f}"
        )
    print("Stab sweep:")
    for r in payload["sweep_stab"]:
        print(
            f"  stab={r['stab']:<7} never_lead={r['ev_d3_if_opener_never_leads']:+.4f}  "
            f"lead_AA={r['ev_d3_if_opener_leads_AA']:+.4f}  "
            f"lead_J+={r['ev_d3_if_opener_leads_J+']:+.4f}"
        )
    print("Raise sweep:")
    for r in payload["sweep_raise"]:
        print(
            f"  raise={r['raise']:<7} lead_AA={r['ev_d3_lead_AA']:+.4f}  "
            f"lead_J+={r['ev_d3_lead_J+']:+.4f}"
        )


if __name__ == "__main__":
    main()
