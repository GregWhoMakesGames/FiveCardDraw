"""Cutoff open / pass with BN behind (0% sandbag in seats 1–6).

Frame: ``cutoff_open_no_sandbagging``
(docs/NEXT_STAGE_SANDBAG_AND_CO.md Agent B).

Seats 1–6 cannot open. CO (7) holds a legal hand. BN (8) behind:
  - if CO passes, BN opens every legal hand;
  - if CO opens, BN always *calls* every legal hand (does not fold legal).

This module does **not** overwrite ``postdraw_nonbluff_ev.py``. The CO-vs-2:1
deal loop is a copy with a ``drawer_is_bn`` flag; CO-vs-BN made-hand deals are
new. Agent A's ``sandbag_v1.py`` is not edited — the v1 HJ+CO predicate is
duplicated here.
"""

from __future__ import annotations

import json
import random
import zlib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from fivecarddraw.cards import BUG_ID, card_from_id
from fivecarddraw.hand_rank import HandCategory, HandValue, evaluate_hand
from fivecarddraw.validation.cascade_odds import (
    CALL_2TO1_COMBOS,
    TOTAL_HANDS,
    p_any_of_seats_2to1_independent,
    p_one_seat_2to1,
)
from fivecarddraw.validation.draw_call_odds import DrawHandResult
from fivecarddraw.validation.postdraw_betting_m2 import (
    PREDRAW_POT,
    _face_pair_rank,
    _one_pair_rank,
    _sample_disjoint_caller,
)
from fivecarddraw.validation.postdraw_draw_mixes import opener_draw_plan_for_action
from fivecarddraw.validation.postdraw_nonbluff_ev import (
    HONEST_POLICY,
    LOCKED_BN_DRAW,
    NonbluffDeal,
    load_summary_fixture as load_nonbluff_fixture,
    play_honest_deal,
)
from fivecarddraw.validation.showdown_matrix import (
    STRAIGHT_PLUS_CLASSES,
    TRIPS_CLASSES,
    TWO_PAIR_CLASSES,
    classify_opener,
    load_call_2to1_hands,
)


DEFAULT_SEED = 20260907
DEFAULT_N_PROB = 20_000
DEFAULT_N_HU = 4_000
DEFAULT_N_2TO1 = 2_000

STEAL_EV = 2.0
FOLD_TO_RAISE_EV = -2.0  # accounting pin; unused while BN never raises in v1
PASS_EV = 0.0
CO_SEAT = 7
BN_SEAT = 8
HJ_SEAT = 6
SEATS_1_6 = (1, 2, 3, 4, 5, 6)
SANDBAG_V1_ACES_SEATS = frozenset({HJ_SEAT, CO_SEAT})

# Product questions: JJ first, then AA / two pair (sandbag-set). QQ/KK are
# free on the same pipeline.
FOCUS_CLASSES = ("pair_J", "pair_Q", "pair_K", "pair_A", "two_pair")

# Enumerated open-legal mass (showdown_matrix opener_combo_counts).
OPEN_LEGAL_COMBOS = 642_881
P_OPEN_UNCOND = OPEN_LEGAL_COMBOS / TOTAL_HANDS
P_2TO1_UNCOND = CALL_2TO1_COMBOS / TOTAL_HANDS


# --- Sandbag-set v1 (import Agent A if present; else duplicate the pin) --------


def _in_sandbag_set_v1_local(opener_class: str | None, seat: int) -> bool:
    """100% sandbag-set: two pair+ in seats 1–7; HJ and CO also sandbag AA.

    This frame is 0% sandbag in seats 1–6, so HJ still *opens* AA here.
    The predicate is CO's own sandbag question (seat 7) plus the global pin.
    """
    if opener_class is None:
        return False
    if (
        opener_class in TWO_PAIR_CLASSES
        or opener_class in TRIPS_CLASSES
        or opener_class in STRAIGHT_PLUS_CLASSES
    ):
        return True
    return opener_class == "pair_A" and seat in SANDBAG_V1_ACES_SEATS


try:
    from fivecarddraw.validation.sandbag_v1 import is_sandbag_set as in_sandbag_set_v1
except ImportError:
    in_sandbag_set_v1 = _in_sandbag_set_v1_local


def is_co_sandbag_class(opener_class: str) -> bool:
    return in_sandbag_set_v1(opener_class, CO_SEAT)


def _cell_seed(base: int, *parts: object) -> int:
    payload = "|".join(str(p) for p in parts)
    return (base + (zlib.adler32(payload.encode("utf-8")) % 1_000_003)) % (2**31)


