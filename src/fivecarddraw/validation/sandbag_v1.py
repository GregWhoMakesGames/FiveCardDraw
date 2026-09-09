"""Sandbag-set v1: seat predicates and folded-to-BN raise probability.

Frame: ``button_open_sandbag_v1``. Three laboratories share this module:

- ``seats_1_7`` (Agent A pin): seats 1–7 pass the v1 sandbag-set 100%
  and always raise a BN open. Opening JJ is −EV.
- ``seats_1_6_only`` (Q1/Q2): seats 1–6 sandbag that set; **CO never
  sandbags** (opens every legal hand). Folded-to-BN ⇒ CO has no open-legal.
- ``co_vs_seats_1_6``: same 1–6 sandbag-set as ``seats_1_6_only``; the
  actor is **CO** after 1–6 passed (BN unrestricted). Deal-MC lives in
  ``cutoff_open_sandbag.py``.

BN folds JJ/QQ/KK to a sandbag raise (−$2). The no-raise leaf is the
0% sandbag steal + 2:1 mix (locked-draw §3.4). This module does **not**
rebuild post-draw Nash / Ring 1.

Seats 1–8: UTG … LJ, HJ, CO, BN. Aces sandbag is HJ+CO in the 7-seat
world, HJ only in the 1–6-only world. LJ never sandbags aces.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from fivecarddraw.cards import Card, card_from_id
from fivecarddraw.validation.cascade_odds import TOTAL_HANDS
from fivecarddraw.validation.showdown_matrix import (
    STRAIGHT_PLUS_CLASSES,
    TRIPS_CLASSES,
    TWO_PAIR_CLASSES,
    classify_opener,
    load_showdown_matrix,
)

# Research seats 1–8 (UTG … BN). Code in this module is 1-indexed.
SEAT_UTG = 1
SEAT_LJ = 5
SEAT_HJ = 6
SEAT_CO = 7
SEAT_BN = 8
SEATS_BEFORE_BN = tuple(range(1, 8))  # 1–7
SANDBAG_WORLD_SEATS_1_7 = "seats_1_7"
SANDBAG_WORLD_SEATS_1_6_ONLY = "seats_1_6_only"
# Same sandbag seats as 1–6-only; hero is CO and BN is not filtered.
SANDBAG_WORLD_CO_VS_SEATS_1_6 = "co_vs_seats_1_6"
# 7-seat pin: HJ+CO aces. 1–6-only / CO-vs-1–6: CO opens all legal, so CO
# is never a sandbag raiser; HJ still buries aces.
ACES_SANDBAG_SEATS_BY_WORLD = {
    SANDBAG_WORLD_SEATS_1_7: frozenset({SEAT_HJ, SEAT_CO}),
    SANDBAG_WORLD_SEATS_1_6_ONLY: frozenset({SEAT_HJ}),
    SANDBAG_WORLD_CO_VS_SEATS_1_6: frozenset({SEAT_HJ}),
}
SANDBAG_SEATS_BY_WORLD = {
    SANDBAG_WORLD_SEATS_1_7: tuple(range(1, 8)),
    SANDBAG_WORLD_SEATS_1_6_ONLY: tuple(range(1, 7)),
    SANDBAG_WORLD_CO_VS_SEATS_1_6: tuple(range(1, 7)),
}
ACES_SANDBAG_SEATS = ACES_SANDBAG_SEATS_BY_WORLD[SANDBAG_WORLD_SEATS_1_7]  # HJ+CO, not LJ
DEFAULT_WORLD = SANDBAG_WORLD_SEATS_1_7

TWO_PAIR_PLUS_CLASSES = frozenset(TWO_PAIR_CLASSES + TRIPS_CLASSES + STRAIGHT_PLUS_CLASSES)
# Q2 walk order. JJ–KK fold to a sandbag raise. AA / two pair+ do not assume fold.
FOLD_TO_RAISE_CLASSES = ("pair_J", "pair_Q", "pair_K")
WALK_CLASSES_AFTER_FACE_PAIRS = ("pair_A", "two_pair", "trips")
# Locked-draw §3.4 EV_bn vs the full 2:1 mix (postdraw_nonbluff_ev_summary.json).
LOCKED_DRAW_D = {
    "pair_J": 3,
    "pair_Q": 3,
    "pair_K": 3,
    "pair_A": 3,
    "two_pair": 1,
    "trips": 2,
}
LOCKED_DRAW_EV_BN = {
    "pair_J": 3.0755,
    "pair_Q": 2.9615,
    "pair_K": 3.0935,
    "pair_A": 2.607,
    "two_pair": 2.1005,
    "trips": 2.329,
}

# Accounting (already pinned in the sandbag ticket).
PASS_EV = 0.0
STEAL_EV = 2.0
FOLD_JJ_TO_RAISE_EV = -2.0
# Called street: pot $6, EV_bn is BN's share; net vs pass is EV_bn − $2,
# so EV(open) = 2 + p_call * (EV_bn − 4). See button_open_no_sandbagging.md.
CALLED_POT = 6.0

# Reused 0% sandbag open pieces — do not resimulate the vs-draw street.
# EV_bn from tests/fixtures/validation/postdraw_nonbluff_ev_summary.json
# (locked draws; docs round pair_J d=3 to +3.08).
PAIR_J_D3_EV_BN = LOCKED_DRAW_EV_BN["pair_J"]
# Folded-to-BN P(any of 1–7 is 2:1). Independent planning ≈ 6.0% (BN no bug);
# 150k-deal check ≈ 6.9% (button_open_no_sandbagging.md).
P_ANY_2TO1_FOLDED_TO_BN_INDEPENDENT = 0.060
P_ANY_2TO1_FOLDED_TO_BN_MC = 0.069

# Deal MC pin (8-way, BN pair_J, 1–7 no voluntary opener).
DEFAULT_MC_SEED = 20260907
DEFAULT_MC_N = 40_000
DEFAULT_REMOVAL_BN_N = 2_000
DEFAULT_REMOVAL_HANDS_PER_BN = 50


def is_two_pair_plus(cls: str | None) -> bool:
    return cls is not None and cls in TWO_PAIR_PLUS_CLASSES


def aces_sandbag_seats(world: str = DEFAULT_WORLD) -> frozenset[int]:
    try:
        return ACES_SANDBAG_SEATS_BY_WORLD[world]
    except KeyError as exc:
        raise ValueError(f"unknown sandbag world {world!r}") from exc


def sandbag_seats(world: str = DEFAULT_WORLD) -> tuple[int, ...]:
    try:
        return SANDBAG_SEATS_BY_WORLD[world]
    except KeyError as exc:
        raise ValueError(f"unknown sandbag world {world!r}") from exc


def is_sandbag_set(
    cls: str | None, seat: int, world: str = DEFAULT_WORLD
) -> bool:
    """True if ``seat`` 100% passes this opener class in ``world``.

    7-seat: 1–7 two pair+; HJ and CO also pair of aces. LJ still opens aces.
    1–6-only / co_vs_seats_1_6: same for 1–6; **CO does not sandbag**.
    Non-openers and BN are never sandbag-set.
    """
    if cls is None or seat not in sandbag_seats(world):
        return False
    if is_two_pair_plus(cls):
        return True
    return cls == "pair_A" and seat in aces_sandbag_seats(world)


def is_voluntary_opener(
    cls: str | None, seat: int, world: str = DEFAULT_WORLD
) -> bool:
    """Open-legal minus that seat's sandbag-set. Under 100% sandbag, this opens.

    In ``seats_1_6_only``, CO's voluntary set is every open-legal hand, so a
    folded-to-BN node has **no open-legal in CO**.
    """
    if cls is None or seat not in SEATS_BEFORE_BN:
        return False
    return not is_sandbag_set(cls, seat, world)


def classify_cards(cards: Iterable[Card] | Sequence[int]) -> str | None:
    """``classify_opener`` over cards or card ids."""
    seq = tuple(cards)
    if seq and isinstance(seq[0], int):
        seq = tuple(card_from_id(i) for i in seq)  # type: ignore[misc]
    return classify_opener(seq)


def _opener_combo_counts() -> dict[str, int]:
    return dict(load_showdown_matrix()["opener_combo_counts"])


def sandbag_set_combo_count(seat: int, world: str = DEFAULT_WORLD) -> int:
    """Unconditional combo count of the v1 sandbag-set for ``seat``."""
    if seat not in sandbag_seats(world):
        return 0
    counts = _opener_combo_counts()
    two_pair_plus = sum(counts[c] for c in TWO_PAIR_PLUS_CLASSES)
    if seat in aces_sandbag_seats(world):
        return two_pair_plus + int(counts["pair_A"])
    return two_pair_plus


def voluntary_combo_count(seat: int, world: str = DEFAULT_WORLD) -> int:
    counts = _opener_combo_counts()
    open_legal = sum(counts.values())
    return open_legal - sandbag_set_combo_count(seat, world)


def not_open_legal_count() -> int:
    counts = _opener_combo_counts()
    return TOTAL_HANDS - sum(counts.values())


def p_sandbag_given_passed_unconditional(
    seat: int, world: str = DEFAULT_WORLD
) -> float:
    """P(sandbag-set | not voluntary) with no card removal.

    For CO in ``seats_1_6_only``, passed ⇒ not open-legal ⇒ this is 0.
    """
    s = sandbag_set_combo_count(seat, world)
    n = not_open_legal_count()
    return s / (s + n) if (s + n) else 0.0


def independent_p_raise_unconditional(
    world: str = DEFAULT_WORLD,
) -> dict[str, float]:
    """Independent-seat P(raise | seats before BN passed) ignoring BN's cards.

    Raise = ≥1 sandbag-set among that world's sandbag seats. CO in
    ``seats_1_6_only`` never contributes (P(neither | passed)=1).
    """
    p_no = 1.0
    by_seat: dict[str, float] = {}
    for seat in SEATS_BEFORE_BN:
        p_n_given_passed = 1.0 - p_sandbag_given_passed_unconditional(seat, world)
        by_seat[str(seat)] = p_n_given_passed
        p_no *= p_n_given_passed
    return {
        "p_no_raise": p_no,
        "p_raise": 1.0 - p_no,
        **{f"p_neither_given_passed_seat_{k}": v for k, v in by_seat.items()},
    }


def ev_no_sandbag_open(
    *,
    p_call: float = P_ANY_2TO1_FOLDED_TO_BN_MC,
    ev_bn_called: float = PAIR_J_D3_EV_BN,
) -> float:
    """0% sandbag open EV vs pass=0: steal + 2:1 call at locked-draw EV_bn."""
    return STEAL_EV + p_call * (ev_bn_called - CALLED_POT + STEAL_EV)


def ev_jj_no_sandbag_open(
    *,
    p_call: float = P_ANY_2TO1_FOLDED_TO_BN_MC,
    ev_bn_called: float = PAIR_J_D3_EV_BN,
) -> float:
    """0% sandbag JJ open EV vs pass=0: steal + 2:1 call at §3.4 pair_J d=3."""
    return ev_no_sandbag_open(p_call=p_call, ev_bn_called=ev_bn_called)


def ev_open_fold_to_raise(p_raise: float, *, ev_no_raise: float) -> float:
    """Mix: no-raise leaf + fold to raise (−$2)."""
    return (1.0 - p_raise) * ev_no_raise + p_raise * FOLD_JJ_TO_RAISE_EV


def ev_jj_open_100pct_sandbag(p_raise: float, *, ev_no_raise: float | None = None) -> float:
    """Mix: no-raise leaf reuses 0% sandbag JJ EV; raise leaf is fold JJ (−$2)."""
    leaf = ev_jj_no_sandbag_open() if ev_no_raise is None else ev_no_raise
    return ev_open_fold_to_raise(p_raise, ev_no_raise=leaf)


def locked_leaf_ev(
    bn_class: str,
    *,
    p_call: float = P_ANY_2TO1_FOLDED_TO_BN_MC,
) -> float:
    """No-raise leaf for ``bn_class``: §3.4 locked draw + reused 6.9% 2:1 mix."""
    if bn_class not in LOCKED_DRAW_EV_BN:
        raise KeyError(f"no locked-draw EV_bn for {bn_class!r}")
    return ev_no_sandbag_open(
        p_call=p_call, ev_bn_called=LOCKED_DRAW_EV_BN[bn_class]
    )


def _ids_to_cls(ids: Sequence[int]) -> str | None:
    return classify_opener(tuple(card_from_id(i) for i in ids))


def independent_p_raise_bn_class_blocked(
    bn_class: str = "pair_J",
    *,
    world: str = DEFAULT_WORLD,
    n_bn: int = DEFAULT_REMOVAL_BN_N,
    n_hands_per_bn: int = DEFAULT_REMOVAL_HANDS_PER_BN,
    seed: int = DEFAULT_MC_SEED,
) -> dict[str, Any]:
    """Independent-seat P(raise | passed) with BN ``bn_class`` card removal.

    Sample BN of that class, then sample 5-card hands from the remaining 48.
    Seat type relabels pair_A (voluntary UTG–LJ; sandbag HJ, and CO only in
    the 7-seat world). CO in ``seats_1_6_only`` never sandbags.
    """
    rng = random.Random(seed)
    deck = list(range(53))
    n_early_s = n_early_v = n_early_n = 0
    n_hj_s = n_hj_v = n_hj_n = 0
    n_co_s = n_co_v = n_co_n = 0
    n_bn_ok = 0
    n_bn_bug = 0
    tries = 0
    while n_bn_ok < n_bn:
        rng.shuffle(deck)
        tries += 1
        bn_ids = deck[:5]
        cls = _ids_to_cls(bn_ids)
        if cls != bn_class:
            continue
        n_bn_ok += 1
        if 52 in bn_ids:
            n_bn_bug += 1
        rem = deck[5:]
        for _ in range(n_hands_per_bn):
            rng.shuffle(rem)
            other = rem[:5]
            ocls = _ids_to_cls(other)
            if ocls is None:
                n_early_n += 1
                n_hj_n += 1
                n_co_n += 1
            elif is_sandbag_set(ocls, SEAT_UTG, world):
                n_early_s += 1
            else:
                n_early_v += 1
            if ocls is None:
                pass
            elif is_sandbag_set(ocls, SEAT_HJ, world):
                n_hj_s += 1
            else:
                n_hj_v += 1
            if ocls is None:
                pass
            elif is_sandbag_set(ocls, SEAT_CO, world):
                n_co_s += 1
            else:
                n_co_v += 1

    def _p_n_given_passed(n_s: int, n_n: int) -> float:
        return n_n / (n_s + n_n) if (n_s + n_n) else 1.0

    p_n_early = _p_n_given_passed(n_early_s, n_early_n)
    p_n_hj = _p_n_given_passed(n_hj_s, n_hj_n)
    p_n_co = _p_n_given_passed(n_co_s, n_co_n)
    p_no = (p_n_early**5) * p_n_hj * p_n_co
    n_other = n_bn * n_hands_per_bn
    # 7-seat fixture keys treated HJ and CO as one late type (same sandbag-set).
    n_late_s, n_late_v, n_late_n = n_hj_s, n_hj_v, n_hj_n
    p_n_late = p_n_hj
    return {
        "bn_class": bn_class,
        "world": world,
        "n_bn": n_bn,
        "n_hands_per_bn": n_hands_per_bn,
        "n_other_hands": n_other,
        "n_bn_tries": tries,
        "p_bn_has_bug": n_bn_bug / n_bn if n_bn else 0.0,
        "p_sandbag_early": n_early_s / n_other,
        "p_voluntary_early": n_early_v / n_other,
        "p_neither_early": n_early_n / n_other,
        "p_sandbag_hj": n_hj_s / n_other,
        "p_voluntary_hj": n_hj_v / n_other,
        "p_neither_hj": n_hj_n / n_other,
        "p_sandbag_co": n_co_s / n_other,
        "p_voluntary_co": n_co_v / n_other,
        "p_neither_co": n_co_n / n_other,
        "p_sandbag_hj_co": n_late_s / n_other,
        "p_voluntary_hj_co": n_late_v / n_other,
        "p_neither_hj_co": n_late_n / n_other,
        "p_neither_given_passed_early": p_n_early,
        "p_neither_given_passed_hj": p_n_hj,
        "p_neither_given_passed_co": p_n_co,
        "p_neither_given_passed_hj_co": p_n_late,
        "p_no_raise": p_no,
        "p_raise": 1.0 - p_no,
        "seed": seed,
    }


def independent_p_raise_bn_pair_j_blocked(
    *,
    n_bn: int = DEFAULT_REMOVAL_BN_N,
    n_hands_per_bn: int = DEFAULT_REMOVAL_HANDS_PER_BN,
    seed: int = DEFAULT_MC_SEED,
) -> dict[str, Any]:
    """Independent-seat P(raise | passed) with BN pair_J card removal.

    7-seat world. Sample BN pair_J, then sample 5-card hands from the remaining 48.
    Seat type only relabels pair_A (voluntary UTG–LJ, sandbag HJ/CO).
    """
    return independent_p_raise_bn_class_blocked(
        "pair_J",
        world=SANDBAG_WORLD_SEATS_1_7,
        n_bn=n_bn,
        n_hands_per_bn=n_hands_per_bn,
        seed=seed,
    )


@dataclass(frozen=True, slots=True)
class DealMcResult:
    n: int
    seed: int
    n_bn_pair_j: int
    n_conditioned: int
    n_raise: int
    p_raise: float
    p_bn_has_bug: float
    n_tried: int
    sandbag_seats_hist: dict[str, int]
    se_p_raise: float
    bn_class: str = "pair_J"
    world: str = SANDBAG_WORLD_SEATS_1_7

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DealMcResult":
        return cls(
            n=int(d["n"]),
            seed=int(d["seed"]),
            n_bn_pair_j=int(d["n_bn_pair_j"]),
            n_conditioned=int(d["n_conditioned"]),
            n_raise=int(d["n_raise"]),
            p_raise=float(d["p_raise"]),
            p_bn_has_bug=float(d["p_bn_has_bug"]),
            n_tried=int(d["n_tried"]),
            sandbag_seats_hist={str(k): int(v) for k, v in d["sandbag_seats_hist"].items()},
            se_p_raise=float(d["se_p_raise"]),
            bn_class=str(d.get("bn_class", "pair_J")),
            world=str(d.get("world", SANDBAG_WORLD_SEATS_1_7)),
        )


def deal_mc_p_raise_given_passed(
    *,
    n: int = DEFAULT_MC_N,
    seed: int = DEFAULT_MC_SEED,
    bn_class: str = "pair_J",
    world: str = DEFAULT_WORLD,
) -> DealMcResult:
    """Seeded 8-way deal MC: P(≥1 sandbag-set | no voluntary before BN, BN class).

    ``seats_1_7``: condition 1–7 have no voluntary opener.
    ``seats_1_6_only``: condition 1–6 have no voluntary opener **and** CO has
    no open-legal (CO never sandbags). Raise = ≥1 of the world's sandbag seats.
    """
    rng = random.Random(seed)
    deck = list(range(53))
    n_tried = 0
    n_bn_class = 0
    n_cond = 0
    n_raise = 0
    n_bug = 0
    hist: dict[int, int] = {k: 0 for k in range(8)}
    while n_cond < n:
        rng.shuffle(deck)
        n_tried += 1
        bn_ids = deck[35:40]
        bn_cls = _ids_to_cls(bn_ids)
        if bn_cls != bn_class:
            continue
        n_bn_class += 1
        n_sandbag = 0
        rejected = False
        for seat in SEATS_BEFORE_BN:
            start = 5 * (seat - 1)
            cls = _ids_to_cls(deck[start : start + 5])
            if is_voluntary_opener(cls, seat, world):
                rejected = True
                break
            if is_sandbag_set(cls, seat, world):
                n_sandbag += 1
        if rejected:
            continue
        n_cond += 1
        if 52 in bn_ids:
            n_bug += 1
        hist[n_sandbag] = hist.get(n_sandbag, 0) + 1
        if n_sandbag:
            n_raise += 1
    p = n_raise / n_cond if n_cond else 0.0
    se = math.sqrt(p * (1.0 - p) / n_cond) if n_cond else 0.0
    return DealMcResult(
        n=n,
        seed=seed,
        n_bn_pair_j=n_bn_class,
        n_conditioned=n_cond,
        n_raise=n_raise,
        p_raise=p,
        p_bn_has_bug=n_bug / n_cond if n_cond else 0.0,
        n_tried=n_tried,
        sandbag_seats_hist={str(k): hist[k] for k in range(8)},
        se_p_raise=se,
        bn_class=bn_class,
        world=world,
    )


def deal_mc_p_raise_given_passed_bn_pair_j(
    *,
    n: int = DEFAULT_MC_N,
    seed: int = DEFAULT_MC_SEED,
) -> DealMcResult:
    """Seeded 8-way deal MC: P(≥1 sandbag-set | 1–7 no voluntary, BN pair_J)."""
    return deal_mc_p_raise_given_passed(
        n=n, seed=seed, bn_class="pair_J", world=SANDBAG_WORLD_SEATS_1_7
    )


def mix_findings(
    p_raise: float,
    *,
    ev_no_raise: float | None = None,
    p_call: float = P_ANY_2TO1_FOLDED_TO_BN_MC,
    ev_bn_called: float = PAIR_J_D3_EV_BN,
) -> dict[str, Any]:
    leaf = (
        ev_jj_no_sandbag_open(p_call=p_call, ev_bn_called=ev_bn_called)
        if ev_no_raise is None
        else ev_no_raise
    )
    ev = ev_jj_open_100pct_sandbag(p_raise, ev_no_raise=leaf)
    piece_no_raise = (1.0 - p_raise) * leaf
    piece_raise = p_raise * FOLD_JJ_TO_RAISE_EV
    return {
        "p_raise": p_raise,
        "ev_jj_no_sandbag_open": leaf,
        "p_call_reused": p_call,
        "ev_bn_pair_j_d3": ev_bn_called,
        "piece_no_raise": piece_no_raise,
        "piece_raise": piece_raise,
        "ev_open_jj": ev,
        "ev_pass": PASS_EV,
        "open_minus_pass": ev - PASS_EV,
        "opening_jj_is_negative_ev": ev < PASS_EV,
    }


def mix_findings_for_class(
    p_raise: float,
    bn_class: str,
    *,
    p_call: float = P_ANY_2TO1_FOLDED_TO_BN_MC,
    raise_policy: str = "fold",
    se_p_raise: float | None = None,
) -> dict[str, Any]:
    """No-raise leaf from §3.4 locked draw + 6.9% 2:1 mix; raise leaf is −$2 fold.

    ``raise_policy='fold'`` is the Q1/Q2 JJ–KK line. For AA / two pair+ it is a
    **bound** (even folding to the raise) unless a caller-of-raise EV is supplied.
    """
    ev_bn = LOCKED_DRAW_EV_BN[bn_class]
    leaf = locked_leaf_ev(bn_class, p_call=p_call)
    if raise_policy not in {"fold", "fold_bound"}:
        raise ValueError(f"unsupported raise_policy {raise_policy!r}")
    ev = ev_open_fold_to_raise(p_raise, ev_no_raise=leaf)
    break_even = leaf / (leaf - FOLD_JJ_TO_RAISE_EV) if (leaf - FOLD_JJ_TO_RAISE_EV) else 1.0
    out: dict[str, Any] = {
        "bn_class": bn_class,
        "locked_draw_d": LOCKED_DRAW_D[bn_class],
        "ev_bn_locked": ev_bn,
        "p_call_reused": p_call,
        "ev_no_raise_leaf": leaf,
        "p_raise": p_raise,
        "raise_policy": raise_policy,
        "piece_no_raise": (1.0 - p_raise) * leaf,
        "piece_raise": p_raise * FOLD_JJ_TO_RAISE_EV,
        "ev_open": ev,
        "ev_pass": PASS_EV,
        "open_minus_pass": ev - PASS_EV,
        "opening_is_positive_ev": ev > PASS_EV,
        "opening_is_negative_ev": ev < PASS_EV,
        "break_even_p_raise": break_even,
    }
    if se_p_raise is not None:
        out["se_p_raise"] = se_p_raise
    return out


def build_sandbag_v1_payload(
    *,
    n: int = DEFAULT_MC_N,
    seed: int = DEFAULT_MC_SEED,
    n_bn: int = DEFAULT_REMOVAL_BN_N,
    n_hands_per_bn: int = DEFAULT_REMOVAL_HANDS_PER_BN,
    mc: DealMcResult | None = None,
    removal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    counts = _opener_combo_counts()
    two_pair_plus = sum(counts[c] for c in TWO_PAIR_PLUS_CLASSES)
    uncond = independent_p_raise_unconditional()
    if removal is None:
        removal = independent_p_raise_bn_pair_j_blocked(
            n_bn=n_bn, n_hands_per_bn=n_hands_per_bn, seed=seed
        )
    if mc is None:
        mc = deal_mc_p_raise_given_passed_bn_pair_j(n=n, seed=seed)
    ev_leaf_mc = ev_jj_no_sandbag_open(p_call=P_ANY_2TO1_FOLDED_TO_BN_MC)
    ev_leaf_ind = ev_jj_no_sandbag_open(p_call=P_ANY_2TO1_FOLDED_TO_BN_INDEPENDENT)
    mix = mix_findings(mc.p_raise, p_call=P_ANY_2TO1_FOLDED_TO_BN_MC)
    mix_ind_call = mix_findings(mc.p_raise, p_call=P_ANY_2TO1_FOLDED_TO_BN_INDEPENDENT)
    return {
        "meta": {
            "frame": "button_open_sandbag_v1",
            "sandbag_set": {
                "seats_1_7": "two_pair_plus",
                "seats_6_7_also": "pair_A",
                "lj_opens_aces": True,
                "aces_sandbag_seats": sorted(ACES_SANDBAG_SEATS),
            },
            "accounting": {
                "pass": PASS_EV,
                "steal": STEAL_EV,
                "fold_jj_to_raise": FOLD_JJ_TO_RAISE_EV,
                "callers_on_no_raise_leaf": "2:1 call only (do not raise)",
            },
            "no_raise_leaf": {
                "source": "button_open_no_sandbagging JJ open",
                "ev_bn_pair_j_d3": PAIR_J_D3_EV_BN,
                "p_any_2to1_independent": P_ANY_2TO1_FOLDED_TO_BN_INDEPENDENT,
                "p_any_2to1_mc": P_ANY_2TO1_FOLDED_TO_BN_MC,
                "formula": "EV = 2 + p_call * (EV_bn - 4)",
                "ev_open_p_call_mc": ev_leaf_mc,
                "ev_open_p_call_independent": ev_leaf_ind,
            },
            "mc": {"n": n, "seed": seed},
            "removal_planning": {
                "n_bn": n_bn,
                "n_hands_per_bn": n_hands_per_bn,
                "seed": seed,
            },
        },
        "inventory": {
            "total_hands": TOTAL_HANDS,
            "open_legal": sum(counts.values()),
            "two_pair_plus": two_pair_plus,
            "pair_A": counts["pair_A"],
            "pair_J": counts["pair_J"],
            "sandbag_seats_1_5": two_pair_plus,
            "sandbag_seats_6_7": two_pair_plus + counts["pair_A"],
            "voluntary_seats_1_5": voluntary_combo_count(SEAT_UTG),
            "voluntary_seats_6_7": voluntary_combo_count(SEAT_HJ),
            "not_open_legal": not_open_legal_count(),
        },
        "independent_unconditional": uncond,
        "independent_bn_pair_j_blocked": _seven_seat_removal_view(removal),
        "deal_mc": _seven_seat_mc_view(mc),
        "findings": {
            **mix,
            "sensitivity_p_call_independent_6pct": mix_ind_call,
            "independent_unconditional_p_raise": uncond["p_raise"],
            "independent_blocked_p_raise": removal["p_raise"],
        },
    }


_SEVEN_SEAT_REMOVAL_KEYS = (
    "n_bn",
    "n_hands_per_bn",
    "n_other_hands",
    "n_bn_tries",
    "p_bn_has_bug",
    "p_sandbag_early",
    "p_voluntary_early",
    "p_neither_early",
    "p_sandbag_hj_co",
    "p_voluntary_hj_co",
    "p_neither_hj_co",
    "p_neither_given_passed_early",
    "p_neither_given_passed_hj_co",
    "p_no_raise",
    "p_raise",
    "seed",
)


def _seven_seat_removal_view(removal: dict[str, Any]) -> dict[str, Any]:
    """Keep the Agent A fixture key set if the 7-seat JSON is regenerated."""
    return {k: removal[k] for k in _SEVEN_SEAT_REMOVAL_KEYS}


def _seven_seat_mc_view(mc: DealMcResult) -> dict[str, Any]:
    d = mc.as_dict()
    d.pop("bn_class", None)
    d.pop("world", None)
    return d


def class_row_from_mc(
    mc: DealMcResult,
    *,
    p_call: float = P_ANY_2TO1_FOLDED_TO_BN_MC,
    raise_policy: str = "fold",
) -> dict[str, Any]:
    mix = mix_findings_for_class(
        mc.p_raise,
        mc.bn_class,
        p_call=p_call,
        raise_policy=raise_policy,
        se_p_raise=mc.se_p_raise,
    )
    mix["deal_mc"] = mc.as_dict()
    return mix


def walk_open_classes(
    *,
    world: str = SANDBAG_WORLD_SEATS_1_6_ONLY,
    n: int = DEFAULT_MC_N,
    seed: int = DEFAULT_MC_SEED,
    classes: Sequence[str] | None = None,
    continue_past_face_pairs: bool = True,
    mc_by_class: dict[str, DealMcResult] | None = None,
) -> dict[str, Any]:
    """Per-class p_raise + fold-to-raise mix. Stop at the first +EV class.

    JJ–KK use ``raise_policy='fold'``. AA / two pair+ use ``fold_bound``
    (even folding to the raise) — not a raise-tree Nash.
    """
    order = tuple(classes) if classes is not None else (
        FOLD_TO_RAISE_CLASSES + WALK_CLASSES_AFTER_FACE_PAIRS
    )
    cached = dict(mc_by_class or {})
    rows: list[dict[str, Any]] = []
    lowest_plus: str | None = None
    q3_flag = False
    for cls in order:
        if cls in FOLD_TO_RAISE_CLASSES:
            policy = "fold"
        else:
            policy = "fold_bound"
        mc = cached.get(cls)
        if mc is None:
            mc = deal_mc_p_raise_given_passed(
                n=n, seed=seed, bn_class=cls, world=world
            )
            cached[cls] = mc
        row = class_row_from_mc(mc, raise_policy=policy)
        rows.append(row)
        if lowest_plus is None and row["opening_is_positive_ev"]:
            lowest_plus = cls
            if cls in {"pair_A", "two_pair", "trips"}:
                q3_flag = True
            break
        if (
            cls == FOLD_TO_RAISE_CLASSES[-1]
            and lowest_plus is None
            and not continue_past_face_pairs
        ):
            break
    none_of_jj_kk = lowest_plus is None or lowest_plus not in FOLD_TO_RAISE_CLASSES
    if lowest_plus is None and any(r["bn_class"] == "pair_A" for r in rows):
        q3_flag = True
    return {
        "world": world,
        "n": n,
        "seed": seed,
        "rows": rows,
        "lowest_plus_ev_class": lowest_plus,
        "none_of_jj_kk_plus_ev": none_of_jj_kk,
        "floor_is_at_least_aa": bool(none_of_jj_kk),
        "q3_aces_sandbag_pin_should_be_revisited": q3_flag
        or (lowest_plus in {"pair_A", "two_pair", "trips"}),
    }


def build_seats_1_6_only_payload(
    *,
    n: int = DEFAULT_MC_N,
    seed: int = DEFAULT_MC_SEED,
    n_bn: int = DEFAULT_REMOVAL_BN_N,
    n_hands_per_bn: int = DEFAULT_REMOVAL_HANDS_PER_BN,
    walk: bool = False,
    mc: DealMcResult | None = None,
    removal: dict[str, Any] | None = None,
    walk_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Q1 (JJ) and optional Q2 class walk in the 1–6-only sandbag world."""
    world = SANDBAG_WORLD_SEATS_1_6_ONLY
    counts = _opener_combo_counts()
    two_pair_plus = sum(counts[c] for c in TWO_PAIR_PLUS_CLASSES)
    uncond = independent_p_raise_unconditional(world)
    if removal is None:
        removal = independent_p_raise_bn_class_blocked(
            "pair_J",
            world=world,
            n_bn=n_bn,
            n_hands_per_bn=n_hands_per_bn,
            seed=seed,
        )
    if mc is None:
        mc = deal_mc_p_raise_given_passed(
            n=n, seed=seed, bn_class="pair_J", world=world
        )
    q1 = mix_findings_for_class(
        mc.p_raise,
        "pair_J",
        p_call=P_ANY_2TO1_FOLDED_TO_BN_MC,
        raise_policy="fold",
        se_p_raise=mc.se_p_raise,
    )
    q1_ind_call = mix_findings_for_class(
        mc.p_raise,
        "pair_J",
        p_call=P_ANY_2TO1_FOLDED_TO_BN_INDEPENDENT,
        raise_policy="fold",
        se_p_raise=mc.se_p_raise,
    )
    q2: dict[str, Any] | None = walk_result
    if walk and q2 is None:
        q2 = walk_open_classes(
            world=world,
            n=n,
            seed=seed,
            mc_by_class={"pair_J": mc},
        )
    ev_leaf_mc = locked_leaf_ev("pair_J", p_call=P_ANY_2TO1_FOLDED_TO_BN_MC)
    return {
        "meta": {
            "frame": "button_open_sandbag_v1",
            "world": world,
            "sandbag_set": {
                "seats_1_6": "two_pair_plus",
                "seat_6_also": "pair_A",
                "seat_7_co": "never_sandbags_opens_all_legal",
                "lj_opens_aces": True,
                "aces_sandbag_seats": sorted(aces_sandbag_seats(world)),
            },
            "accounting": {
                "pass": PASS_EV,
                "steal": STEAL_EV,
                "fold_jj_qq_kk_to_raise": FOLD_JJ_TO_RAISE_EV,
                "callers_on_no_raise_leaf": "2:1 call only (do not raise)",
                "folded_to_bn": "seats 1–6 no voluntary opener and CO no open-legal",
            },
            "no_raise_leaf": {
                "source": "button_open_no_sandbagging open (seats 1–7 no open-legal)",
                "ev_bn_pair_j_d3": PAIR_J_D3_EV_BN,
                "p_any_2to1_independent": P_ANY_2TO1_FOLDED_TO_BN_INDEPENDENT,
                "p_any_2to1_mc": P_ANY_2TO1_FOLDED_TO_BN_MC,
                "formula": "EV = 2 + p_call * (EV_bn - 4)",
                "ev_open_jj_p_call_mc": ev_leaf_mc,
                "note": "Same 6.9% 2:1 mix as Agent A; do not rebuild Nash.",
            },
            "mc": {"n": n, "seed": seed},
            "removal_planning": {
                "n_bn": n_bn,
                "n_hands_per_bn": n_hands_per_bn,
                "seed": seed,
            },
        },
        "inventory": {
            "total_hands": TOTAL_HANDS,
            "open_legal": sum(counts.values()),
            "two_pair_plus": two_pair_plus,
            "pair_A": counts["pair_A"],
            "pair_J": counts["pair_J"],
            "sandbag_seats_1_5": two_pair_plus,
            "sandbag_seat_6_hj": two_pair_plus + counts["pair_A"],
            "sandbag_seat_7_co": 0,
            "voluntary_seats_1_5": voluntary_combo_count(SEAT_UTG, world),
            "voluntary_seat_6_hj": voluntary_combo_count(SEAT_HJ, world),
            "voluntary_seat_7_co": voluntary_combo_count(SEAT_CO, world),
            "not_open_legal": not_open_legal_count(),
        },
        "independent_unconditional": uncond,
        "independent_bn_pair_j_blocked": removal,
        "deal_mc_pair_j": mc.as_dict(),
        "q1": {
            **q1,
            "sensitivity_p_call_independent_6pct": q1_ind_call,
            "independent_unconditional_p_raise": uncond["p_raise"],
            "independent_blocked_p_raise": removal["p_raise"],
            "agent_a_seven_seat_p_raise": 0.573025,
        },
        "q2": q2,
    }


