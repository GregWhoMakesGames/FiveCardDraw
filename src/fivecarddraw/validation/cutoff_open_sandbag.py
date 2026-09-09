"""Cutoff open vs seats 1–6 sandbag rate (fold-to-raise bound).

Frame: ``cutoff_open_sandbag_v1``. Direct analog of BN ``seats_1_6_only``:

    EV(open) = (1 - p_raise) * L + p_raise * (-2)

Actor is **CO** after seats 1–6 passed. BN has not acted. Sandbag-set v1 is
the same as ``seats_1_6_only`` (1–5 two pair+; HJ two pair+ and pair_A;
CO never sandbags). Raise = ≥1 of 1–6 has the sandbag-set; they always
raise; CO folds JJ/QQ/KK → −$2. BN is **not** in p_raise — BN's calls and
opens vs a CO open already sit inside the 0% CO leaf L.

L is the pinned ``cutoff_open_no_sandbagging`` EV(open) for that class.
Do **not** rebuild draw / post-draw Nash. There is no live CO vs BN vs
sandbagger street in this mix.
"""

from __future__ import annotations

import json
import math
import os
import random
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, Sequence

from fivecarddraw.cards import BUG_ID, card_from_id, parse_hand
from fivecarddraw.validation.cascade_odds import TOTAL_HANDS
from fivecarddraw.validation.cutoff_open import (
    blend_2to1_street,
    classify_seat_ids,
    load_summary_fixture as load_cutoff_open,
    mix_open_ev,
    two_to_one_id_set,
)
from fivecarddraw.validation.sandbag_v1 import (
    DEFAULT_MC_N,
    DEFAULT_MC_SEED,
    DEFAULT_REMOVAL_BN_N,
    DEFAULT_REMOVAL_HANDS_PER_BN,
    FOLD_JJ_TO_RAISE_EV,
    FOLD_TO_RAISE_CLASSES,
    PASS_EV,
    SANDBAG_WORLD_CO_VS_SEATS_1_6,
    SANDBAG_WORLD_SEATS_1_6_ONLY,
    SEAT_CO,
    SEAT_HJ,
    SEAT_UTG,
    STEAL_EV,
    TWO_PAIR_PLUS_CLASSES,
    aces_sandbag_seats,
    ev_open_fold_to_raise,
    independent_p_raise_bn_class_blocked,
    independent_p_raise_unconditional,
    is_sandbag_set,
    is_voluntary_opener,
    not_open_legal_count,
    sandbag_set_combo_count,
    sandbag_seats,
    voluntary_combo_count,
)
from fivecarddraw.validation.showdown_matrix import (
    TRIPS_CLASSES,
    classify_opener,
    load_call_2to1_hands,
    load_showdown_matrix,
)

WORLD = SANDBAG_WORLD_CO_VS_SEATS_1_6
FOCUS_CLASSES = FOLD_TO_RAISE_CLASSES  # pair_J, pair_Q, pair_K
SEATS_1_6 = tuple(range(1, 7))
# Writeup planning masses (combo / C(53,5)); tests pin the live inventory.
P_JUNK_WRITEUP = 0.7760
P_SANDBAG_EARLY_WRITEUP = 0.0821
P_SANDBAG_HJ_WRITEUP = 0.1302
# rank 11/12/13/14 → card_id 36..51
PHYSICAL_JACK_IDS = frozenset(range(36, 40))
PHYSICAL_QUEEN_IDS = frozenset(range(40, 44))
PHYSICAL_KING_IDS = frozenset(range(44, 48))
PHYSICAL_ACE_IDS = frozenset(range(48, 52))
DEFAULT_BLOCKER_MC_N = 10_000
DEFAULT_BLOCKER_LEAF_N = 8_000
BLOCKER_CLASSES = ("pair_J", "pair_Q", "pair_K")


def _hand_ids(text: str) -> tuple[int, ...]:
    return tuple(sorted(c.card_id for c in parse_hand(text)))


# Matched kickers: two of the pair rank + 9s 7h, swapping the fifth card
# (4c / Bu / As). Bug is an ace kicker, not a duplicate pair rank.
PAIR_J_NO_BUG_IDS = _hand_ids("Jh Jd 9s 7h 4c")
PAIR_J_BUG_IDS = _hand_ids("Jh Jd Bu 9s 7h")
PAIR_J_ACE_IDS = _hand_ids("Jh Jd As 7h 4c")
PAIR_Q_NO_BUG_IDS = _hand_ids("Qh Qd 9s 7h 4c")
PAIR_Q_BUG_IDS = _hand_ids("Qh Qd Bu 9s 7h")
PAIR_Q_ACE_IDS = _hand_ids("Qh Qd As 7h 4c")
PAIR_K_NO_BUG_IDS = _hand_ids("Kh Kd 9s 7h 4c")
PAIR_K_BUG_IDS = _hand_ids("Kh Kd Bu 9s 7h")
PAIR_K_ACE_IDS = _hand_ids("Kh Kd As 7h 4c")

MATCHED_KICKER_HANDS: dict[str, dict[str, tuple[tuple[int, ...], str]]] = {
    "pair_J": {
        "no_bug": (PAIR_J_NO_BUG_IDS, "pair_J_two_jacks"),
        "bug": (PAIR_J_BUG_IDS, "pair_J_two_jacks_plus_bug"),
        "ace": (PAIR_J_ACE_IDS, "pair_J_ace_kicker"),
    },
    "pair_Q": {
        "no_bug": (PAIR_Q_NO_BUG_IDS, "pair_Q_two_queens"),
        "bug": (PAIR_Q_BUG_IDS, "pair_Q_two_queens_plus_bug"),
        "ace": (PAIR_Q_ACE_IDS, "pair_Q_ace_kicker"),
    },
    "pair_K": {
        "no_bug": (PAIR_K_NO_BUG_IDS, "pair_K_two_kings"),
        "bug": (PAIR_K_BUG_IDS, "pair_K_two_kings_plus_bug"),
        "ace": (PAIR_K_ACE_IDS, "pair_K_ace_kicker"),
    },
}


def _ids_to_cls(ids: Sequence[int]) -> str | None:
    return classify_opener(tuple(card_from_id(i) for i in ids))


_TWO_TO_ONE_IDS: set[frozenset[int]] | None = None


def _two_to_one_id_cache() -> set[frozenset[int]]:
    global _TWO_TO_ONE_IDS
    if _TWO_TO_ONE_IDS is None:
        _TWO_TO_ONE_IDS = two_to_one_id_set(load_call_2to1_hands())
    return _TWO_TO_ONE_IDS