def _pair_rank_from_class(cls: str) -> int | None:
    return {"pair_J": 11, "pair_Q": 12, "pair_K": 13, "pair_A": 14}.get(cls)


# --- Planning probabilities (independent seats; CO-bug split) -------------------


def planning_behind_co(*, co_has_bug: bool) -> dict[str, float]:
    """Independent-seat planning given only whether CO holds the bug.

    ``p_one_seat_2to1(bn_has_bug=…)`` is reused as a *blocker split*: a known
    five-card hand holding (or not) the bug. The closed form still uses a
    uniform 5-set of 52 (not 48) cards, so this is planning, not the MC pin.
    """
    p_one = p_one_seat_2to1(bn_has_bug=co_has_bug)
    return {
        "p_open_uncond": P_OPEN_UNCOND,
        "p_2to1_uncond": P_2TO1_UNCOND,
        "p_one_seat_2to1_approx": p_one,
        "p_bn_2to1_approx": p_one,
        "p_any_of_1_6_2to1_approx": p_any_of_seats_2to1_independent(p_one, 6),
        "p_bn_open_legal_approx": P_OPEN_UNCOND,
    }


# --- Deal classification --------------------------------------------------------


def two_to_one_id_set(callers: Sequence[DrawHandResult]) -> set[frozenset[int]]:
    return {frozenset(c.card_id for c in h.cards) for h in callers}


def classify_seat_ids(
    ids: Sequence[int], two_to_one: set[frozenset[int]] | None = None
) -> str:
    """Return ``open_legal``, ``two_to_one``, or ``neither``."""
    cards = tuple(card_from_id(i) for i in ids)
    if classify_opener(cards) is not None:
        return "open_legal"
    if two_to_one is not None and frozenset(ids) in two_to_one:
        return "two_to_one"
    return "neither"


def sample_class_ids(
    opener_class: str, rng: random.Random, *, blocked: set[int] | None = None
) -> tuple[int, ...] | None:
    """Rejection-sample a uniform 5-set of ``opener_class`` (combo-weighted)."""
    blocked = blocked or set()
    pool = [i for i in range(53) if i not in blocked]
    if len(pool) < 5:
        return None
    for _ in range(8_000):
        ids = tuple(sorted(rng.sample(pool, 5)))
        cards = tuple(card_from_id(i) for i in ids)
        if classify_opener(cards) == opener_class:
            return ids
    return None


def sample_open_legal_ids(
    rng: random.Random, *, blocked: set[int]
) -> tuple[tuple[int, ...], str] | None:
    pool = [i for i in range(53) if i not in blocked]
    if len(pool) < 5:
        return None
    for _ in range(80):
        ids = tuple(sorted(rng.sample(pool, 5)))
        cards = tuple(card_from_id(i) for i in ids)
        cls = classify_opener(cards)
        if cls is not None:
            return ids, cls
    return None


# --- (a) BN behind: deal MC with CO's hand blocked ------------------------------


@dataclass(slots=True)
class BehindAccum:
    n: float = 0.0
    bn_legal: float = 0.0
    bn_2to1: float = 0.0
    any_1_6_2to1: float = 0.0
    steal: float = 0.0  # BN not legal, no 2:1 in 1–6 or BN
    vs_2to1: float = 0.0  # BN not legal, ≥1 2:1 in 1–6 or BN
    vs_bn: float = 0.0  # BN legal (calls)
    bn_2to1_leaf: float = 0.0  # BN is 2:1 (CO draws first vs that caller)
    seat16_2to1_bn_neither: float = 0.0  # caller-first §3.4 draw order
    co_has_bug: float = 0.0

    def add(
        self,
        *,
        bn_kind: str,
        any_16_2to1: bool,
        co_bug: bool,
    ) -> None:
        self.n += 1.0
        if co_bug:
            self.co_has_bug += 1.0
        bn_legal = bn_kind == "open_legal"
        bn_is_2 = bn_kind == "two_to_one"
        if bn_legal:
            self.bn_legal += 1.0
            self.vs_bn += 1.0
            return
        if bn_is_2:
            self.bn_2to1 += 1.0
        if any_16_2to1:
            self.any_1_6_2to1 += 1.0
        if bn_is_2 or any_16_2to1:
            self.vs_2to1 += 1.0
            if bn_is_2:
                self.bn_2to1_leaf += 1.0
            else:
                self.seat16_2to1_bn_neither += 1.0
        else:
            self.steal += 1.0

    def as_dict(self) -> dict[str, float]:
        n = self.n or 1.0
        return {
            "n": self.n,
            "p_bn_open_legal": round(self.bn_legal / n, 6),
            "p_bn_2to1": round(self.bn_2to1 / n, 6),
            "p_any_of_1_6_2to1": round(self.any_1_6_2to1 / n, 6),
            "p_steal": round(self.steal / n, 6),
            "p_vs_2to1": round(self.vs_2to1 / n, 6),
            "p_vs_bn_legal": round(self.vs_bn / n, 6),
            "p_bn_2to1_leaf": round(self.bn_2to1_leaf / n, 6),
            "p_seat16_2to1_bn_neither": round(self.seat16_2to1_bn_neither / n, 6),
            "p_co_has_bug": round(self.co_has_bug / n, 6),
        }


