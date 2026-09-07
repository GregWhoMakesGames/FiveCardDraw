"""HJ slowplay mix vs opening the v1 sandbag-set (CO never sandbags).

Frame: ``hijack_slowplay``. Parent pins:

- CO never-slowplay: ``cutoff_open_no_sandbagging`` (quoted; this module does
  not re-solve the CO tree).
- BN 1–6-only sandbag: ``sandbag_v1.py`` world ``seats_1_6_only``.

Laboratory (locked): CO opens every legal; BN opens every legal (temporary
hypothesis); HJ sandbag-set = two pair+ and AA; seats 1–5 still 100% sandbag
two pair+ (LJ still opens AA) and raise an HJ open.

HJ's choice after 1–5 passed, holding a sandbag-set hand:

- Open fraction ``q = 1-r``
- Slowplay fraction ``r``: pass, then raise if CO or BN opens

v1 is position-by-position approximate GTO, not full 8-way Nash. Street EVs
reuse locked §3.4 / CO-vs-BN-legal non-bluff leaves and a raise-checkdown
bound. Do not rebuild post-draw Nash / Ring 1 / Stage C.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from fivecarddraw.cards import card_from_id
from fivecarddraw.hand_rank import evaluate_hand
from fivecarddraw.validation.cascade_odds import CALL_2TO1_COMBOS, TOTAL_HANDS
from fivecarddraw.validation.postdraw_draw_mixes import opener_draw_plan_for_action
from fivecarddraw.validation.postdraw_nonbluff_ev import LOCKED_BN_DRAW
from fivecarddraw.validation.sandbag_v1 import (
    DEFAULT_MC_SEED,
    FOLD_JJ_TO_RAISE_EV,
    LOCKED_DRAW_EV_BN,
    PASS_EV,
    SANDBAG_WORLD_SEATS_1_6_ONLY,
    SEAT_HJ,
    SEAT_LJ,
    STEAL_EV,
    independent_p_raise_bn_class_blocked,
    independent_p_raise_unconditional,
    is_two_pair_plus,
    not_open_legal_count,
    sandbag_set_combo_count,
)
from fivecarddraw.validation.showdown_matrix import (
    STRAIGHT_PLUS_CLASSES,
    TRIPS_CLASSES,
    TWO_PAIR_CLASSES,
    classify_opener,
    load_showdown_matrix,
)

DEFAULT_SEED = DEFAULT_MC_SEED  # 20260907
DEFAULT_N_EQUITY = 2_000
DEFAULT_N_REMOVAL_BN = 1_000
DEFAULT_N_HANDS_PER_BN = 40
INDIFFERENCE_NICKEL = 0.05
BN_BREAK_EVEN_P_RAISE = 0.4918969633094986  # 1–6-only JJ leaf / (leaf+2)
R_TOT_OPEN_EVERYTHING_LINE = 0.98
# User-facing independent planning pins (1–6-only writeup).
P_J_PLAN = 0.7760
P_S_15_PLAN = 0.0821
P_S_HJ_PLAN = 0.1302

FOCUS_CLASSES = (
    "pair_A",
    "two_pair",
    "two_pair_aces_up",
    "trips",
    "straight_plus",
)

# Quoted from cursor/cutoff-open-no-sandbagging-6cf1 fixture / frame writeup.
# Do not re-run the CO tree here.
CO_NEVER_SLOWPLAY_PIN: dict[str, Any] = {
    "frame": "cutoff_open_no_sandbagging",
    "source_branch": "cursor/cutoff-open-no-sandbagging-6cf1",
    "source_commit": "ee78fc7",
    "fixture": "tests/fixtures/validation/cutoff_open_summary.json",
    "doc": "docs/research/cutoff_open_no_sandbagging.md",
    "laboratory": (
        "Seats 1–6 unable (0% sandbag). CO legal. BN opens every legal if CO "
        "passes; calls every legal if CO opens."
    ),
    "q1_open_every_legal": True,
    "q1_jj_ev_open": 1.43502,
    "q1_jj_ev_pass": 0.0,
    "q2_co_should_sandbag": False,
    "q2_sandbag_classes": [],
    "pair_A_ev_open": 1.66791,
    "pair_A_best_pass": 0.27355,
    "pair_A_open_minus_best_pass": 1.39436,
    "two_pair_ev_open": 1.78692,
    "two_pair_best_pass": 0.36403,
    "two_pair_open_minus_best_pass": 1.42289,
    "docs_round_jj_open": 1.44,
    "docs_round_open_minus_best_pass_lo": 1.39,
    "docs_round_open_minus_best_pass_hi": 1.42,
    "confirmed_never_slowplay": True,
}

# Honest non-bluff HU street vs BN's open-legal range (CO lab, n_hu=4k).
CO_VS_BN_LEGAL_STREET: dict[str, dict[str, float]] = {
    "pair_A": {
        "ev_street": 2.5255,
        "ev_checkdown": 3.2445,
        "p_win": 0.54075,
        "p_tie": 0.0,
        "n": 4000.0,
    },
    "two_pair": {
        "ev_street": 3.3565,
        "ev_checkdown": 3.3135,
        "p_win": 0.55225,
        "p_tie": 0.0,
        "n": 4000.0,
    },
}

# §3.4 locked-draw EV vs all 2:1 (postdraw_nonbluff_ev_summary.json).
SECTION_34_EV: dict[str, float] = {
    "pair_A": LOCKED_DRAW_EV_BN["pair_A"],
    "two_pair": LOCKED_DRAW_EV_BN["two_pair"],
    "two_pair_aces_up": 2.077,
    "trips": LOCKED_DRAW_EV_BN["trips"],
    "straight_plus": LOCKED_DRAW_EV_BN["trips"],  # lower bound (trips d=2)
}

TRIPS_PLUS_CLASSES = frozenset(TRIPS_CLASSES + STRAIGHT_PLUS_CLASSES)


def _opener_counts() -> dict[str, int]:
    return dict(load_showdown_matrix()["opener_combo_counts"])


def inventory() -> dict[str, Any]:
    counts = _opener_counts()
    two_pair_plus = sandbag_set_combo_count(SEAT_LJ, SANDBAG_WORLD_SEATS_1_6_ONLY)
    hj = sandbag_set_combo_count(SEAT_HJ, SANDBAG_WORLD_SEATS_1_6_ONLY)
    trips = sum(counts[c] for c in TRIPS_CLASSES)
    straight_plus = sum(counts[c] for c in STRAIGHT_PLUS_CLASSES)
    not_legal = not_open_legal_count()
    return {
        "total_hands": TOTAL_HANDS,
        "open_legal": sum(counts.values()),
        "not_open_legal": not_legal,
        "two_to_one": CALL_2TO1_COMBOS,
        "two_pair_plus": two_pair_plus,
        "pair_A": counts["pair_A"],
        "two_pair": counts["two_pair"],
        "two_pair_aces_up": counts["two_pair_aces_up"],
        "trips": counts["trips"],
        "trips_all": trips,
        "straight_plus": straight_plus,
        "sandbag_seats_1_5": two_pair_plus,
        "sandbag_seat_6_hj": hj,
        "p_j": not_legal / TOTAL_HANDS,
        "p_s_1_5": two_pair_plus / TOTAL_HANDS,
        "p_s_hj": hj / TOTAL_HANDS,
        "p_open": sum(counts.values()) / TOTAL_HANDS,
        "p_2to1": CALL_2TO1_COMBOS / TOTAL_HANDS,
        "hj_sandbag_mass": {
            "pair_A": counts["pair_A"] / hj,
            "two_pair": counts["two_pair"] / hj,
            "two_pair_aces_up": counts["two_pair_aces_up"] / hj,
            "trips": counts["trips"] / hj,
            "trips_all": trips / hj,
            "straight_plus": straight_plus / hj,
        },
    }


def independent_p_raise_rates(
    r_1_5: float,
    r_hj: float,
    *,
    p_j: float | None = None,
    p_s_1_5: float | None = None,
    p_s_hj: float | None = None,
) -> dict[str, float]:
    """Independent-seat P(raise vs BN) with per-block sandbag rates.

    ``p_raise = 1 - (p_j / (p_j + r_1_5 p_s^{1-5}))^5 * (p_j / (p_j + r_HJ p_s^{HJ}))``
    """
    inv = inventory() if p_j is None else None
    p_j = inv["p_j"] if p_j is None else p_j
    p_s_1_5 = inv["p_s_1_5"] if p_s_1_5 is None else p_s_1_5
    p_s_hj = inv["p_s_hj"] if p_s_hj is None else p_s_hj
    p_no_15 = (p_j / (p_j + r_1_5 * p_s_1_5)) ** 5
    p_no_hj = p_j / (p_j + r_hj * p_s_hj)
    p_no = p_no_15 * p_no_hj
    return {
        "r_1_5": r_1_5,
        "r_hj": r_hj,
        "p_j": p_j,
        "p_s_1_5": p_s_1_5,
        "p_s_hj": p_s_hj,
        "p_no_raise_1_5": p_no_15,
        "p_no_raise_hj": p_no_hj,
        "p_no_raise": p_no,
        "p_raise": 1.0 - p_no,
    }


def mass_weighted_r_tot(
    r_1_5: float,
    r_hj: float,
    *,
    p_s_1_5: float | None = None,
    p_s_hj: float | None = None,
) -> dict[str, float]:
    """Mass-weighted slowplay rate of seats 1–6 vs BN (CO never sandbags)."""
    inv = inventory() if p_s_1_5 is None else None
    p_s_1_5 = inv["p_s_1_5"] if p_s_1_5 is None else p_s_1_5
    p_s_hj = inv["p_s_hj"] if p_s_hj is None else p_s_hj
    w_15 = 5.0 * p_s_1_5
    w_hj = p_s_hj
    denom = w_15 + w_hj
    r_tot = (w_15 * r_1_5 + w_hj * r_hj) / denom if denom else 0.0
    return {
        "r_1_5": r_1_5,
        "r_hj": r_hj,
        "weight_1_5": w_15,
        "weight_hj": w_hj,
        "r_tot": r_tot,
        "r_hj_for_r_tot_le_0_98": (0.98 * denom - w_15) / w_hj if w_hj else 0.0,
        "drops_total_slowplay_by_at_least_2pct": r_tot <= R_TOT_OPEN_EVERYTHING_LINE + 1e-15,
    }


def planning_p_raise_rates(r_1_5: float, r_hj: float) -> dict[str, float]:
    """Same formula with the 1–6-only writeup's rounded pins."""
    return independent_p_raise_rates(
        r_1_5,
        r_hj,
        p_j=P_J_PLAN,
        p_s_1_5=P_S_15_PLAN,
        p_s_hj=P_S_HJ_PLAN,
    )