def load_co_zero_sandbag_leaf(co_class: str, *, fixture: dict[str, Any] | None = None) -> float:
    """0% sandbag CO open EV for ``co_class`` (cutoff_open fixture). Do not rebuild."""
    data = fixture if fixture is not None else load_cutoff_open()
    for row in data["by_class"]:
        if row["co_class"] == co_class:
            return float(row["ev_open"])
    raise KeyError(f"no cutoff_open leaf for {co_class!r}")


def break_even_p_raise(leaf: float) -> float:
    """p* such that (1-p)*L + p*(-2) = 0 ⇒ p* = L/(L+2)."""
    denom = leaf - FOLD_JJ_TO_RAISE_EV
    if denom == 0.0:
        return 1.0
    return leaf / denom


def inventory_masses(*, world: str = WORLD) -> dict[str, float]:
    total = float(TOTAL_HANDS)
    p_j = not_open_legal_count() / total
    p_s_early = sandbag_set_combo_count(SEAT_UTG, world) / total
    p_s_hj = sandbag_set_combo_count(SEAT_HJ, world) / total
    return {
        "total_hands": TOTAL_HANDS,
        "p_j": p_j,
        "p_s_early": p_s_early,
        "p_s_hj": p_s_hj,
        "p_j_writeup": P_JUNK_WRITEUP,
        "p_s_early_writeup": P_SANDBAG_EARLY_WRITEUP,
        "p_s_hj_writeup": P_SANDBAG_HJ_WRITEUP,
    }


def independent_p_raise_at_rate(
    r: float,
    *,
    world: str = WORLD,
    p_j: float | None = None,
    p_s_early: float | None = None,
    p_s_hj: float | None = None,
) -> float:
    """Independent-seat P(raise | 1–6 passed) at sandbag rate r.

    p(r) = 1 - [p_j / (p_j + r p_s^{1-5})]^5 * [p_j / (p_j + r p_s^{HJ})]
    """
    if r <= 0.0:
        return 0.0
    masses = inventory_masses(world=world)
    pj = masses["p_j"] if p_j is None else p_j
    ps_e = masses["p_s_early"] if p_s_early is None else p_s_early
    ps_h = masses["p_s_hj"] if p_s_hj is None else p_s_hj
    p_n_early = pj / (pj + r * ps_e)
    p_n_hj = pj / (pj + r * ps_h)
    return 1.0 - (p_n_early**5) * p_n_hj


def invert_independent_rate(
    p_star: float,
    *,
    world: str = WORLD,
    hi: float = 16.0,
    tol: float = 1e-14,
    max_iter: int = 80,
) -> dict[str, float | bool]:
    """Sandbag rate r with independent p(r) = p_star.

    r > 1 means even 100% sandbag still has p_raise < p_star (open stays +EV).
    """
    if p_star <= 0.0:
        return {"r": 0.0, "p_at_r": 0.0, "bracketed": True, "above_100pct": False}
    p_hi = independent_p_raise_at_rate(hi, world=world)
    if p_star >= p_hi:
        return {
            "r": hi,
            "p_at_r": p_hi,
            "bracketed": False,
            "above_100pct": True,
        }
    lo, plo = 0.0, 0.0
    h, ph = hi, p_hi
    for _ in range(max_iter):
        mid = 0.5 * (lo + h)
        pm = independent_p_raise_at_rate(mid, world=world)
        if abs(pm - p_star) <= tol or abs(h - lo) <= tol:
            return {
                "r": mid,
                "p_at_r": pm,
                "bracketed": True,
                "above_100pct": mid > 1.0,
            }
        if pm < p_star:
            lo, plo = mid, pm
        else:
            h, ph = mid, pm
    _ = plo, ph
    mid = 0.5 * (lo + h)
    return {
        "r": mid,
        "p_at_r": independent_p_raise_at_rate(mid, world=world),
        "bracketed": True,
        "above_100pct": mid > 1.0,
    }


def calibrated_p_raise_at_rate(
    r: float,
    *,
    kappa: float,
    world: str = WORLD,
) -> float:
    """Scale independent p(r) so p(1) matches deal-MC p(1)."""
    return kappa * independent_p_raise_at_rate(r, world=world)


def invert_calibrated_rate(
    p_star: float,
    *,
    p_mc_1: float,
    p_ind_1: float,
    world: str = WORLD,
) -> dict[str, float | bool]:
    """Invert kappa * p_ind(r) = p_star with kappa = p_mc(1) / p_ind(1)."""
    if p_ind_1 <= 0.0:
        raise ValueError("independent p(1) must be positive")
    kappa = p_mc_1 / p_ind_1
    linear = (p_star / p_mc_1) if p_mc_1 > 0.0 else float("inf")
    if p_star <= 0.0:
        return {
            "r": 0.0,
            "kappa": kappa,
            "linear_r": 0.0,
            "above_100pct": False,
            "p_at_r": 0.0,
        }
    if p_mc_1 <= 0.0:
        return {
            "r": float("inf"),
            "kappa": kappa,
            "linear_r": linear,
            "above_100pct": True,
            "p_at_r": 0.0,
        }
    target_ind = p_star / kappa
    inv = invert_independent_rate(target_ind, world=world)
    r = float(inv["r"])
    return {
        "r": r,
        "kappa": kappa,
        "linear_r": linear,
        "above_100pct": bool(r > 1.0 or p_star >= p_mc_1),
        "p_at_r": calibrated_p_raise_at_rate(r, kappa=kappa, world=world),
        "independent_target": target_ind,
        "independent_r": float(inv["r"]),
    }


@dataclass(frozen=True, slots=True)
class CoDealMcResult:
    n: int
    seed: int
    n_co_class: int
    n_conditioned: int
    n_raise: int
    p_raise: float
    p_co_has_bug: float
    n_tried: int
    sandbag_seats_hist: dict[str, int]
    se_p_raise: float
    co_class: str
    world: str = WORLD
    sandbag_rate: float = 1.0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CoDealMcResult":
        return cls(
            n=int(d["n"]),
            seed=int(d["seed"]),
            n_co_class=int(d["n_co_class"]),
            n_conditioned=int(d["n_conditioned"]),
            n_raise=int(d["n_raise"]),
            p_raise=float(d["p_raise"]),
            p_co_has_bug=float(d["p_co_has_bug"]),
            n_tried=int(d["n_tried"]),
            sandbag_seats_hist={str(k): int(v) for k, v in d["sandbag_seats_hist"].items()},
            se_p_raise=float(d["se_p_raise"]),
            co_class=str(d["co_class"]),
            world=str(d.get("world", WORLD)),
            sandbag_rate=float(d.get("sandbag_rate", 1.0)),
        )