def estimate_behind_probs(
    co_class: str,
    two_to_one: set[frozenset[int]],
    *,
    n_deals: int,
    seed: int,
) -> dict[str, float]:
    """8-way deal MC: CO of ``co_class``, then seats 1–6 and BN from the rest."""
    rng = random.Random(seed)
    acc = BehindAccum()
    tries = 0
    while acc.n < n_deals and tries < n_deals * 40:
        tries += 1
        co_ids = sample_class_ids(co_class, rng)
        if co_ids is None:
            continue
        rem = [i for i in range(53) if i not in co_ids]
        rng.shuffle(rem)
        # Seats 1–6 then BN (7 hands × 5 cards).
        kinds: list[str] = []
        for s in range(7):
            ids = tuple(sorted(rem[s * 5 : (s + 1) * 5]))
            kinds.append(classify_seat_ids(ids, two_to_one))
        seat16 = kinds[:6]
        bn_kind = kinds[6]
        acc.add(
            bn_kind=bn_kind,
            any_16_2to1=any(k == "two_to_one" for k in seat16),
            co_bug=BUG_ID in co_ids,
        )
    out = acc.as_dict()
    out["co_class"] = co_class
    out["seed"] = seed
    out["tries"] = tries
    return out


# --- Draw-order deal loops (do not edit postdraw_nonbluff_ev.py) ----------------


def generate_co_vs_2to1_deals(
    co_class: str,
    callers: Sequence[DrawHandResult],
    *,
    n_deals: int,
    seed: int,
    drawer_is_bn: bool,
    caller_d: int = 1,
    draw_policy=LOCKED_BN_DRAW,
) -> list[NonbluffDeal]:
    """CO opener vs one 2:1 caller.

    ``drawer_is_bn=False``: seats 1–6 caller draws first (same as M2 / §3.4).
    ``drawer_is_bn=True``: CO opened, BN is the 2:1 caller → CO draws first,
    BN last. Fixed ``n`` makes the *set* of cards order-invariant; we still
    resimulate the BN-caller cell as the ticket requires.
    """
    if caller_d not in (0, 1):
        raise ValueError(f"illegal caller draw: {caller_d=}")
    rng = random.Random(seed)
    co_n = draw_policy.n_draw_for(co_class)
    deals: list[NonbluffDeal] = []
    tries = 0
    while len(deals) < n_deals and tries < n_deals * 40:
        tries += 1
        ids = sample_class_ids(co_class, rng)
        if ids is None:
            continue
        blocked = set(ids)
        caller = _sample_disjoint_caller(callers, blocked, rng)
        if caller is None:
            continue
        cards = tuple(card_from_id(i) for i in ids)
        plan = opener_draw_plan_for_action(cards, co_class, co_n)
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
            if drawer_is_bn:
                d_cards = rem[: plan.n_draw]
                c_card = rem[plan.n_draw]
            else:
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
                opener_class=co_class,
                caller_class="all_2to1",
                d=plan.n_draw,
                caller_d=caller_d,
                opener_start_pair=_pair_rank_from_class(co_class),
                opener_final=opener_final,
                drawer_final=drawer_final,
                opener_final_pair=_one_pair_rank(opener_final),
                drawer_final_pair=_face_pair_rank(drawer_final),
                drawer_straight_plus=drawer_final.category >= HandCategory.STRAIGHT,
                opener_two_pair_plus=opener_final.category >= HandCategory.TWO_PAIR,
            )
        )
    return deals