def planning_r_tot(r_1_5: float, r_hj: float) -> dict[str, float]:
    return mass_weighted_r_tot(
        r_1_5, r_hj, p_s_1_5=P_S_15_PLAN, p_s_hj=P_S_HJ_PLAN
    )


def world0_open_leaves(
    *,
    p_not_legal: float,
    p_2to1: float,
) -> dict[str, float]:
    """HJ-opens leaves when 1–5 have no open-legal (CO-pin world).

    CO/BN call every legal (v1). 2:1 call only. Steal if CO and BN are not
    legal and nobody among 1–5/CO/BN is 2:1.
    """
    p_neither = p_not_legal - p_2to1
    if p_not_legal <= 0.0 or p_neither < 0.0:
        raise ValueError("illegal junk / 2:1 split")
    p_both_not_legal = p_not_legal**2
    p_neither_given_not = p_neither / p_not_legal
    p_no_2to1_seven = p_neither_given_not**7
    p_steal = p_neither**2 * p_neither_given_not**5
    p_vs_2to1 = p_both_not_legal - p_steal
    p_vs_legal = 1.0 - p_both_not_legal
    return {
        "p_steal": p_steal,
        "p_vs_2to1": p_vs_2to1,
        "p_vs_legal": p_vs_legal,
        "p_both_not_legal": p_both_not_legal,
        "p_no_2to1_given_both_not_legal": p_no_2to1_seven,
        "p_behind_opens": p_vs_legal,
    }