def seat_passed_then_raises(
    cls: str | None,
    seat: int,
    world: str,
    rng: random.Random,
    sandbag_rate: float,
) -> tuple[bool, bool]:
    """Whether this seat spoils the folded-to-CO deal, and whether it raises.

    Sandbag-set holders pass-then-raise with probability ``sandbag_rate``;
    otherwise they open (deal rejected). ``sandbag_rate >= 1`` takes the r=1
    path with **no extra RNG** so locked 40k / 10k pins stay bit-identical.
    """
    if is_sandbag_set(cls, seat, world):
        if sandbag_rate < 1.0 and rng.random() >= sandbag_rate:
            return True, False
        return False, True
    if is_voluntary_opener(cls, seat, world):
        return True, False
    return False, False


def deal_mc_p_raise_given_passed_co(
    *,
    n: int = DEFAULT_MC_N,
    seed: int = DEFAULT_MC_SEED,
    co_class: str = "pair_J",
    world: str = WORLD,
    sandbag_rate: float = 1.0,
) -> CoDealMcResult:
    """P(≥1 of 1–6 sandbag-set | 1–6 passed, CO holds ``co_class``).

    BN is dealt and **not** filtered (unlike folded-to-BN worlds). CO is the
    hero, so CO is not a sandbag raiser in this world. Interior ``sandbag_rate``
    < 1 lets sandbag-set holders open (reject) with probability 1−r.
    """
    rng = random.Random(seed)
    deck = list(range(53))
    n_tried = 0
    n_co_class = 0
    n_cond = 0
    n_raise = 0
    n_bug = 0
    hist: dict[int, int] = {k: 0 for k in range(7)}
    while n_cond < n:
        rng.shuffle(deck)
        n_tried += 1
        co_ids = deck[5 * (SEAT_CO - 1) : 5 * SEAT_CO]
        if _ids_to_cls(co_ids) != co_class:
            continue
        n_co_class += 1
        n_sandbag = 0
        rejected = False
        for seat in SEATS_1_6:
            start = 5 * (seat - 1)
            cls = _ids_to_cls(deck[start : start + 5])
            reject, raises = seat_passed_then_raises(
                cls, seat, world, rng, sandbag_rate
            )
            if reject:
                rejected = True
                break
            if raises:
                n_sandbag += 1
        if rejected:
            continue
        n_cond += 1
        if 52 in co_ids:
            n_bug += 1
        hist[n_sandbag] = hist.get(n_sandbag, 0) + 1
        if n_sandbag:
            n_raise += 1
    p = n_raise / n_cond if n_cond else 0.0
    se = math.sqrt(p * (1.0 - p) / n_cond) if n_cond else 0.0
    return CoDealMcResult(
        n=n,
        seed=seed,
        n_co_class=n_co_class,
        n_conditioned=n_cond,
        n_raise=n_raise,
        p_raise=p,
        p_co_has_bug=n_bug / n_cond if n_cond else 0.0,
        n_tried=n_tried,
        sandbag_seats_hist={str(k): hist[k] for k in range(7)},
        se_p_raise=se,
        co_class=co_class,
        world=world,
        sandbag_rate=sandbag_rate,
    )


def mix_co_open(p_raise: float, leaf: float) -> dict[str, Any]:
    ev = ev_open_fold_to_raise(p_raise, ev_no_raise=leaf)
    p_star = break_even_p_raise(leaf)
    return {
        "ev_no_raise_leaf": leaf,
        "p_raise": p_raise,
        "piece_no_raise": (1.0 - p_raise) * leaf,
        "piece_raise": p_raise * FOLD_JJ_TO_RAISE_EV,
        "ev_open": ev,
        "ev_pass": PASS_EV,
        "open_minus_pass": ev - PASS_EV,
        "opening_is_positive_ev": ev > PASS_EV,
        "opening_is_negative_ev": ev < PASS_EV,
        "break_even_p_raise": p_star,
        "raise_policy": "fold",
    }


def has_physical_ace(ids: Sequence[int]) -> bool:
    return any(i in PHYSICAL_ACE_IDS for i in ids)


def n_physical_of(ids: Sequence[int], rank_ids: frozenset[int]) -> int:
    return sum(1 for i in ids if i in rank_ids)


def n_physical_jacks(ids: Sequence[int]) -> int:
    return n_physical_of(ids, PHYSICAL_JACK_IDS)


def n_physical_queens(ids: Sequence[int]) -> int:
    return n_physical_of(ids, PHYSICAL_QUEEN_IDS)


def n_physical_kings(ids: Sequence[int]) -> int:
    return n_physical_of(ids, PHYSICAL_KING_IDS)


def _class_slug(co_class: str) -> str:
    return co_class.lower()


def sample_class_ids_forced(
    co_class: str,
    rng: random.Random,
    *,
    require_bug: bool = False,
    require_physical_ace: bool = False,
) -> tuple[int, ...] | None:
    """Rejection-sample ``co_class`` with optional singleton blockers forced in."""
    forced: list[int] = []
    if require_bug:
        forced.append(BUG_ID)
    if require_physical_ace:
        forced.append(rng.choice(tuple(PHYSICAL_ACE_IDS)))
    if len(set(forced)) != len(forced):
        return None
    blocked = set(forced)
    pool = [i for i in range(53) if i not in blocked]
    need = 5 - len(forced)
    if need < 0 or len(pool) < need:
        return None
    for _ in range(8_000):
        ids = tuple(sorted(forced + rng.sample(pool, need)))
        if _ids_to_cls(ids) == co_class:
            return ids
    return None


def remaining_sandbag_buckets(co_ids: Sequence[int]) -> dict[str, int]:
    """Exact C(48,5) opener-class counts given CO's five cards."""
    rem = [i for i in range(53) if i not in set(co_ids)]
    counts: dict[str, int] = {
        "straight": 0,
        "flush": 0,
        "two_pair": 0,
        "two_pair_aces_up": 0,
        "trips": 0,
        "boats_plus": 0,
        "pair_A": 0,
        "two_pair_plus": 0,
        "hj_set": 0,
        "n_remaining": 0,
    }
    boats = frozenset({"full_house", "four_of_a_kind", "straight_flush", "five_aces"})
    for combo in combinations(rem, 5):
        cls = _ids_to_cls(combo)
        counts["n_remaining"] += 1
        if cls is None:
            continue
        if cls == "straight":
            counts["straight"] += 1
        elif cls == "flush":
            counts["flush"] += 1
        elif cls == "two_pair":
            counts["two_pair"] += 1
        elif cls == "two_pair_aces_up":
            counts["two_pair_aces_up"] += 1
        elif cls in TRIPS_CLASSES:
            counts["trips"] += 1
        elif cls in boats:
            counts["boats_plus"] += 1
        elif cls == "pair_A":
            counts["pair_A"] += 1
        if cls in TWO_PAIR_PLUS_CLASSES:
            counts["two_pair_plus"] += 1
        if cls in TWO_PAIR_PLUS_CLASSES or cls == "pair_A":
            counts["hj_set"] += 1
    return counts