def bn_value_continue_as_m2_drawer(bn_final: HandValue) -> tuple[bool, int | None]:
    """Map a made-hand BN onto the honest 2:1 M2 caller line.

    Straight+ still raises. Two pair+ is not a face pair, so a raw M2 drawer
    would *fold* it to a CO value-bet. Treat two pair+ as an AA-strength
    continue (call a bet, value-stab when checked). One-pair BN uses the
    real face-pair rank (AA stab / JJ–KK check).
    """
    if bn_final.category >= HandCategory.STRAIGHT:
        return True, None
    if bn_final.category >= HandCategory.TWO_PAIR:
        return False, 14
    return False, _face_pair_rank(bn_final)


def generate_co_vs_bn_legal_deals(
    co_class: str,
    *,
    n_deals: int,
    seed: int,
    draw_policy=LOCKED_BN_DRAW,
) -> list[NonbluffDeal]:
    """HU: CO class × BN open-legal range. CO draws first, then BN.

    Post-draw: left-of-dealer first live is CO, so opener-first betting
    matches. Locked draws (pairs d=3, two pair d=1, trips d=2, quads d=1).
    """
    rng = random.Random(seed)
    co_n = draw_policy.n_draw_for(co_class)
    deals: list[NonbluffDeal] = []
    tries = 0
    by_bn: Counter[str] = Counter()
    while len(deals) < n_deals and tries < n_deals * 40:
        tries += 1
        co_ids = sample_class_ids(co_class, rng)
        if co_ids is None:
            continue
        sampled = sample_open_legal_ids(rng, blocked=set(co_ids))
        if sampled is None:
            continue
        bn_ids, bn_cls = sampled
        left = [i for i in range(53) if i not in co_ids and i not in bn_ids]
        rng.shuffle(left)
        co_cards = tuple(card_from_id(i) for i in co_ids)
        bn_cards = tuple(card_from_id(i) for i in bn_ids)
        bn_n = draw_policy.n_draw_for(bn_cls)
        co_plan = opener_draw_plan_for_action(co_cards, co_class, co_n)
        bn_plan = opener_draw_plan_for_action(bn_cards, bn_cls, bn_n)
        need = co_plan.n_draw + bn_plan.n_draw
        if len(left) < need:
            continue
        # CO draws first (left of dealer), BN last.
        co_draw = left[: co_plan.n_draw]
        bn_draw = left[co_plan.n_draw : need]
        co_final = evaluate_hand(
            (*co_plan.keep, *(card_from_id(i) for i in co_draw))
        )
        bn_final = evaluate_hand(
            (*bn_plan.keep, *(card_from_id(i) for i in bn_draw))
        )
        sp, face = bn_value_continue_as_m2_drawer(bn_final)
        deals.append(
            NonbluffDeal(
                opener_class=co_class,
                caller_class=bn_cls,
                d=co_plan.n_draw,
                caller_d=bn_plan.n_draw,
                opener_start_pair=_pair_rank_from_class(co_class),
                opener_final=co_final,
                drawer_final=bn_final,
                opener_final_pair=_one_pair_rank(co_final),
                drawer_final_pair=face,
                drawer_straight_plus=sp,
                opener_two_pair_plus=co_final.category >= HandCategory.TWO_PAIR,
            )
        )
        by_bn[bn_cls] += 1
    return deals


def checkdown_ev_co(deal: NonbluffDeal, pot: float = PREDRAW_POT) -> float:
    """Showdown-only CO chips from a ``pot`` already in the middle (invested 0)."""
    if deal.opener_final > deal.drawer_final:
        return pot
    if deal.opener_final < deal.drawer_final:
        return 0.0
    return pot / 2.0


def evaluate_co_deals(deals: Sequence[NonbluffDeal]) -> dict[str, float]:
    n = 0.0
    ev = 0.0
    ev_cd = 0.0
    wins = 0.0
    ties = 0.0
    for deal in deals:
        e, _caller, _flags = play_honest_deal(deal, HONEST_POLICY)
        n += 1.0
        ev += e
        ev_cd += checkdown_ev_co(deal)
        if deal.opener_final > deal.drawer_final:
            wins += 1.0
        elif deal.opener_final == deal.drawer_final:
            ties += 1.0
    n = n or 1.0
    return {
        "n": n,
        "ev_co_street": round(ev / n, 5),
        "ev_co_checkdown": round(ev_cd / n, 5),
        "p_co_wins_final": round(wins / n, 5),
        "p_tie_final": round(ties / n, 5),
        "p_bn_wins_final": round((n - wins - ties) / n, 5),
    }