def p_raise_1_5_given_passed(p_j: float, p_s_1_5: float, r_1_5: float = 1.0) -> float:
    return 1.0 - (p_j / (p_j + r_1_5 * p_s_1_5)) ** 5


def mix_open_ev(
    *,
    p_steal: float,
    p_vs_2to1: float,
    p_vs_legal: float,
    ev_street_2to1: float,
    ev_street_legal: float,
) -> float:
    """Pass = 0; steal = +$2; called street net = EV_street − $2."""
    return (
        p_steal * STEAL_EV
        + p_vs_2to1 * (ev_street_2to1 - 2.0)
        + p_vs_legal * (ev_street_legal - 2.0)
    )


def mix_open_hyp_ev(p_raise_15: float, ev_world0: float, ev_vs_raise: float) -> float:
    """Hypothesis: 1–5 raise sandbag-set; mix no-raise leaf with vs-raise leaf."""
    return (1.0 - p_raise_15) * ev_world0 + p_raise_15 * ev_vs_raise


def raise_checkdown_ev(*, p_win: float, p_tie: float = 0.0, invested: float = 4.0) -> float:
    """Checkdown on a $10 pot (raiser/caller each put $4 pre-draw)."""
    return (10.0 * p_win + 5.0 * p_tie) - invested


def mix_slowplay_ev(p_behind_opens: float, ev_raise_given_open: float) -> float:
    """Pass: pot never opened → 0; if CO or BN opens, take the raise leaf."""
    return p_behind_opens * ev_raise_given_open


def _class_predicate(hj_class: str) -> Callable[[str | None], bool]:
    if hj_class == "straight_plus":
        return lambda cls: cls in STRAIGHT_PLUS_CLASSES
    if hj_class == "trips_plus":
        return lambda cls: cls in TRIPS_PLUS_CLASSES
    return lambda cls: cls == hj_class


def _villain_two_pair_plus(cls: str | None) -> bool:
    return is_two_pair_plus(cls)


def _villain_open_legal(cls: str | None) -> bool:
    return cls is not None


def _draw_locked(
    ids: Sequence[int], cls: str, rem: list[int], rng: random.Random
) -> tuple:
    cards = tuple(card_from_id(i) for i in ids)
    n = LOCKED_BN_DRAW.n_draw_for(cls)
    plan = opener_draw_plan_for_action(cards, cls, n)
    if plan.n_draw <= 0:
        return plan.keep
    if len(rem) < plan.n_draw:
        return plan.keep
    drawn_ids = [rem.pop() for _ in range(plan.n_draw)]
    return tuple(plan.keep) + tuple(card_from_id(i) for i in drawn_ids)