def labeled_remaining_hand(co_ids: Sequence[int], label: str) -> dict[str, Any]:
    cls = _ids_to_cls(co_ids)
    return {
        "label": label,
        "co_ids": list(co_ids),
        "co_class": cls,
        "has_bug": BUG_ID in set(co_ids),
        "has_physical_ace": has_physical_ace(co_ids),
        "n_physical_jacks": n_physical_jacks(co_ids),
        "n_physical_queens": n_physical_queens(co_ids),
        "n_physical_kings": n_physical_kings(co_ids),
        **remaining_sandbag_buckets(co_ids),
    }


def _remaining_job(
    item: tuple[str, tuple[int, ...], str],
) -> tuple[str, dict[str, Any]]:
    key, ids, label = item
    return key, labeled_remaining_hand(ids, label)


def exact_remaining_matched_kickers() -> dict[str, Any]:
    """Exact C(48,5) sandbag buckets for the nine matched JJ/QQ/KK hands."""
    jobs = [
        (f"{_class_slug(cls)}_{flavor}", ids, label)
        for cls in BLOCKER_CLASSES
        for flavor, (ids, label) in MATCHED_KICKER_HANDS[cls].items()
    ]
    workers = min(len(jobs), os.cpu_count() or 4)
    remaining: dict[str, Any] = {}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for key, payload in pool.map(_remaining_job, jobs):
            remaining[key] = payload
    return remaining


def deal_mc_p_raise_co_flavor(
    *,
    n: int = DEFAULT_BLOCKER_MC_N,
    seed: int = DEFAULT_MC_SEED,
    co_class: str = "pair_K",
    require_bug: bool = False,
    require_physical_ace: bool = False,
    world: str = WORLD,
    sandbag_rate: float = 1.0,
) -> CoDealMcResult:
    """Same folded-to-CO raise MC as ``deal_mc_p_raise_given_passed_co``, with
    singleton blockers forced into CO's five cards.

    Does **not** replace the class-average 40k pins. The bug is an ace (or a
    straight/flush fill), not a duplicate king: ``pair_K`` plus the joker is
    two kings + bug as ace kicker. Interior ``sandbag_rate`` < 1 is the same
    card-removal MC with sandbag-set holders opening at 1−r.
    """
    rng = random.Random(seed)
    n_tried = 0
    n_co_class = 0
    n_cond = 0
    n_raise = 0
    n_bug = 0
    hist: dict[int, int] = {k: 0 for k in range(7)}
    while n_cond < n:
        n_tried += 1
        co_ids = sample_class_ids_forced(
            co_class,
            rng,
            require_bug=require_bug,
            require_physical_ace=require_physical_ace,
        )
        if co_ids is None:
            continue
        n_co_class += 1
        rest = [i for i in range(53) if i not in co_ids]
        rng.shuffle(rest)
        n_sandbag = 0
        rejected = False
        for seat in SEATS_1_6:
            start = 5 * (seat - 1)
            cls = _ids_to_cls(rest[start : start + 5])
            reject, raises = seat_passed_then_raises(
                cls, seat, world, rng, sandbag_rate
            )
            if reject:
                rejected = True
                break
            if raises:
                n_sandbag += 1
        if rejected:
            continue
        n_cond += 1
        if BUG_ID in co_ids:
            n_bug += 1
        hist[n_sandbag] = hist.get(n_sandbag, 0) + 1
        if n_sandbag:
            n_raise += 1
    p = n_raise / n_cond if n_cond else 0.0
    se = math.sqrt(p * (1.0 - p) / n_cond) if n_cond else 0.0
    return CoDealMcResult(
        n=n,
        seed=seed,
        n_co_class=n_co_class,
        n_conditioned=n_cond,
        n_raise=n_raise,
        p_raise=p,
        p_co_has_bug=n_bug / n_cond if n_cond else 0.0,
        n_tried=n_tried,
        sandbag_seats_hist={str(k): hist[k] for k in range(7)},
        se_p_raise=se,
        co_class=co_class,
        world=world,
        sandbag_rate=sandbag_rate,
    )


def estimate_behind_probs_flavor(
    co_class: str,
    *,
    n_deals: int,
    seed: int,
    require_bug: bool = False,
    require_physical_ace: bool = False,
) -> dict[str, float]:
    """0% CO-behind mix, same method as ``cutoff_open.estimate_behind_probs``,
    with singleton blockers forced. Reuses that lab's *unfiltered* 1–6 deal
    so the leaf stays comparable to L.
    """
    from fivecarddraw.validation.cutoff_open import BehindAccum

    two_to_one = _two_to_one_id_cache()
    rng = random.Random(seed)
    acc = BehindAccum()
    tries = 0
    cap = n_deals * 80
    while acc.n < n_deals and tries < cap:
        tries += 1
        co_ids = sample_class_ids_forced(
            co_class,
            rng,
            require_bug=require_bug,
            require_physical_ace=require_physical_ace,
        )
        if co_ids is None:
            continue
        rem = [i for i in range(53) if i not in co_ids]
        rng.shuffle(rem)
        kinds: list[str] = []
        for s in range(7):
            ids = tuple(sorted(rem[s * 5 : (s + 1) * 5]))
            kinds.append(classify_seat_ids(ids, two_to_one))
        seat16 = kinds[:6]
        acc.add(
            bn_kind=kinds[6],
            any_16_2to1=any(k == "two_to_one" for k in seat16),
            co_bug=BUG_ID in co_ids,
        )
    out = acc.as_dict()
    out["co_class"] = co_class
    out["seed"] = seed
    out["tries"] = tries
    out["require_bug"] = require_bug
    out["require_physical_ace"] = require_physical_ace
    return out


def zero_leaf_from_behind(
    probs: dict[str, float],
    *,
    class_row: dict[str, Any] | None = None,
    pair_k_row: dict[str, Any] | None = None,
) -> dict[str, float]:
    """Reweight locked class-average street EVs with a flavor's steal / call mix.

    Does **not** resimulate draw / post-draw. Street EVs stay that class's
    average cells (conservative if the bug also wins more often).
    ``pair_k_row`` is an alias for KK callers.
    """
    row = class_row if class_row is not None else pair_k_row
    if row is None:
        raise ValueError("class_row or pair_k_row is required")
    cls = str(row.get("co_class", "pair_K"))
    ev_2 = blend_2to1_street(
        probs,
        ev_caller_first=float(row["vs_2to1_caller_first"]["ev_co_street"]),
        ev_co_first=float(row["vs_2to1_co_first"]["ev_co_street"]),
    )
    ev_bn = float(row["vs_bn_legal"]["ev_co_street"])
    leaf = mix_open_ev(
        p_steal=float(probs["p_steal"]),
        p_vs_2to1=float(probs["p_vs_2to1"]),
        p_vs_bn=float(probs["p_vs_bn_legal"]),
        ev_street_2to1=ev_2,
        ev_street_bn=ev_bn,
    )
    return {
        "leaf": leaf,
        "ev_street_2to1": ev_2,
        "ev_street_bn": ev_bn,
        "p_steal": float(probs["p_steal"]),
        "p_vs_2to1": float(probs["p_vs_2to1"]),
        "p_vs_bn_legal": float(probs["p_vs_bn_legal"]),
        "street_ev_source": f"{cls} class-average cutoff_open cells",
    }