def locked_section_34_ev(opener_class: str) -> float | None:
    """§3.4 locked-draw EV_bn vs all 2:1 (caller d=1) — bound when order matches."""
    d = LOCKED_BN_DRAW.n_draw_for(opener_class)
    try:
        data = load_nonbluff_fixture()
    except FileNotFoundError:
        return None
    for row in data.get("bn_grid", []):
        if (
            row.get("opener_class") == opener_class
            and row.get("bn_d") == d
            and row.get("caller_class") == "all_2to1"
            and row.get("caller_d") == 1
        ):
            return float(row["ev_bn"])
    return None


# --- Mix: open vs pass ----------------------------------------------------------


def mix_open_ev(
    *,
    p_steal: float,
    p_vs_2to1: float,
    p_vs_bn: float,
    ev_street_2to1: float,
    ev_street_bn: float,
) -> float:
    """Pass = 0; steal = +$2; called street net = EV_street − $2.

    Equivalent to ``2 + p_2to1*(e2−4) + p_bn*(eb−4)``.
    """
    return (
        p_steal * STEAL_EV
        + p_vs_2to1 * (ev_street_2to1 - 2.0)
        + p_vs_bn * (ev_street_bn - 2.0)
    )


def mix_pass_call_ev(*, p_vs_bn: float, ev_street_bn: float) -> float:
    """Pass a legal hand, then call BN's open (same HU street as open-vs-legal).

    BN not legal → dead hand 0. JJ v1 folds instead (pass = 0).
    """
    return p_vs_bn * (ev_street_bn - 2.0)


def mix_pass_raise_checkdown_ev(
    *, p_vs_bn: float, p_win: float, p_tie: float
) -> float:
    """Bound: pass, raise BN's open, check down a $10 pot (CO invested $4)."""
    street = 10.0 * p_win + 5.0 * p_tie
    return p_vs_bn * (street - 4.0)


def blend_2to1_street(
    probs: dict[str, float],
    *,
    ev_caller_first: float,
    ev_co_first: float,
) -> float:
    """Weight §3.4 (1–6 caller) vs resim (BN 2:1 caller) inside the vs-2:1 leaf."""
    p = probs["p_vs_2to1"]
    if p <= 0.0:
        return ev_caller_first
    w_bn = probs["p_bn_2to1_leaf"] / p
    w_16 = probs["p_seat16_2to1_bn_neither"] / p
    return w_bn * ev_co_first + w_16 * ev_caller_first


# --- Grid / payload -------------------------------------------------------------


@dataclass(slots=True)
class ClassResult:
    co_class: str
    probs: dict[str, float] = field(default_factory=dict)
    vs_2to1_caller_first: dict[str, float] = field(default_factory=dict)
    vs_2to1_co_first: dict[str, float] = field(default_factory=dict)
    vs_bn_legal: dict[str, float] = field(default_factory=dict)
    section_34_ev: float | None = None
    ev_open: float = 0.0
    ev_pass_fold: float = 0.0
    ev_pass_call: float = 0.0
    ev_pass_raise_cd: float = 0.0
    open_minus_pass_fold: float = 0.0
    open_minus_best_pass: float = 0.0
    should_open: bool = True
    should_sandbag: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "co_class": self.co_class,
            "sandbag_set_v1_on_co": is_co_sandbag_class(self.co_class),
            "probs": self.probs,
            "vs_2to1_caller_first": self.vs_2to1_caller_first,
            "vs_2to1_co_first": self.vs_2to1_co_first,
            "vs_bn_legal": self.vs_bn_legal,
            "section_34_locked_ev": self.section_34_ev,
            "ev_open": round(self.ev_open, 5),
            "ev_pass_fold": round(self.ev_pass_fold, 5),
            "ev_pass_call": round(self.ev_pass_call, 5),
            "ev_pass_raise_checkdown": round(self.ev_pass_raise_cd, 5),
            "open_minus_pass_fold": round(self.open_minus_pass_fold, 5),
            "open_minus_best_pass": round(self.open_minus_best_pass, 5),
            "should_open": self.should_open,
            "should_sandbag": self.should_sandbag,
        }