def default_fixture_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "validation"
        / "sandbag_v1.json"
    )


def default_seats_1_6_fixture_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "validation"
        / "sandbag_v1_seats_1_6_only.json"
    )


def write_sandbag_v1_fixture(
    path: Path | None = None,
    *,
    payload: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Path:
    path = path or default_fixture_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = payload if payload is not None else build_sandbag_v1_payload(**kwargs)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def write_seats_1_6_only_fixture(
    path: Path | None = None,
    *,
    payload: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Path:
    path = path or default_seats_1_6_fixture_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = payload if payload is not None else build_seats_1_6_only_payload(**kwargs)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def load_sandbag_v1(path: Path | None = None) -> dict[str, Any]:
    path = path or default_fixture_path()
    return json.loads(path.read_text(encoding="utf-8"))


def load_seats_1_6_only(path: Path | None = None) -> dict[str, Any]:
    path = path or default_seats_1_6_fixture_path()
    return json.loads(path.read_text(encoding="utf-8"))


def _print_q1(payload: dict[str, Any]) -> None:
    q1 = payload["q1"]
    mc = payload["deal_mc_pair_j"]
    print(
        f"world={payload['meta']['world']} "
        f"independent unconditional p_raise = "
        f"{payload['independent_unconditional']['p_raise']:.6f}"
    )
    print(
        f"independent BN pair_J blocked p_raise = "
        f"{payload['independent_bn_pair_j_blocked']['p_raise']:.6f}"
    )
    print(
        f"deal MC n={mc['n']} seed={mc['seed']} p_raise = {mc['p_raise']:.6f} "
        f"(se {mc['se_p_raise']:.6f})"
    )
    print(
        f"reused no-raise JJ EV = {q1['ev_no_raise_leaf']:.6f} "
        f"(p_call={q1['p_call_reused']}, EV_bn d={q1['locked_draw_d']}="
        f"{q1['ev_bn_locked']})"
    )
    print(
        f"EV(open JJ) = {q1['ev_open']:.6f} "
        f"= (1-p)*leaf {q1['piece_no_raise']:.6f} + p*(-2) {q1['piece_raise']:.6f}"
    )
    sign = "+EV" if q1["opening_is_positive_ev"] else "−EV"
    print(f"opening JJ is {sign} vs pass")


def _print_q2(q2: dict[str, Any]) -> None:
    print("--- Q2 walk ---")
    for row in q2["rows"]:
        sign = "+" if row["opening_is_positive_ev"] else "−"
        print(
            f"{row['bn_class']} policy={row['raise_policy']} "
            f"p_raise={row['p_raise']:.6f} (se {row.get('se_p_raise', float('nan')):.6f}) "
            f"leaf={row['ev_no_raise_leaf']:.6f} EV(open)={row['ev_open']:.6f} ({sign}EV)"
        )
    floor = q2["lowest_plus_ev_class"]
    if floor is None:
        print("lowest +EV class: none signed (floor is at least AA / two pair+)")
    else:
        print(f"lowest +EV class: {floor}")
    if q2["q3_aces_sandbag_pin_should_be_revisited"]:
        print(
            "Q3 flag: v1 aces-sandbag pin should be revisited "
            "(do not iterate the sandbag set in this PR)"
        )


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(
        description="Sandbag-set v1: P(raise | passed, BN class) and open EV"
    )
    p.add_argument("-o", "--output", type=Path, default=None)
    p.add_argument("--n", type=int, default=DEFAULT_MC_N)
    p.add_argument("--seed", type=int, default=DEFAULT_MC_SEED)
    p.add_argument("--n-bn", type=int, default=DEFAULT_REMOVAL_BN_N)
    p.add_argument("--n-hands-per-bn", type=int, default=DEFAULT_REMOVAL_HANDS_PER_BN)
    p.add_argument("--write-fixture", action="store_true")
    p.add_argument(
        "--world",
        choices=(SANDBAG_WORLD_SEATS_1_7, SANDBAG_WORLD_SEATS_1_6_ONLY),
        default=SANDBAG_WORLD_SEATS_1_7,
    )
    p.add_argument(
        "--walk",
        action="store_true",
        help="Q2: walk BN classes in seats_1_6_only (implies that world)",
    )
    args = p.parse_args()
    if args.walk:
        args.world = SANDBAG_WORLD_SEATS_1_6_ONLY
    if args.world == SANDBAG_WORLD_SEATS_1_6_ONLY:
        payload = build_seats_1_6_only_payload(
            n=args.n,
            seed=args.seed,
            n_bn=args.n_bn,
            n_hands_per_bn=args.n_hands_per_bn,
            walk=args.walk,
        )
        if args.write_fixture or args.output is not None:
            path = write_seats_1_6_only_fixture(args.output, payload=payload)
            print(f"Wrote {path}")
        _print_q1(payload)
        if payload.get("q2"):
            _print_q2(payload["q2"])
        return
    payload = build_sandbag_v1_payload(
        n=args.n,
        seed=args.seed,
        n_bn=args.n_bn,
        n_hands_per_bn=args.n_hands_per_bn,
    )
    if args.write_fixture or args.output is not None:
        path = write_sandbag_v1_fixture(args.output, payload=payload)
        print(f"Wrote {path}")
    f = payload["findings"]
    mc = payload["deal_mc"]
    print(
        f"independent unconditional p_raise = "
        f"{payload['independent_unconditional']['p_raise']:.6f}"
    )
    print(
        f"independent BN pair_J blocked p_raise = "
        f"{payload['independent_bn_pair_j_blocked']['p_raise']:.6f}"
    )
    print(
        f"deal MC n={mc['n']} seed={mc['seed']} p_raise = {mc['p_raise']:.6f} "
        f"(se {mc['se_p_raise']:.6f})"
    )
    print(
        f"reused no-raise JJ EV = {f['ev_jj_no_sandbag_open']:.6f} "
        f"(p_call={f['p_call_reused']}, EV_bn d=3={f['ev_bn_pair_j_d3']})"
    )
    print(
        f"EV(open JJ) = {f['ev_open_jj']:.6f} "
        f"= (1-p)*leaf {f['piece_no_raise']:.6f} + p*(-2) {f['piece_raise']:.6f}"
    )
    print(f"opening JJ is −EV vs pass: {f['opening_jj_is_negative_ev']}")


if __name__ == "__main__":
    main()