def equity_vs_range(
    hj_class: str,
    vill_pred: Callable[[str | None], bool],
    *,
    n: int = DEFAULT_N_EQUITY,
    seed: int = DEFAULT_SEED,
    vill_draw_class: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Locked-draw showdown equity: HJ ``hj_class`` vs a villain predicate.

    Cheap MC — not a betting street. Used for raise-checkdown / continue bounds.
    """
    rng = random.Random(seed)
    deck = list(range(53))
    hj_ok = _class_predicate(hj_class)
    n_ok = 0
    n_win = 0
    n_tie = 0
    n_tried = 0
    vill_tries_per_hj = 24
    while n_ok < n and n_tried < n * 800:
        n_tried += 1
        rng.shuffle(deck)
        hj_ids = tuple(sorted(deck[:5]))
        hj_cls = classify_opener(tuple(card_from_id(i) for i in hj_ids))
        if not hj_ok(hj_cls):
            continue
        rest = deck[5:]
        for _ in range(vill_tries_per_hj):
            if n_ok >= n:
                break
            rng.shuffle(rest)
            vill_ids = tuple(sorted(rest[:5]))
            vill_cls = classify_opener(tuple(card_from_id(i) for i in vill_ids))
            if not vill_pred(vill_cls):
                continue
            rem = list(rest[5:])
            rng.shuffle(rem)
            hj_final = _draw_locked(hj_ids, hj_cls or hj_class, rem, rng)
            v_draw_cls = vill_cls if vill_draw_class is None else vill_draw_class(vill_cls)
            vill_final = _draw_locked(vill_ids, v_draw_cls, rem, rng)
            hv = evaluate_hand(hj_final)
            vv = evaluate_hand(vill_final)
            n_ok += 1
            if hv > vv:
                n_win += 1
            elif hv == vv:
                n_tie += 1
    p_win = n_win / n_ok if n_ok else 0.0
    p_tie = n_tie / n_ok if n_ok else 0.0
    se = math.sqrt(p_win * (1.0 - p_win) / n_ok) if n_ok else 0.0
    return {
        "hj_class": hj_class,
        "n": n_ok,
        "seed": seed,
        "n_tried": n_tried,
        "p_win": p_win,
        "p_tie": p_tie,
        "p_lose": 1.0 - p_win - p_tie if n_ok else 0.0,
        "se_p_win": se,
        "ev_raise_checkdown": raise_checkdown_ev(p_win=p_win, p_tie=p_tie),
        "ev_fold": FOLD_JJ_TO_RAISE_EV,
    }


def street_vs_legal(hj_class: str, p_win_vs_legal: float | None) -> dict[str, float]:
    """EV_street when CO/BN call an HJ open.

    pair_A / two_pair reuse the CO lab honest non-bluff HU. Stronger classes
    use two_pair's honest street as a *lower* bound unless a showdown p_win
    is supplied (then $6 checkdown = 6 p_win, which for two pair sits on
    the honest cell).
    """
    if hj_class in CO_VS_BN_LEGAL_STREET:
        row = CO_VS_BN_LEGAL_STREET[hj_class]
        return {
            "ev_street": row["ev_street"],
            "p_win": row["p_win"],
            "p_tie": row["p_tie"],
            "source": "cutoff_open_vs_bn_legal_honest",
        }
    proxy = CO_VS_BN_LEGAL_STREET["two_pair"]
    if p_win_vs_legal is None:
        return {
            "ev_street": proxy["ev_street"],
            "p_win": proxy["p_win"],
            "p_tie": proxy["p_tie"],
            "source": "two_pair_honest_lower_bound",
        }
    return {
        "ev_street": 6.0 * p_win_vs_legal,
        "p_win": p_win_vs_legal,
        "p_tie": 0.0,
        "source": "six_pot_checkdown_from_equity_mc",
    }


def _best_vs_raise(eq_tp: dict[str, Any]) -> dict[str, Any]:
    fold_ev = FOLD_JJ_TO_RAISE_EV
    call_ev = float(eq_tp["ev_raise_checkdown"])
    if call_ev >= fold_ev:
        return {
            "policy": "call_checkdown",
            "ev": call_ev,
            "p_win_vs_two_pair_plus": eq_tp["p_win"],
            "p_tie_vs_two_pair_plus": eq_tp["p_tie"],
        }
    return {
        "policy": "fold",
        "ev": fold_ev,
        "p_win_vs_two_pair_plus": eq_tp["p_win"],
        "p_tie_vs_two_pair_plus": eq_tp["p_tie"],
    }


def _r_from_ev(ev_open: float, ev_slow: float) -> tuple[float, str]:
    gap = ev_open - ev_slow
    if abs(gap) <= INDIFFERENCE_NICKEL:
        return 0.5, "mix_indifference_nickel"
    if ev_slow >= ev_open:
        return 1.0, "slowplay"
    return 0.0, "open"


@dataclass(slots=True)
class ClassMix:
    hj_class: str
    p_raise_15: float
    p_behind_opens: float
    p_steal: float
    p_vs_2to1: float
    p_vs_legal: float
    ev_street_2to1: float
    ev_street_legal: float
    ev_open_world0: float
    ev_vs_raise: float
    vs_raise_policy: str
    ev_open_hyp: float
    ev_slowplay: float
    ev_open_minus_slowplay: float
    r_star: float
    action: str
    p_win_vs_legal: float
    p_win_vs_two_pair_plus: float

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for key in (
            "p_raise_15",
            "p_behind_opens",
            "p_steal",
            "p_vs_2to1",
            "p_vs_legal",
            "ev_street_2to1",
            "ev_street_legal",
            "ev_open_world0",
            "ev_vs_raise",
            "ev_open_hyp",
            "ev_slowplay",
            "ev_open_minus_slowplay",
            "p_win_vs_legal",
            "p_win_vs_two_pair_plus",
        ):
            d[key] = round(float(d[key]), 6)
        d["r_star"] = round(float(d["r_star"]), 4)
        return d


def evaluate_class(
    hj_class: str,
    *,
    eq_legal: dict[str, Any],
    eq_tp: dict[str, Any],
    p_not_legal: float,
    p_2to1: float,
    p_raise_15: float,
    p_behind_opens: float | None = None,
) -> ClassMix:
    leaves = world0_open_leaves(p_not_legal=p_not_legal, p_2to1=p_2to1)
    if p_behind_opens is None:
        p_behind_opens = leaves["p_behind_opens"]
    legal_street = street_vs_legal(hj_class, eq_legal.get("p_win"))
    ev_34 = SECTION_34_EV[hj_class]
    ev_world0 = mix_open_ev(
        p_steal=leaves["p_steal"],
        p_vs_2to1=leaves["p_vs_2to1"],
        p_vs_legal=leaves["p_vs_legal"],
        ev_street_2to1=ev_34,
        ev_street_legal=legal_street["ev_street"],
    )
    vs_raise = _best_vs_raise(eq_tp)
    ev_hyp = mix_open_hyp_ev(p_raise_15, ev_world0, vs_raise["ev"])
    if hj_class in CO_VS_BN_LEGAL_STREET:
        p_win_slow = CO_VS_BN_LEGAL_STREET[hj_class]["p_win"]
        p_tie_slow = CO_VS_BN_LEGAL_STREET[hj_class]["p_tie"]
    else:
        p_win_slow = float(eq_legal["p_win"])
        p_tie_slow = float(eq_legal.get("p_tie", 0.0))
    ev_raise_given = raise_checkdown_ev(p_win=p_win_slow, p_tie=p_tie_slow)
    ev_slow = mix_slowplay_ev(p_behind_opens, ev_raise_given)
    r_star, action = _r_from_ev(ev_hyp, ev_slow)
    return ClassMix(
        hj_class=hj_class,
        p_raise_15=p_raise_15,
        p_behind_opens=p_behind_opens,
        p_steal=leaves["p_steal"],
        p_vs_2to1=leaves["p_vs_2to1"],
        p_vs_legal=leaves["p_vs_legal"],
        ev_street_2to1=ev_34,
        ev_street_legal=legal_street["ev_street"],
        ev_open_world0=ev_world0,
        ev_vs_raise=vs_raise["ev"],
        vs_raise_policy=vs_raise["policy"],
        ev_open_hyp=ev_hyp,
        ev_slowplay=ev_slow,
        ev_open_minus_slowplay=ev_hyp - ev_slow,
        r_star=r_star,
        action=action,
        p_win_vs_legal=p_win_slow,
        p_win_vs_two_pair_plus=float(eq_tp["p_win"]),
    )


def _removal_for_class(
    hj_class: str,
    *,
    n_bn: int,
    n_hands: int,
    seed: int,
) -> dict[str, Any] | None:
    """Card-removal frequencies with this class blocked (reuse sandbag_v1)."""
    if hj_class == "straight_plus":
        return None
    probe = "trips" if hj_class == "trips" else hj_class
    return independent_p_raise_bn_class_blocked(
        probe,
        world=SANDBAG_WORLD_SEATS_1_6_ONLY,
        n_bn=n_bn,
        n_hands_per_bn=n_hands,
        seed=seed,
    )


def _probs_from_removal(
    removal: dict[str, Any] | None,
    inv: dict[str, Any],
) -> dict[str, float]:
    if removal is None:
        p_j = inv["p_j"]
        p_s = inv["p_s_1_5"]
        return {
            "p_not_legal": p_j,
            "p_2to1": inv["p_2to1"],
            "p_raise_15": p_raise_1_5_given_passed(p_j, p_s, 1.0),
            "p_behind_opens": 1.0 - p_j**2,
            "source": "independent_unconditional",
        }
    p_legal = float(removal["p_voluntary_co"])
    p_not = 1.0 - p_legal
    p_n_early = float(removal["p_neither_given_passed_early"])
    return {
        "p_not_legal": p_not,
        "p_2to1": inv["p_2to1"],
        "p_raise_15": 1.0 - p_n_early**5,
        "p_behind_opens": 1.0 - p_not**2,
        "source": "independent_class_blocked",
        "p_legal_one_seat": p_legal,
        "p_neither_given_passed_early": p_n_early,
    }


def _mass_for_r(inv: dict[str, Any]) -> dict[str, float]:
    """HJ sandbag-set masses that partition the set (trips row = all trips)."""
    hj = inv["sandbag_seat_6_hj"]
    return {
        "pair_A": inv["pair_A"] / hj,
        "two_pair": inv["two_pair"] / hj,
        "two_pair_aces_up": inv["two_pair_aces_up"] / hj,
        "trips": inv["trips_all"] / hj,
        "straight_plus": inv["straight_plus"] / hj,
    }


def _hj_slowplay_bucket(cls: str | None) -> str | None:
    if cls == "pair_A":
        return "pair_A"
    if cls in TWO_PAIR_CLASSES:
        return cls
    if cls in TRIPS_CLASSES:
        return "trips"
    if cls in STRAIGHT_PLUS_CLASSES:
        return "straight_plus"
    return None


def deal_mc_p_raise_hj_mix(
    r_by_class: dict[str, float],
    *,
    n: int = 40_000,
    seed: int = DEFAULT_SEED,
    bn_class: str = "pair_J",
) -> dict[str, Any]:
    """8-way deal MC: P(raise vs BN) with CO never sandbagging and mixed HJ r.

    Condition: 1–5 no voluntary opener, HJ no voluntary opener, CO no
    open-legal, BN ``bn_class``. Raise if ≥1 of 1–5 is two pair+ or HJ
    slowplays its sandbag-set hand (Bernoulli ``r`` by bucket).
    """
    from fivecarddraw.validation.sandbag_v1 import (
        SEATS_BEFORE_BN,
        is_sandbag_set,
        is_voluntary_opener,
    )

    rng = random.Random(seed)
    deck = list(range(53))
    world = SANDBAG_WORLD_SEATS_1_6_ONLY
    n_tried = 0
    n_bn = 0
    n_cond = 0
    n_raise = 0
    hist = {k: 0 for k in range(8)}
    while n_cond < n:
        rng.shuffle(deck)
        n_tried += 1
        bn_ids = deck[35:40]
        bn_cls = classify_opener(tuple(card_from_id(i) for i in bn_ids))
        if bn_cls != bn_class:
            continue
        n_bn += 1
        rejected = False
        n_sandbag = 0
        for seat in SEATS_BEFORE_BN:
            start = 5 * (seat - 1)
            cls = classify_opener(
                tuple(card_from_id(i) for i in deck[start : start + 5])
            )
            if is_voluntary_opener(cls, seat, world):
                rejected = True
                break
            if seat == SEAT_HJ:
                bucket = _hj_slowplay_bucket(cls)
                r = r_by_class.get(bucket or "", 0.0) if bucket else 0.0
                if cls is not None and is_sandbag_set(cls, seat, world):
                    if r >= 1.0 - 1e-12 or (0.0 < r < 1.0 and rng.random() < r):
                        n_sandbag += 1
            elif is_sandbag_set(cls, seat, world):
                n_sandbag += 1
        if rejected:
            continue
        n_cond += 1
        hist[n_sandbag] = hist.get(n_sandbag, 0) + 1
        if n_sandbag:
            n_raise += 1
    p = n_raise / n_cond if n_cond else 0.0
    se = math.sqrt(p * (1.0 - p) / n_cond) if n_cond else 0.0
    return {
        "n": n,
        "seed": seed,
        "bn_class": bn_class,
        "n_bn_class": n_bn,
        "n_conditioned": n_cond,
        "n_raise": n_raise,
        "p_raise": p,
        "se_p_raise": se,
        "n_tried": n_tried,
        "sandbag_seats_hist": {str(k): hist[k] for k in range(8)},
        "r_by_class": dict(r_by_class),
    }


def derive_answers(
    rows: list[ClassMix],
    inv: dict[str, Any],
    *,
    deal_mc: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mass = _mass_for_r(inv)
    by = {r.hj_class: r for r in rows}
    # ``trips`` row stands in for trips_K / trips_A too.
    r_hj = 0.0
    used = 0.0
    r_by_class: dict[str, float] = {}
    for cls, w in mass.items():
        row = by.get(cls)
        if row is None:
            continue
        r_hj += w * row.r_star
        used += w
        r_by_class[cls] = row.r_star
    r_hj = r_hj / used if used else 1.0
    rt = planning_r_tot(1.0, r_hj)
    pr = planning_p_raise_rates(1.0, r_hj)
    pr_100 = planning_p_raise_rates(1.0, 1.0)
    r_all_open = all(r.r_star <= 0.0 + 1e-12 for r in rows)
    r_all_slow = all(r.r_star >= 1.0 - 1e-12 for r in rows)
    drop = 1.0 - rt["r_tot"]
    p_mc = None if deal_mc is None else float(deal_mc["p_raise"])
    p_vs_line = p_mc if p_mc is not None else pr["p_raise"]
    supports = bool(
        rt["drops_total_slowplay_by_at_least_2pct"]
        and p_vs_line < BN_BREAK_EVEN_P_RAISE
    )
    return {
        "co_never_slowplay_confirmed": True,
        "co_open_minus_best_pass_pair_A": CO_NEVER_SLOWPLAY_PIN[
            "pair_A_open_minus_best_pass"
        ],
        "co_open_minus_best_pass_two_pair": CO_NEVER_SLOWPLAY_PIN[
            "two_pair_open_minus_best_pass"
        ],
        "r_hj_star_mass_weighted": r_hj,
        "r_hj_by_class": r_by_class,
        "r_hj_all_open": r_all_open,
        "r_hj_all_slowplay": r_all_slow,
        "r_1_5": 1.0,
        "r_tot": rt["r_tot"],
        "r_tot_at_all_100": planning_r_tot(1.0, 1.0)["r_tot"],
        "slowplay_rate_drop": drop,
        "drops_total_slowplay_by_at_least_2pct": rt[
            "drops_total_slowplay_by_at_least_2pct"
        ],
        "p_raise_independent_at_r_star": pr["p_raise"],
        "p_raise_independent_at_all_100": pr_100["p_raise"],
        "p_raise_mc_at_all_100": 0.495925,
        "p_raise_mc_at_r_star": p_mc,
        "bn_break_even_p_raise": BN_BREAK_EVEN_P_RAISE,
        "p_raise_below_bn_break_even_independent": pr["p_raise"]
        < BN_BREAK_EVEN_P_RAISE,
        "p_raise_below_bn_break_even": p_vs_line < BN_BREAK_EVEN_P_RAISE,
        "supports_bn_open_everything": supports,
        "hundred_pct_hj_slowplay_is_optimal": r_all_slow,
        "note": (
            "Primary EV(open) mixes the 1–5 raise (hypothesis) with the "
            "no-raise steal/2:1/legal leaf. World-0 (1–5 unable) is the "
            "sensitivity: it overstates EV(open) if 1–5 raise."
        ),
    }


def run_hijack_slowplay(
    *,
    n_equity: int = DEFAULT_N_EQUITY,
    n_bn: int = DEFAULT_N_REMOVAL_BN,
    n_hands_per_bn: int = DEFAULT_N_HANDS_PER_BN,
    seed: int = DEFAULT_SEED,
    classes: Sequence[str] | None = None,
    progress: bool = True,
    equity_cache: dict[str, dict[str, dict[str, Any]]] | None = None,
    skip_removal: bool = False,
    n_mc: int = 40_000,
    skip_mc: bool = False,
) -> dict[str, Any]:
    use = list(classes) if classes else list(FOCUS_CLASSES)
    inv = inventory()
    cached = equity_cache or {}
    rows: list[ClassMix] = []
    equity_out: dict[str, Any] = {}
    removal_out: dict[str, Any] = {}
    for cls in use:
        if progress:
            print(f"  {cls}: equity vs open-legal / two_pair+ (n={n_equity})…")
        eq = cached.get(cls, {})
        eq_legal = eq.get("legal")
        eq_tp = eq.get("two_pair_plus")
        if eq_legal is None:
            eq_legal = equity_vs_range(
                cls,
                _villain_open_legal,
                n=n_equity,
                seed=seed + zlib_offset(cls, "legal"),
            )
        if eq_tp is None:
            eq_tp = equity_vs_range(
                cls,
                _villain_two_pair_plus,
                n=n_equity,
                seed=seed + zlib_offset(cls, "tp"),
            )
        equity_out[cls] = {"legal": eq_legal, "two_pair_plus": eq_tp}
        if skip_removal:
            removal = None
        else:
            if progress:
                print(f"  {cls}: class-blocked removal…")
            removal = _removal_for_class(
                cls, n_bn=n_bn, n_hands=n_hands_per_bn, seed=seed
            )
        removal_out[cls] = removal
        probs = _probs_from_removal(removal, inv)
        rows.append(
            evaluate_class(
                cls,
                eq_legal=eq_legal,
                eq_tp=eq_tp,
                p_not_legal=probs["p_not_legal"],
                p_2to1=probs["p_2to1"],
                p_raise_15=probs["p_raise_15"],
                p_behind_opens=probs["p_behind_opens"],
            )
        )
    r_by_class = {r.hj_class: r.r_star for r in rows}
    deal_mc: dict[str, Any] | None = None
    if not skip_mc and n_mc > 0:
        if progress:
            print(f"  deal MC p_raise at r* (n={n_mc}, BN pair_J)…")
        deal_mc = deal_mc_p_raise_hj_mix(
            r_by_class, n=n_mc, seed=seed, bn_class="pair_J"
        )
    answers = derive_answers(rows, inv, deal_mc=deal_mc)
    uncond = independent_p_raise_unconditional(SANDBAG_WORLD_SEATS_1_6_ONLY)
    return {
        "meta": {
            "frame": "hijack_slowplay",
            "seed": seed,
            "n_equity": n_equity,
            "n_bn": n_bn,
            "n_hands_per_bn": n_hands_per_bn,
            "n_mc": n_mc if not skip_mc else 0,
            "laboratory": {
                "co": "never sandbags (opens every legal)",
                "bn": "opens every legal (temporary hypothesis)",
                "hj_sandbag_set": "two_pair_plus and pair_A",
                "seats_1_5": (
                    "100% sandbag two pair+; LJ still opens AA; they raise "
                    "an HJ open"
                ),
            },
            "accounting": {
                "pass": PASS_EV,
                "steal": STEAL_EV,
                "fold_to_raise": FOLD_JJ_TO_RAISE_EV,
                "raise_checkdown_pot": 10.0,
                "called_net": "EV_street - $2 (pot $6 into draw)",
            },
            "approximations": [
                "CO/BN call every legal if HJ opens (v1; they do not raise).",
                "1–5 raise two pair+ if HJ opens (hypothesis stack).",
                "Slowplay raise vs CO/BN uses checkdown ($10 pot); no fold "
                "equity vs JJ–KK (conservative for slowplay).",
                "Vs 1–5 raise: best of fold −$2 and call-checkdown; no 3-bet Nash.",
                "pair_A / two_pair vs-legal open street reused from CO lab.",
                "v1 is approximate GTO, not full 8-way Nash.",
            ],
            "locked_draws": {
                "name": LOCKED_BN_DRAW.name,
                "pair_d": LOCKED_BN_DRAW.pair_d,
                "two_pair_d": LOCKED_BN_DRAW.two_pair_d,
                "trips_d": LOCKED_BN_DRAW.trips_d,
                "quads_d": LOCKED_BN_DRAW.quads_d,
            },
            "doc": "docs/research/hijack_slowplay.md",
            "regenerate": (
                "python -m fivecarddraw.validation.hijack_slowplay --write-fixture"
            ),
            "co_pin": CO_NEVER_SLOWPLAY_PIN,
        },
        "inventory": inv,
        "independent_unconditional_1_6": uncond,
        "planning_pins": {
            "p_j": P_J_PLAN,
            "p_s_1_5": P_S_15_PLAN,
            "p_s_hj": P_S_HJ_PLAN,
            "p_raise_all_100": planning_p_raise_rates(1.0, 1.0)["p_raise"],
            "p_raise_r_hj_0": planning_p_raise_rates(1.0, 0.0)["p_raise"],
            "r_tot_all_100": planning_r_tot(1.0, 1.0)["r_tot"],
            "r_tot_r_hj_0": planning_r_tot(1.0, 0.0)["r_tot"],
            "r_hj_for_r_tot_0_98": planning_r_tot(1.0, 1.0)["r_hj_for_r_tot_le_0_98"],
        },
        "removal": {
            k: ({kk: vv for kk, vv in (v or {}).items() if not kk.startswith("_")})
            if v
            else None
            for k, v in removal_out.items()
        },
        "equity": equity_out,
        "deal_mc_r_star": deal_mc,
        "by_class": [r.as_dict() | {"probs_source": _probs_from_removal(removal_out[r.hj_class], inv)["source"]} for r in rows],
        "answers": answers,
    }


def zlib_offset(cls: str, tag: str) -> int:
    import zlib

    return zlib.adler32(f"{cls}|{tag}".encode()) % 10_000


def default_fixture_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "validation"
        / "hijack_slowplay.json"
    )


def write_fixture(payload: dict[str, Any], path: Path | None = None) -> Path:
    path = path or default_fixture_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    slim = {
        "meta": payload["meta"],
        "inventory": {
            k: v
            for k, v in payload["inventory"].items()
            if k != "hj_sandbag_mass"
        },
        "inventory_hj_mass": payload["inventory"]["hj_sandbag_mass"],
        "planning_pins": payload["planning_pins"],
        "independent_unconditional_1_6": {
            "p_raise": payload["independent_unconditional_1_6"]["p_raise"],
            "p_no_raise": payload["independent_unconditional_1_6"]["p_no_raise"],
        },
        "equity": payload["equity"],
        "deal_mc_r_star": payload.get("deal_mc_r_star"),
        "by_class": payload["by_class"],
        "answers": payload["answers"],
    }
    path.write_text(json.dumps(slim, indent=2) + "\n", encoding="utf-8")
    return path


def load_fixture(path: Path | None = None) -> dict[str, Any]:
    path = path or default_fixture_path()
    return json.loads(path.read_text(encoding="utf-8"))


def _print_payload(payload: dict[str, Any]) -> None:
    a = payload["answers"]
    pin = payload["meta"]["co_pin"]
    print("CO never-slowplay:", pin["confirmed_never_slowplay"])
    print(
        f"  lab: {pin['laboratory']}"
    )
    print(
        f"  JJ EV(open)={pin['q1_jj_ev_open']:+.3f} vs pass 0; "
        f"AA open−best pass={pin['pair_A_open_minus_best_pass']:+.2f}; "
        f"two pair={pin['two_pair_open_minus_best_pass']:+.2f}"
    )
    print("HJ class mixes (hypothesis: 1–5 raise):")
    for r in payload["by_class"]:
        print(
            f"  {r['hj_class']:<18} open_hyp={r['ev_open_hyp']:+.3f}  "
            f"slow={r['ev_slowplay']:+.3f}  Δ={r['ev_open_minus_slowplay']:+.3f}  "
            f"r*={r['r_star']:.2f} ({r['action']})  "
            f"world0={r['ev_open_world0']:+.3f}  "
            f"vs_raise={r['vs_raise_policy']}"
        )
    print(
        f"r_HJ*={a['r_hj_star_mass_weighted']:.4f}  "
        f"r_tot={a['r_tot']:.4f} (100% was {a['r_tot_at_all_100']:.4f}, "
        f"drop={a['slowplay_rate_drop']:.4f})"
    )
    mc_star = a.get("p_raise_mc_at_r_star")
    mc_star_s = "n/a" if mc_star is None else f"{mc_star:.4f}"
    print(
        f"p_raise independent at r*={a['p_raise_independent_at_r_star']:.4f} "
        f"MC at r*={mc_star_s} vs BN break-even {a['bn_break_even_p_raise']:.4f} "
        f"(all-100 independent {a['p_raise_independent_at_all_100']:.4f}, "
        f"MC {a['p_raise_mc_at_all_100']:.4f})"
    )
    print(
        f"≥2% drop: {a['drops_total_slowplay_by_at_least_2pct']}  "
        f"supports BN open-everything: {a['supports_bn_open_everything']}  "
        f"100% HJ slowplay optimal: {a['hundred_pct_hj_slowplay_is_optimal']}"
    )


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(
        description="HJ slowplay mix vs open (CO never sandbags; BN open-everything hypothesis)"
    )
    p.add_argument("--n-equity", type=int, default=DEFAULT_N_EQUITY)
    p.add_argument("--n-bn", type=int, default=DEFAULT_N_REMOVAL_BN)
    p.add_argument("--n-hands-per-bn", type=int, default=DEFAULT_N_HANDS_PER_BN)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--quick", action="store_true")
    p.add_argument("--skip-removal", action="store_true")
    p.add_argument("--n-mc", type=int, default=40_000)
    p.add_argument("--skip-mc", action="store_true")
    p.add_argument(
        "--classes",
        type=str,
        default=None,
        help="Comma-separated HJ classes",
    )
    p.add_argument("-o", "--output", type=Path, default=None)
    p.add_argument("--write-fixture", action="store_true")
    args = p.parse_args()
    n_eq, n_bn, n_h = args.n_equity, args.n_bn, args.n_hands_per_bn
    skip_rem = args.skip_removal
    skip_mc = args.skip_mc
    n_mc = args.n_mc
    if args.quick:
        n_eq, n_bn, n_h, n_mc = 250, 200, 20, 400
        skip_rem = True
        skip_mc = True
    classes = (
        [c.strip() for c in args.classes.split(",") if c.strip()]
        if args.classes
        else None
    )
    payload = run_hijack_slowplay(
        n_equity=n_eq,
        n_bn=n_bn,
        n_hands_per_bn=n_h,
        seed=args.seed,
        classes=classes,
        progress=True,
        skip_removal=skip_rem,
        n_mc=n_mc,
        skip_mc=skip_mc,
    )
    out = args.output or Path("outputs/validation/hijack_slowplay.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out}")
    if args.write_fixture:
        fix = write_fixture(payload)
        print(f"Wrote fixture {fix}")
    _print_payload(payload)


if __name__ == "__main__":
    main()