def evaluate_co_class(
    co_class: str,
    callers: Sequence[DrawHandResult],
    two_to_one: set[frozenset[int]],
    *,
    n_prob: int,
    n_hu: int,
    n_2to1: int,
    seed: int,
    progress: bool = False,
) -> ClassResult:
    if progress:
        print(f"  {co_class}: behind probs (n={n_prob})…")
    probs = estimate_behind_probs(
        co_class, two_to_one, n_deals=n_prob, seed=_cell_seed(seed, "prob", co_class)
    )
    sec34 = locked_section_34_ev(co_class)

    if progress:
        print(f"  {co_class}: vs 2:1 caller-first / CO-first (n={n_2to1})…")
    d_16 = generate_co_vs_2to1_deals(
        co_class,
        callers,
        n_deals=n_2to1,
        seed=_cell_seed(seed, "2to1", co_class, False),
        drawer_is_bn=False,
    )
    d_bn = generate_co_vs_2to1_deals(
        co_class,
        callers,
        n_deals=n_2to1,
        seed=_cell_seed(seed, "2to1", co_class, True),
        drawer_is_bn=True,
    )
    vs16 = evaluate_co_deals(d_16) if d_16 else {"n": 0.0, "ev_co_street": sec34 or 3.0}
    vsbn_d = evaluate_co_deals(d_bn) if d_bn else {"n": 0.0, "ev_co_street": sec34 or 3.0}

    if progress:
        print(f"  {co_class}: vs BN legal HU (n={n_hu})…")
    hu = generate_co_vs_bn_legal_deals(
        co_class, n_deals=n_hu, seed=_cell_seed(seed, "hu", co_class)
    )
    vs_bn = evaluate_co_deals(hu) if hu else {
        "n": 0.0,
        "ev_co_street": 3.0,
        "p_co_wins_final": 0.5,
        "p_tie_final": 0.0,
    }

    ev_2 = blend_2to1_street(
        probs,
        ev_caller_first=vs16["ev_co_street"],
        ev_co_first=vsbn_d["ev_co_street"],
    )
    # Prefer the live resim; §3.4 is the bound when caller-first matches.
    if sec34 is not None and abs(vs16["ev_co_street"] - sec34) > 0.75:
        # Resim noise or thin n; fall back toward the locked bound.
        ev_2 = blend_2to1_street(
            probs,
            ev_caller_first=0.5 * vs16["ev_co_street"] + 0.5 * sec34,
            ev_co_first=vsbn_d["ev_co_street"],
        )

    ev_open = mix_open_ev(
        p_steal=probs["p_steal"],
        p_vs_2to1=probs["p_vs_2to1"],
        p_vs_bn=probs["p_vs_bn_legal"],
        ev_street_2to1=ev_2,
        ev_street_bn=vs_bn["ev_co_street"],
    )
    ev_pass_fold = PASS_EV
    ev_pass_call = mix_pass_call_ev(
        p_vs_bn=probs["p_vs_bn_legal"], ev_street_bn=vs_bn["ev_co_street"]
    )
    ev_pass_raise = mix_pass_raise_checkdown_ev(
        p_vs_bn=probs["p_vs_bn_legal"],
        p_win=vs_bn.get("p_co_wins_final", 0.0),
        p_tie=vs_bn.get("p_tie_final", 0.0),
    )
    # JJ v1: fold to a BN open → pass is 0. Sandbag classes continue.
    if is_co_sandbag_class(co_class):
        best_pass = max(ev_pass_fold, ev_pass_call, ev_pass_raise)
    else:
        best_pass = ev_pass_fold
    row = ClassResult(
        co_class=co_class,
        probs=probs,
        vs_2to1_caller_first=vs16,
        vs_2to1_co_first=vsbn_d,
        vs_bn_legal=vs_bn,
        section_34_ev=sec34,
        ev_open=ev_open,
        ev_pass_fold=ev_pass_fold,
        ev_pass_call=ev_pass_call,
        ev_pass_raise_cd=ev_pass_raise,
        open_minus_pass_fold=ev_open - ev_pass_fold,
        open_minus_best_pass=ev_open - best_pass,
        should_open=ev_open > best_pass,
        should_sandbag=is_co_sandbag_class(co_class) and ev_open < best_pass,
    )
    return row


def derive_answers(rows: list[ClassResult]) -> dict[str, Any]:
    by = {r.co_class: r for r in rows}
    jj = by.get("pair_J")
    aa = by.get("pair_A")
    tp = by.get("two_pair")
    legal_open = [r.co_class for r in rows if r.should_open]
    minus_ev = [r.co_class for r in rows if not r.should_open]
    sandbag = [r.co_class for r in rows if r.should_sandbag]
    return {
        "q1_open_every_legal": bool(jj) and jj.should_open and not minus_ev,
        "q1_jj_ev_open": None if jj is None else round(jj.ev_open, 5),
        "q1_jj_ev_pass": 0.0,
        "q1_jj_open_minus_pass": None if jj is None else round(jj.open_minus_pass_fold, 5),
        "q1_minus_ev_classes": minus_ev,
        "q1_open_classes": legal_open,
        "q2_co_should_sandbag": bool(sandbag),
        "q2_sandbag_classes": sandbag,
        "q2_pair_A_ev_open": None if aa is None else round(aa.ev_open, 5),
        "q2_pair_A_best_pass": None
        if aa is None
        else round(max(aa.ev_pass_fold, aa.ev_pass_call, aa.ev_pass_raise_cd), 5),
        "q2_two_pair_ev_open": None if tp is None else round(tp.ev_open, 5),
        "q2_two_pair_best_pass": None
        if tp is None
        else round(max(tp.ev_pass_fold, tp.ev_pass_call, tp.ev_pass_raise_cd), 5),
        "note": (
            "JJ pass = 0 (v1 fold to BN open). Sandbag pass uses the best of "
            "fold / call / raise-checkdown vs BN legal; steal is given up."
        ),
    }