def flavor_row(
    *,
    label: str,
    mc: CoDealMcResult,
    leaf: float,
    p_ind_1: float,
    leaf_note: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = class_row(mc, leaf=leaf, p_ind_1=p_ind_1)
    row["flavor"] = label
    row["leaf_note"] = leaf_note
    if extra:
        row.update(extra)
    return row


def _vs_zero(row: dict[str, Any]) -> str:
    ev = float(row["ev_open_100pct"])
    se = row.get("se_ev_open_100pct")
    if se is None:
        leaf = float(row.get("ev_no_raise_leaf", 0.0))
        se = float(row.get("se_p_raise", 0.0)) * (leaf - FOLD_JJ_TO_RAISE_EV)
    within = row.get("ev_within_1se_of_zero")
    if within is None:
        within = abs(ev) <= float(se)
    if within:
        side = "+EV" if ev > 0.0 else "−EV" if ev < 0.0 else "0"
        return f"{side} inside 1 SE"
    if ev > 0.0:
        return "+EV"
    if ev < 0.0:
        return "−EV"
    return "0"


def _class_flavor_block(
    co_class: str,
    *,
    class_row: dict[str, Any],
    avg_leaf: float,
    p_ind_1: float,
    n: int,
    seed: int,
    n_leaf: int,
) -> dict[str, Any]:
    """Joker + ace-kicker mixes for one face pair (does not touch 40k pins)."""
    print(f"[blockers] {co_class} behind-probs n_leaf={n_leaf} + MC n={n}", flush=True)
    behind_bug = estimate_behind_probs_flavor(
        co_class, n_deals=n_leaf, seed=seed, require_bug=True
    )
    behind_ace = estimate_behind_probs_flavor(
        co_class, n_deals=n_leaf, seed=seed, require_physical_ace=True
    )
    leaf_bug = zero_leaf_from_behind(behind_bug, class_row=class_row)
    leaf_ace = zero_leaf_from_behind(behind_ace, class_row=class_row)
    mc_bug = deal_mc_p_raise_co_flavor(
        n=n, seed=seed, co_class=co_class, require_bug=True
    )
    mc_ace = deal_mc_p_raise_co_flavor(
        n=n, seed=seed, co_class=co_class, require_physical_ace=True
    )
    bug_avg = flavor_row(
        label=f"{co_class}_bug_avg_leaf",
        mc=mc_bug,
        leaf=avg_leaf,
        p_ind_1=p_ind_1,
        leaf_note=f"conservative: class-average {co_class} L",
    )
    bug_rew = flavor_row(
        label=f"{co_class}_bug_reweighted_leaf",
        mc=mc_bug,
        leaf=leaf_bug["leaf"],
        p_ind_1=p_ind_1,
        leaf_note=(
            f"0% steal/2:1/BN mix reweighted; street EVs stay {co_class} average"
        ),
        extra={"zero_leaf_reweight": leaf_bug, "behind_probs": behind_bug},
    )
    ace_avg = flavor_row(
        label=f"{co_class}_ace_kicker_avg_leaf",
        mc=mc_ace,
        leaf=avg_leaf,
        p_ind_1=p_ind_1,
        leaf_note=f"conservative: class-average {co_class} L",
        extra={"behind_probs": behind_ace, "zero_leaf_reweight": leaf_ace},
    )
    ace_rew = flavor_row(
        label=f"{co_class}_ace_kicker_reweighted_leaf",
        mc=mc_ace,
        leaf=leaf_ace["leaf"],
        p_ind_1=p_ind_1,
        leaf_note=(
            f"0% steal/2:1/BN mix reweighted; street EVs stay {co_class} average"
        ),
    )
    return {
        "bug": {
            "avg_leaf_mix": bug_avg,
            "reweighted_leaf_mix": bug_rew,
        },
        "ace_kicker": {
            "avg_leaf_mix": ace_avg,
            "reweighted_leaf_mix": ace_rew,
        },
    }


def ranking_co_vs_bn_from_pins(
    *,
    cutoff_fixture: dict[str, Any] | None = None,
    sandbag_fixture: dict[str, Any] | None = None,
    bn_1_6_path: Path | None = None,
    co_p_raise: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Decompose CO KK>QQ>JJ vs BN's near-tie from existing pins. No new HU."""
    cutoff = cutoff_fixture if cutoff_fixture is not None else load_cutoff_open()
    if sandbag_fixture is None:
        path = bn_1_6_path or (
            Path(__file__).resolve().parents[3]
            / "tests"
            / "fixtures"
            / "validation"
            / "sandbag_v1_seats_1_6_only.json"
        )
        bn_data = json.loads(path.read_text(encoding="utf-8"))
    else:
        bn_data = sandbag_fixture
    co_by = {r["co_class"]: r for r in cutoff["by_class"]}
    bn_by = {r["bn_class"]: r for r in bn_data["q2"]["rows"]}
    co_rows: dict[str, Any] = {}
    for cls in BLOCKER_CLASSES:
        row = co_by[cls]
        bn = row["vs_bn_legal"]
        pr = row["probs"]
        co_rows[cls] = {
            "leaf": float(row["ev_open"]),
            "p_steal": float(pr["p_steal"]),
            "p_vs_2to1": float(pr["p_vs_2to1"]),
            "p_vs_bn_legal": float(pr["p_vs_bn_legal"]),
            "ev_co_street_bn": float(bn["ev_co_street"]),
            "p_co_wins_final_bn": float(bn["p_co_wins_final"]),
        }
    bn_rows: dict[str, Any] = {}
    for cls in BLOCKER_CLASSES:
        row = bn_by[cls]
        bn_rows[cls] = {
            "leaf": float(row["ev_no_raise_leaf"]),
            "ev_bn_locked": float(row["ev_bn_locked"]),
            "p_raise": float(row["p_raise"]),
            "se_p_raise": float(row["se_p_raise"]),
            "ev_open_100pct": float(row["ev_open"]),
        }

    def _delta(a: str, b: str, *, leaves: dict[str, float], ps: dict[str, float]) -> dict[str, float]:
        la, lb = leaves[a], leaves[b]
        pa, pb = ps[a], ps[b]
        # EV = (1-p)*L + p*(-2). Hold p at b for the leaf piece; L at a for p.
        leaf_hold_p_b = (1.0 - pb) * (la - lb)
        p_hold_l_a = -(pa - pb) * (la + 2.0)
        return {
            "delta_ev_a_minus_b": leaf_hold_p_b + p_hold_l_a,
            "leaf_piece_hold_p_at_b": leaf_hold_p_b,
            "p_raise_piece_hold_L_at_a": p_hold_l_a,
            "delta_L": la - lb,
            "delta_p_raise": pa - pb,
        }

    co_leaves = {c: co_rows[c]["leaf"] for c in BLOCKER_CLASSES}
    # Class-average p_raise lives on the sandbag 40k pins; ranking of *leaves*
    # is the 0% lab. Include both.
    if co_p_raise is None:
        sandbag = load_fixture()
        co_p = {
            r["co_class"]: float(r["p_raise"])
            for r in sandbag["by_class"]
            if r["co_class"] in BLOCKER_CLASSES
        }
    else:
        co_p = {k: float(v) for k, v in co_p_raise.items()}
    bn_leaves = {c: bn_rows[c]["leaf"] for c in BLOCKER_CLASSES}
    bn_p = {c: bn_rows[c]["p_raise"] for c in BLOCKER_CLASSES}
    se_jj = float(bn_rows["pair_J"]["se_p_raise"])
    se_qq = float(bn_rows["pair_Q"]["se_p_raise"])
    se_kk = float(bn_rows["pair_K"]["se_p_raise"])
    z_jj_qq = (bn_p["pair_Q"] - bn_p["pair_J"]) / math.sqrt(se_jj**2 + se_qq**2)
    z_jj_kk = (bn_p["pair_K"] - bn_p["pair_J"]) / math.sqrt(se_jj**2 + se_kk**2)
    return {
        "note": (
            "CO 0% leaves strictly increase JJ < QQ < KK because BN is still "
            "to act (~21% legal). Higher pair wins more of the HU vs BN jacks+ "
            "range (cutoff_open_summary.json vs_bn_legal). Button no-raise "
            "leaves were ~+$1.93 (steal-dominated, ~7% 2:1); ranking there "
            "was p_raise noise (z<1.3) plus QQ's weaker locked EV_bn cell."
        ),
        "sources": [
            "tests/fixtures/validation/cutoff_open_summary.json",
            "tests/fixtures/validation/cutoff_open_sandbag_v1.json",
            "tests/fixtures/validation/sandbag_v1_seats_1_6_only.json",
        ],
        "co_0pct": co_rows,
        "bn_1_6_only": bn_rows,
        "co_delta_kk_minus_jj": _delta(
            "pair_K", "pair_J", leaves=co_leaves, ps=co_p
        ),
        "co_delta_qq_minus_jj": _delta(
            "pair_Q", "pair_J", leaves=co_leaves, ps=co_p
        ),
        "bn_delta_jj_minus_qq": _delta(
            "pair_J", "pair_Q", leaves=bn_leaves, ps=bn_p
        ),
        "bn_delta_jj_minus_kk": _delta(
            "pair_J", "pair_K", leaves=bn_leaves, ps=bn_p
        ),
        "bn_p_raise_z_qq_minus_jj": z_jj_qq,
        "bn_p_raise_z_kk_minus_jj": z_jj_kk,
    }


def build_blockers_payload(
    *,
    n: int = DEFAULT_BLOCKER_MC_N,
    seed: int = DEFAULT_MC_SEED,
    n_leaf: int = DEFAULT_BLOCKER_LEAF_N,
    cutoff_fixture: dict[str, Any] | None = None,
    p_ind_1: float | None = None,
    co_p_raise: dict[str, float] | None = None,
) -> dict[str, Any]:
    """JJ/QQ/KK + joker / ace-kicker split on the same fold-to-raise mix."""
    cutoff = cutoff_fixture if cutoff_fixture is not None else load_cutoff_open()
    by_open = {r["co_class"]: r for r in cutoff["by_class"]}
    p1 = (
        float(independent_p_raise_unconditional(WORLD)["p_raise"])
        if p_ind_1 is None
        else p_ind_1
    )

    print("[blockers] exact C(48,5) remaining buckets (9 matched hands)", flush=True)
    remaining = exact_remaining_matched_kickers()

    out: dict[str, Any] = {
        "note": (
            "The bug plays as an ace (or completes a straight/flush), not a "
            "third of the pair rank. pair_X + joker = two of that rank + bug "
            "as ace kicker. Ace kicker is a physical ace (no joker required)."
        ),
        "mc": {"n": n, "seed": seed, "n_leaf": n_leaf},
        "remaining_exact": remaining,
    }
    answers: dict[str, Any] = {}
    for cls in BLOCKER_CLASSES:
        class_row = by_open[cls]
        avg_leaf = float(class_row["ev_open"])
        slug = _class_slug(cls)
        bundle = _class_flavor_block(
            cls,
            class_row=class_row,
            avg_leaf=avg_leaf,
            p_ind_1=p1,
            n=n,
            seed=seed,
            n_leaf=n_leaf,
        )
        out[f"{slug}_bug"] = bundle["bug"]
        out[f"{slug}_ace_kicker"] = bundle["ace_kicker"]
        bug_avg = bundle["bug"]["avg_leaf_mix"]
        bug_rew = bundle["bug"]["reweighted_leaf_mix"]
        ace_avg = bundle["ace_kicker"]["avg_leaf_mix"]
        ace_rew = bundle["ace_kicker"]["reweighted_leaf_mix"]
        answers[f"{slug}_bug_plus_ev_at_100pct_avg_leaf"] = bug_avg[
            "opening_is_positive_ev"
        ]
        answers[f"{slug}_bug_plus_ev_at_100pct_reweighted"] = bug_rew[
            "opening_is_positive_ev"
        ]
        answers[f"{slug}_ace_plus_ev_at_100pct_avg_leaf"] = ace_avg[
            "opening_is_positive_ev"
        ]
        answers[f"{slug}_ace_plus_ev_at_100pct_reweighted"] = ace_rew[
            "opening_is_positive_ev"
        ]
        answers[f"{slug}_bug_avg_leaf_within_1se_of_zero"] = bug_avg[
            "ev_within_1se_of_zero"
        ]
        answers[f"{slug}_ace_rew_within_1se_of_zero"] = ace_rew[
            "ev_within_1se_of_zero"
        ]

    joker_rew = [
        answers[f"{_class_slug(c)}_bug_plus_ev_at_100pct_reweighted"]
        for c in BLOCKER_CLASSES
    ]
    ace_rew_plus = [
        answers[f"{_class_slug(c)}_ace_plus_ev_at_100pct_reweighted"]
        for c in BLOCKER_CLASSES
    ]
    answers["joker_in_hand_plus_ev_all_three_reweighted"] = all(joker_rew)
    answers["ace_kicker_plus_ev_any_three_reweighted"] = any(ace_rew_plus)
    out["answers"] = answers
    out["ranking_co_vs_bn"] = ranking_co_vs_bn_from_pins(
        cutoff_fixture=cutoff, co_p_raise=co_p_raise
    )
    return out


def class_row(
    mc: CoDealMcResult,
    *,
    leaf: float,
    p_ind_1: float,
) -> dict[str, Any]:
    mix = mix_co_open(mc.p_raise, leaf)
    mix_0 = mix_co_open(0.0, leaf)
    rates = invert_calibrated_rate(
        mix["break_even_p_raise"],
        p_mc_1=mc.p_raise,
        p_ind_1=p_ind_1,
        world=mc.world,
    )
    se_ev = mc.se_p_raise * (leaf - FOLD_JJ_TO_RAISE_EV)
    ev = float(mix["ev_open"])
    return {
        "co_class": mc.co_class,
        "world": mc.world,
        **mix,
        "ev_open_0pct": mix_0["ev_open"],
        "ev_open_100pct": mix["ev_open"],
        "se_p_raise": mc.se_p_raise,
        "se_ev_open_100pct": se_ev,
        "ev_within_1se_of_zero": abs(ev) <= se_ev,
        "deal_mc": mc.as_dict(),
        "r_calibrated": rates["r"],
        "r_linear": rates["linear_r"],
        "r_above_100pct": rates["above_100pct"],
        "kappa_mc_over_ind": rates["kappa"],
        "independent_p_raise_1": p_ind_1,
    }


def build_co_vs_seats_1_6_payload(
    *,
    n: int = DEFAULT_MC_N,
    seed: int = DEFAULT_MC_SEED,
    n_co: int = DEFAULT_REMOVAL_BN_N,
    n_hands_per_co: int = DEFAULT_REMOVAL_HANDS_PER_BN,
    classes: Sequence[str] = FOCUS_CLASSES,
    mc_by_class: dict[str, CoDealMcResult] | None = None,
    removal_by_class: dict[str, dict[str, Any]] | None = None,
    cutoff_fixture: dict[str, Any] | None = None,
) -> dict[str, Any]:
    world = WORLD
    cutoff = cutoff_fixture if cutoff_fixture is not None else load_cutoff_open()
    counts = dict(load_showdown_matrix()["opener_combo_counts"])
    two_pair_plus = sandbag_set_combo_count(SEAT_UTG, world)
    uncond = independent_p_raise_unconditional(world)
    p_ind_1 = float(uncond["p_raise"])
    masses = inventory_masses(world=world)
    cached_mc = dict(mc_by_class or {})
    cached_rem = dict(removal_by_class or {})
    rows: list[dict[str, Any]] = []
    for cls in classes:
        leaf = load_co_zero_sandbag_leaf(cls, fixture=cutoff)
        if cls not in cached_rem:
            rem = independent_p_raise_bn_class_blocked(
                cls,
                world=world,
                n_bn=n_co,
                n_hands_per_bn=n_hands_per_co,
                seed=seed,
            )
            rem["co_class"] = rem.pop("bn_class", cls)
            cached_rem[cls] = rem
        if cls not in cached_mc:
            cached_mc[cls] = deal_mc_p_raise_given_passed_co(
                n=n, seed=seed, co_class=cls, world=world
            )
        row = class_row(cached_mc[cls], leaf=leaf, p_ind_1=p_ind_1)
        row["independent_blocked"] = cached_rem[cls]
        rows.append(row)

    by = {r["co_class"]: r for r in rows}
    binding = min(rows, key=lambda r: float(r["r_calibrated"])) if rows else None
    jj = by.get("pair_J")
    return {
        "meta": {
            "frame": "cutoff_open_sandbag_v1",
            "world": world,
            "parent_0pct_frame": "cutoff_open_no_sandbagging",
            "analog_of": "button_open_sandbag_v1 seats_1_6_only",
            "sandbag_set": {
                "seats_1_5": "two_pair_plus",
                "seat_6_hj_also": "pair_A",
                "seat_7_co": "never_sandbags_opens_all_legal",
                "seat_8_bn": "not_in_p_raise",
                "lj_opens_aces": True,
                "aces_sandbag_seats": sorted(aces_sandbag_seats(world)),
            },
            "accounting": {
                "pass": PASS_EV,
                "steal": STEAL_EV,
                "fold_jj_qq_kk_to_raise": FOLD_JJ_TO_RAISE_EV,
                "formula": "EV(open) = (1-p_raise)*L + p_raise*(-2)",
                "L": (
                    "cutoff_open_no_sandbagging EV(open) for the class "
                    "(steal + 2:1 mix + BN-behind legal calls; locked draws)"
                ),
                "p_raise": (
                    "P(≥1 of seats 1–6 has sandbag-set | 1–6 passed, CO holds class). "
                    "BN is unrestricted and not a raiser in this mix."
                ),
                "no_live_nash": (
                    "No simulation of draw choice or post-draw Nash. Street EVs "
                    "inside L are locked non-bluff / honest-policy numbers."
                ),
            },
            "mc": {"n": n, "seed": seed},
            "removal_planning": {
                "n_co": n_co,
                "n_hands_per_co": n_hands_per_co,
                "seed": seed,
            },
            "doc": "docs/research/cutoff_open_sandbag_v1.md",
            "regenerate": (
                "python -m fivecarddraw.validation.cutoff_open_sandbag --write-fixture"
            ),
        },
        "inventory": {
            "total_hands": TOTAL_HANDS,
            "open_legal": sum(counts.values()),
            "two_pair_plus": two_pair_plus,
            "pair_A": counts["pair_A"],
            "pair_J": counts["pair_J"],
            "pair_Q": counts["pair_Q"],
            "pair_K": counts["pair_K"],
            "sandbag_seats_1_5": two_pair_plus,
            "sandbag_seat_6_hj": sandbag_set_combo_count(SEAT_HJ, world),
            "sandbag_seat_7_co": sandbag_set_combo_count(SEAT_CO, world),
            "voluntary_seats_1_5": voluntary_combo_count(SEAT_UTG, world),
            "voluntary_seat_6_hj": voluntary_combo_count(SEAT_HJ, world),
            "not_open_legal": not_open_legal_count(),
            **masses,
        },
        "independent_unconditional": uncond,
        "independent_p_raise_at_r1": p_ind_1,
        "same_world_as_seats_1_6_only": sandbag_seats(world)
        == sandbag_seats(SANDBAG_WORLD_SEATS_1_6_ONLY),
        "by_class": rows,
        "answers": {
            "q1_jj_plus_ev_at_100pct": bool(jj and not jj["opening_is_negative_ev"]),
            "q2_jj_plus_ev_at_0pct": bool(jj and jj["ev_open_0pct"] > PASS_EV),
            "q3_jj_r_calibrated": None if jj is None else jj["r_calibrated"],
            "q3_jj_r_linear": None if jj is None else jj["r_linear"],
            "binding_class": None if binding is None else binding["co_class"],
            "binding_r_calibrated": None if binding is None else binding["r_calibrated"],
            "note": (
                "Never-slowplay (open every legal) was the 0% lab. This frame "
                "asks whether opening JJ/QQ/KK stays +EV when 1–6 sandbag."
            ),
        },
    }


def default_fixture_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "validation"
        / "cutoff_open_sandbag_v1.json"
    )


def write_fixture(
    path: Path | None = None,
    *,
    payload: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Path:
    path = path or default_fixture_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = payload if payload is not None else build_co_vs_seats_1_6_payload(**kwargs)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def merge_blockers_into_fixture(
    path: Path | None = None,
    *,
    n: int = DEFAULT_BLOCKER_MC_N,
    seed: int = DEFAULT_MC_SEED,
    n_leaf: int = DEFAULT_BLOCKER_LEAF_N,
) -> Path:
    """Keep the locked 40k JJ/QQ/KK pins; add the singleton-blocker section."""
    path = path or default_fixture_path()
    data = json.loads(path.read_text(encoding="utf-8"))
    co_p = {r["co_class"]: float(r["p_raise"]) for r in data["by_class"]}
    data["blockers"] = build_blockers_payload(
        n=n,
        seed=seed,
        n_leaf=n_leaf,
        p_ind_1=float(data["independent_p_raise_at_r1"]),
        co_p_raise=co_p,
    )
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def load_fixture(path: Path | None = None) -> dict[str, Any]:
    path = path or default_fixture_path()
    return json.loads(path.read_text(encoding="utf-8"))


def _print_payload(payload: dict[str, Any]) -> None:
    print(
        f"world={payload['meta']['world']} independent p(1) = "
        f"{payload['independent_p_raise_at_r1']:.6f}"
    )
    for row in payload["by_class"]:
        sign0 = "+" if row["ev_open_0pct"] > 0 else "−"
        sign1 = "+" if row["opening_is_positive_ev"] else "−"
        print(
            f"{row['co_class']} L={row['ev_no_raise_leaf']:+.5f} "
            f"p_raise={row['p_raise']:.6f} (se {row['se_p_raise']:.6f}) "
            f"EV(0%)={row['ev_open_0pct']:+.4f} ({sign0}) "
            f"EV(100%)={row['ev_open_100pct']:+.4f} ({sign1}) "
            f"p*={row['break_even_p_raise']:.4f} "
            f"r_cal={row['r_calibrated']:.4f} r_lin={row['r_linear']:.4f}"
        )
    a = payload["answers"]
    print(
        f"binding class={a['binding_class']} r_cal={a['binding_r_calibrated']}"
    )


def _print_blockers(payload: dict[str, Any]) -> None:
    blockers = payload.get("blockers") or {}
    if not blockers:
        return
    print(
        f"{'flavor':<28} {'p_raise':>8} {'SE':>8} {'L_rew':>8} {'EV(100%)':>9}  vs 0"
    )
    by = {r["co_class"]: r for r in payload["by_class"]}
    for cls in BLOCKER_CLASSES:
        avg = by[cls]
        print(
            f"{cls + ' class avg':<28} {avg['p_raise']:8.4f} "
            f"{avg['se_p_raise']:8.5f} {avg['ev_no_raise_leaf']:8.3f} "
            f"{avg['ev_open_100pct']:9.3f}  {_vs_zero(avg)}"
        )
        slug = _class_slug(cls)
        for kind, key in (("joker", f"{slug}_bug"), ("ace", f"{slug}_ace_kicker")):
            rew = blockers[key]["reweighted_leaf_mix"]
            print(
                f"{cls + ' +' + kind + ' rew':<28} {rew['p_raise']:8.4f} "
                f"{rew['se_p_raise']:8.5f} {rew['ev_no_raise_leaf']:8.3f} "
                f"{rew['ev_open_100pct']:9.3f}  {_vs_zero(rew)}"
            )
    print(f"blockers answers={blockers.get('answers')}")


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(
        description="CO open vs seats 1–6 sandbag rate (fold JJ/QQ/KK to raise)"
    )
    p.add_argument("-o", "--output", type=Path, default=None)
    p.add_argument("--n", type=int, default=DEFAULT_MC_N)
    p.add_argument("--seed", type=int, default=DEFAULT_MC_SEED)
    p.add_argument("--n-co", type=int, default=DEFAULT_REMOVAL_BN_N)
    p.add_argument("--n-hands-per-co", type=int, default=DEFAULT_REMOVAL_HANDS_PER_BN)
    p.add_argument("--write-fixture", action="store_true")
    p.add_argument(
        "--write-blockers",
        action="store_true",
        help=(
            "Augment the existing fixture with JJ/QQ/KK + joker / ace-kicker "
            "MCs; do not redo 40k class pins"
        ),
    )
    p.add_argument(
        "--write-chart",
        action="store_true",
        help=(
            "Interpolate the CO open chart (slowplay r × blockers) from locked "
            "0%/100% pins; do not redo endpoint MC"
        ),
    )
    p.add_argument("--blocker-n", type=int, default=DEFAULT_BLOCKER_MC_N)
    p.add_argument("--blocker-n-leaf", type=int, default=DEFAULT_BLOCKER_LEAF_N)
    p.add_argument(
        "--classes",
        type=str,
        default=None,
        help="Comma-separated CO classes (default: pair_J,pair_Q,pair_K)",
    )
    args = p.parse_args()
    if args.write_chart:
        from fivecarddraw.validation.cutoff_open_chart import main_write_chart

        main_write_chart(args.output)
        return
    if args.write_blockers:
        path = merge_blockers_into_fixture(
            args.output,
            n=args.blocker_n,
            seed=args.seed,
            n_leaf=args.blocker_n_leaf,
        )
        print(f"Wrote blockers into {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        _print_payload(data)
        _print_blockers(data)
        return
    classes = (
        tuple(c.strip() for c in args.classes.split(",") if c.strip())
        if args.classes
        else FOCUS_CLASSES
    )
    payload = build_co_vs_seats_1_6_payload(
        n=args.n,
        seed=args.seed,
        n_co=args.n_co,
        n_hands_per_co=args.n_hands_per_co,
        classes=classes,
    )
    if args.write_fixture or args.output is not None:
        path = write_fixture(args.output, payload=payload)
        print(f"Wrote {path}")
    _print_payload(payload)


if __name__ == "__main__":
    main()