def run_cutoff_open(
    *,
    n_prob: int = DEFAULT_N_PROB,
    n_hu: int = DEFAULT_N_HU,
    n_2to1: int = DEFAULT_N_2TO1,
    seed: int = DEFAULT_SEED,
    classes: Sequence[str] | None = None,
    progress: bool = True,
    callers: Sequence[DrawHandResult] | None = None,
) -> dict[str, Any]:
    use = list(classes) if classes else list(FOCUS_CLASSES)
    if progress:
        print("Loading 2:1 callers…")
    callers = callers or load_call_2to1_hands(progress=progress)
    two_to_one = two_to_one_id_set(callers)
    rows: list[ClassResult] = []
    for cls in use:
        rows.append(
            evaluate_co_class(
                cls,
                callers,
                two_to_one,
                n_prob=n_prob,
                n_hu=n_hu,
                n_2to1=n_2to1,
                seed=seed,
                progress=progress,
            )
        )
    answers = derive_answers(rows)
    planning = {
        "co_has_bug": planning_behind_co(co_has_bug=True),
        "co_no_bug": planning_behind_co(co_has_bug=False),
    }
    return {
        "meta": {
            "seed": seed,
            "n_prob": n_prob,
            "n_hu": n_hu,
            "n_2to1": n_2to1,
            "frame": "cutoff_open_no_sandbagging",
            "matchup": (
                "Seats 1–6 unable (0% sandbag). CO legal. BN opens every legal "
                "if CO passes; calls every legal if CO opens."
            ),
            "accounting": {
                "pass": PASS_EV,
                "steal": STEAL_EV,
                "fold_to_raise": FOLD_TO_RAISE_EV,
                "called_net": "EV_street - $2 (pot $6 into draw)",
            },
            "draw_order": {
                "co_opens_bn_calls": "CO first, then BN (BN last)",
                "co_opens_seat16_2to1": "2:1 caller first (same as M2 / §3.4)",
                "postdraw_betting": (
                    "HU CO vs BN: left-of-dealer first live is CO; "
                    "opener-first matches"
                ),
                "card_sets": (
                    "Fixed draw counts ⇒ disjoint card-sets are order-invariant; "
                    "BN-caller cell is still resimulated"
                ),
            },
            "locked_draws": {
                "name": LOCKED_BN_DRAW.name,
                "pair_d": LOCKED_BN_DRAW.pair_d,
                "two_pair_d": LOCKED_BN_DRAW.two_pair_d,
                "trips_d": LOCKED_BN_DRAW.trips_d,
                "quads_d": LOCKED_BN_DRAW.quads_d,
            },
            "honest_policy": HONEST_POLICY.key,
            "sandbag_set_v1": {
                "two_pair_plus": "all seats 1–7",
                "pair_A": "HJ (6) and CO (7) only",
                "this_frame": "0% sandbag in seats 1–6; CO sandbag is Q2",
            },
            "doc": "docs/research/cutoff_open_no_sandbagging.md",
            "regenerate": (
                "analyze-cutoff-open --n-prob 20000 --n-hu 4000 --n-2to1 2000 "
                "--write-fixture"
            ),
        },
        "planning": planning,
        "by_class": [r.as_dict() for r in rows],
        "answers": answers,
    }


def default_fixture_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "validation"
        / "cutoff_open_summary.json"
    )


def write_summary_fixture(
    payload: dict[str, Any], path: Path | None = None
) -> Path:
    path = path or default_fixture_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    slim = {
        "meta": payload["meta"],
        "planning": payload["planning"],
        "by_class": payload["by_class"],
        "answers": payload["answers"],
    }
    path.write_text(json.dumps(slim, indent=2) + "\n", encoding="utf-8")
    return path


def load_summary_fixture(path: Path | None = None) -> dict[str, Any]:
    path = path or default_fixture_path()
    return json.loads(path.read_text(encoding="utf-8"))


def write_markdown_summary(payload: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    a = payload["answers"]
    meta = payload["meta"]
    lines = [
        "# Cutoff open, no sandbagging (seats 1–6)",
        "",
        f"Seed `{meta['seed']}`, n_prob={meta['n_prob']}, n_hu={meta['n_hu']}, "
        f"n_2to1={meta['n_2to1']}.",
        "",
        "## Product answers",
        "",
        f"1. Open every legal? **{a['q1_open_every_legal']}**. "
        f"JJ EV(open)={a['q1_jj_ev_open']} vs pass 0 "
        f"(Δ={a['q1_jj_open_minus_pass']}). "
        f"−EV classes: {a['q1_minus_ev_classes'] or 'none'}.",
        f"2. CO sandbag two pair+ / AA? **{a['q2_co_should_sandbag']}**. "
        f"AA open={a['q2_pair_A_ev_open']} vs best pass={a['q2_pair_A_best_pass']}; "
        f"two pair open={a['q2_two_pair_ev_open']} vs best pass="
        f"{a['q2_two_pair_best_pass']}.",
        "",
        "## By class",
        "",
        "| CO class | P(steal) | P(vs 2:1) | P(BN legal) | EV open | "
        "EV pass-fold | EV pass-call | EV pass-raise-cd | Open? | Sandbag? |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for r in payload["by_class"]:
        p = r["probs"]
        lines.append(
            f"| {r['co_class']} | {p['p_steal']:.4f} | {p['p_vs_2to1']:.4f} | "
            f"{p['p_vs_bn_legal']:.4f} | {r['ev_open']:+.4f} | "
            f"{r['ev_pass_fold']:+.4f} | {r['ev_pass_call']:+.4f} | "
            f"{r['ev_pass_raise_checkdown']:+.4f} | {r['should_open']} | "
            f"{r['should_sandbag']} |"
        )
    lines += ["", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(
        description="CO open/pass with BN behind (0% sandbag seats 1–6)"
    )
    p.add_argument("--n-prob", type=int, default=DEFAULT_N_PROB)
    p.add_argument("--n-hu", type=int, default=DEFAULT_N_HU)
    p.add_argument("--n-2to1", type=int, default=DEFAULT_N_2TO1)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--quick", action="store_true")
    p.add_argument(
        "--classes",
        type=str,
        default=None,
        help="Comma-separated CO classes (default: JJ,QQ,KK,AA,two_pair)",
    )
    p.add_argument("-o", "--output", type=Path, default=None)
    p.add_argument("--write-fixture", action="store_true")
    args = p.parse_args()
    n_prob, n_hu, n_2to1 = args.n_prob, args.n_hu, args.n_2to1
    if args.quick:
        n_prob, n_hu, n_2to1 = 400, 250, 150
    classes = (
        [c.strip() for c in args.classes.split(",") if c.strip()]
        if args.classes
        else None
    )
    payload = run_cutoff_open(
        n_prob=n_prob,
        n_hu=n_hu,
        n_2to1=n_2to1,
        seed=args.seed,
        classes=classes,
        progress=True,
    )
    out = args.output or Path("outputs/validation/cutoff_open.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out}")
    md = out.with_suffix(".md")
    write_markdown_summary(payload, md)
    print(f"Wrote {md}")
    if args.write_fixture:
        fix = write_summary_fixture(payload)
        print(f"Wrote fixture {fix}")
    a = payload["answers"]
    print()
    print("Answers:")
    print(
        f"  Q1 open every legal={a['q1_open_every_legal']}  "
        f"JJ EV(open)={a['q1_jj_ev_open']} vs pass 0"
    )
    print(
        f"  Q2 sandbag={a['q2_co_should_sandbag']}  "
        f"AA open={a['q2_pair_A_ev_open']} pass={a['q2_pair_A_best_pass']}  "
        f"TP open={a['q2_two_pair_ev_open']} pass={a['q2_two_pair_best_pass']}"
    )
    for r in payload["by_class"]:
        print(
            f"  {r['co_class']:<12} open={r['ev_open']:+.4f}  "
            f"steal={r['probs']['p_steal']:.3f}  "
            f"p_bn={r['probs']['p_vs_bn_legal']:.3f}  "
            f"HU={r['vs_bn_legal'].get('ev_co_street')}"
        )


if __name__ == "__main__":
    main()
