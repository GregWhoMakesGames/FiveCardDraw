"""Reusable bluff-frequency helpers (Ring 1 library).

Later streets (miss stabs, CO return-to-actor) should import these rather than
forking a third post-draw simulator. Payoffs come from `play_raise_node`.

Doc: `docs/NEXT_STAGE_POSTDRAW_BLUFF.md`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from fivecarddraw.rules import pot_odds_to_call as POT_ODDS_TO_CALL
from fivecarddraw.validation.postdraw_betting_m2 import (
    BIG,
    play_raise_node,
)
from fivecarddraw.validation.postdraw_cap import family_bucket, fine_bucket
from fivecarddraw.validation.postdraw_nonbluff_ev import caller_ev_from_bn

# Public names are CAPS_SNAKE so later bluff tickets pin the same break-even.
__all__ = [
    "AIR_SHARE_OF_THREE_BETS",
    "BEST_RESPONSE",
    "BIG",
    "BISECT_ROOT",
    "BLUFF_TWO_PAIR_TRIPS",
    "BN_POLAR_MIX",
    "CALL_3BET",
    "CALLER_EVS",
    "CALLER_MIX",
    "CATCHER_EVS",
    "CATCHER_FLUSH",
    "COMPUTE_STRATEGY_EV",
    "FOLD_RAISE_EV_BN",
    "INDIFFERENCE_RESULT",
    "INDIFFERENCE_ROOT",
    "NODE_PAYOFF",
    "POT_AFTER_3BET",
    "POT_ODDS_CALL_3BET",
    "POT_ODDS_TO_CALL",
    "PRECOMPUTE_RAISE_NODE_PAYOFFS",
    "RING1_CALLER_CALL_FLUSH",
    "RING1_CALLER_FOLD_CATCHERS",
    "STRATEGY_EV",
    "VALUE_BOAT_PLUS",
    "VALUE_FLUSH_PLUS",
]

# After BN 3-bet: pot $26, $4 for the caller to call. Break-even 4/30.
POT_AFTER_3BET = 26.0
CALL_3BET = BIG  # 4.0
POT_ODDS_CALL_3BET = POT_ODDS_TO_CALL(POT_AFTER_3BET, CALL_3BET)  # 4/30
# BN already bet $4; folding the raise surrenders that bet. Not the 3-bet steal.
FOLD_RAISE_EV_BN = -BIG  # -4.0

VALUE_FLUSH_PLUS = frozenset({"flush", "boat_plus"})
VALUE_BOAT_PLUS = frozenset({"boat_plus"})
BLUFF_TWO_PAIR_TRIPS = frozenset({"two_pair_or_trips"})
CATCHER_FLUSH = "flush"

# BN vs a cap: two pair / trips fold (they were bluffing); flush+ calls.
_FOLD_CAP_FAMILIES = frozenset({"two_pair_or_trips", "pair_or_worse"})


@dataclass(frozen=True, slots=True)
class BN_POLAR_MIX:
    """BN 3-bet mix on the raise node.

    Value buckets always 3-bet. Bluff buckets 3-bet with frequency `beta`;
    otherwise they **fold** the raise (drawing dead to a straight+ raiser).
    Remaining families (straights) call. Vs a cap: bluff-bucket hands fold;
    others call.

    Empty `value_buckets` and `bluff_buckets` is the call-it-down baseline
    (always call the raise).
    """

    beta: float
    value_buckets: frozenset[str] = VALUE_FLUSH_PLUS
    bluff_buckets: frozenset[str] = BLUFF_TWO_PAIR_TRIPS

    def p_three_bet(self, bn_family: str) -> float:
        if bn_family in self.value_buckets:
            return 1.0
        if bn_family in self.bluff_buckets:
            return float(self.beta)
        return 0.0

    def leftover_vs_raise(self, bn_family: str) -> str:
        """Action when not 3-betting: fold bluff buckets, else call."""
        if bn_family in self.bluff_buckets:
            return "fold"
        return "call"

    def leftover_ev_bn(self, p: NODE_PAYOFF) -> float:
        if self.leftover_vs_raise(p.bn_family) == "fold":
            return p.ev_bn_fold_raise
        return p.ev_bn_call

    def folds_cap(self, bn_family: str) -> bool:
        return bn_family in self.bluff_buckets


@dataclass(frozen=True, slots=True)
class CALLER_MIX:
    """Caller vs-3-bet action by family bucket (`fold` / `call` / `cap`)."""

    by_family: Mapping[str, str]

    def action(self, caller_family: str) -> str:
        return self.by_family.get(caller_family, "fold")


# Ring 1 held caller: SF/boat+ caps; straights fold; flushes are the search target.
RING1_CALLER_FOLD_CATCHERS = CALLER_MIX(
    {"straight": "fold", "flush": "fold", "boat_plus": "cap"}
)
RING1_CALLER_CALL_FLUSH = CALLER_MIX(
    {"straight": "fold", "flush": "call", "boat_plus": "cap"}
)


@dataclass(frozen=True, slots=True)
class NODE_PAYOFF:
    """One raise-node deal, with EV_bn for the lines Ring 1 needs."""

    bn_family: str
    caller_family: str
    bn_fine: str
    caller_fine: str
    ev_bn_call: float
    ev_bn_fold_raise: float
    ev_bn_3bet_fold: float
    ev_bn_3bet_call: float
    ev_bn_3bet_cap_bn_call: float
    ev_bn_3bet_cap_bn_fold: float


@dataclass(frozen=True, slots=True)
class STRATEGY_EV:
    ev_bn: float
    ev_caller: float
    n: float
    p_3bet: float
    p_cap: float
    p_fold_3bet: float


@dataclass(frozen=True, slots=True)
class CALLER_EVS:
    """Caller EV on the 3-bet subtree (fold is −8 when the steal works)."""

    n_weight: float
    ev_fold: float
    ev_call: float
    ev_cap: float

    @property
    def call_minus_fold(self) -> float:
        return self.ev_call - self.ev_fold


@dataclass(frozen=True, slots=True)
class INDIFFERENCE_RESULT:
    beta: float
    alpha: float
    bracketed: bool
    catcher: CALLER_EVS
    n_value: float
    n_bluff: float
    n_catcher: float
    n_catcher_vs_value: float
    n_catcher_vs_bluff: float
    f_at_0: float
    f_at_1: float
    f_at_beta: float


def PRECOMPUTE_RAISE_NODE_PAYOFFS(deals: Sequence[Any]) -> list[NODE_PAYOFF]:
    """Chip payoffs via `play_raise_node` (max_raises=3). Do not fork a street."""
    out: list[NODE_PAYOFF] = []
    for deal in deals:
        ev_call, _ = play_raise_node(deal, bn_vs_raise="call")
        ev_fold_raise, _ = play_raise_node(deal, bn_vs_raise="fold")
        ev_fold, _ = play_raise_node(
            deal, bn_vs_raise="three_bet", caller_vs_3bet="fold"
        )
        ev_call3, _ = play_raise_node(
            deal, bn_vs_raise="three_bet", caller_vs_3bet="call"
        )
        ev_cap_call, _ = play_raise_node(
            deal,
            bn_vs_raise="three_bet",
            caller_vs_3bet="cap",
            bn_vs_cap="call",
        )
        ev_cap_fold, _ = play_raise_node(
            deal,
            bn_vs_raise="three_bet",
            caller_vs_3bet="cap",
            bn_vs_cap="fold",
        )
        out.append(
            NODE_PAYOFF(
                bn_family=family_bucket(deal.opener_final),
                caller_family=family_bucket(deal.drawer_final),
                bn_fine=fine_bucket(deal.opener_final),
                caller_fine=fine_bucket(deal.drawer_final),
                ev_bn_call=ev_call,
                ev_bn_fold_raise=ev_fold_raise,
                ev_bn_3bet_fold=ev_fold,
                ev_bn_3bet_call=ev_call3,
                ev_bn_3bet_cap_bn_call=ev_cap_call,
                ev_bn_3bet_cap_bn_fold=ev_cap_fold,
            )
        )
    return out


def _three_bet_ev_bn(p: NODE_PAYOFF, caller_act: str, bn_mix: BN_POLAR_MIX) -> float:
    if caller_act == "fold":
        return p.ev_bn_3bet_fold
    if caller_act == "call":
        return p.ev_bn_3bet_call
    if caller_act != "cap":
        raise ValueError(f"unknown caller action: {caller_act}")
    if bn_mix.folds_cap(p.bn_family):
        return p.ev_bn_3bet_cap_bn_fold
    return p.ev_bn_3bet_cap_bn_call


def COMPUTE_STRATEGY_EV(
    deals: Sequence[Any] | None,
    bn_mix: BN_POLAR_MIX,
    caller_mix: CALLER_MIX,
    *,
    payoffs: Sequence[NODE_PAYOFF] | None = None,
) -> STRATEGY_EV:
    """Mean EV_bn / EV_caller on the node via `play_raise_node` payoffs.

    Mixed BN 3-bets are a convex combination (no extra RNG).
    """
    rows = payoffs if payoffs is not None else PRECOMPUTE_RAISE_NODE_PAYOFFS(deals or ())
    if not rows:
        return STRATEGY_EV(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    ev_sum = 0.0
    p3_sum = 0.0
    cap_sum = 0.0
    fold_sum = 0.0
    for p in rows:
        p3 = bn_mix.p_three_bet(p.bn_family)
        p3_sum += p3
        ev = (1.0 - p3) * bn_mix.leftover_ev_bn(p)
        if p3 > 0.0:
            act = caller_mix.action(p.caller_family)
            ev += p3 * _three_bet_ev_bn(p, act, bn_mix)
            if act == "cap":
                cap_sum += p3
            elif act == "fold":
                fold_sum += p3
        ev_sum += ev
    n = float(len(rows))
    ev_bn = ev_sum / n
    return STRATEGY_EV(
        ev_bn=ev_bn,
        ev_caller=caller_ev_from_bn(ev_bn),
        n=n,
        p_3bet=p3_sum / n,
        p_cap=cap_sum / n,
        p_fold_3bet=fold_sum / n,
    )


def AIR_SHARE_OF_THREE_BETS(
    payoffs: Sequence[NODE_PAYOFF],
    bn_mix: BN_POLAR_MIX,
) -> tuple[float, float, float, float]:
    """α = bluff mass / all 3-bet mass. Also returns (n_value, n_bluff, n_3bet)."""
    n_value = 0.0
    n_bluff = 0.0
    for p in payoffs:
        if p.bn_family in bn_mix.value_buckets:
            n_value += 1.0
        elif p.bn_family in bn_mix.bluff_buckets:
            n_bluff += 1.0
    n_3bet = n_value + bn_mix.beta * n_bluff
    alpha = (bn_mix.beta * n_bluff / n_3bet) if n_3bet > 0.0 else 0.0
    return alpha, n_value, n_bluff, n_3bet


def CATCHER_EVS(
    payoffs: Sequence[NODE_PAYOFF],
    bn_mix: BN_POLAR_MIX,
    catcher_bucket: str = CATCHER_FLUSH,
    *,
    caller_key: str = "family",
) -> CALLER_EVS:
    """Caller EV_fold / EV_call / EV_cap facing a 3-bet, combo-weighted by p(3-bet)."""
    w = 0.0
    fold_bn = 0.0
    call_bn = 0.0
    cap_bn = 0.0
    for p in payoffs:
        key = p.caller_family if caller_key == "family" else p.caller_fine
        if key != catcher_bucket:
            continue
        p3 = bn_mix.p_three_bet(p.bn_family)
        if p3 <= 0.0:
            continue
        w += p3
        fold_bn += p3 * p.ev_bn_3bet_fold
        call_bn += p3 * p.ev_bn_3bet_call
        cap_line = (
            p.ev_bn_3bet_cap_bn_fold
            if bn_mix.folds_cap(p.bn_family)
            else p.ev_bn_3bet_cap_bn_call
        )
        cap_bn += p3 * cap_line
    if w <= 0.0:
        nan = float("nan")
        return CALLER_EVS(0.0, nan, nan, nan)
    return CALLER_EVS(
        n_weight=w,
        ev_fold=caller_ev_from_bn(fold_bn / w),
        ev_call=caller_ev_from_bn(call_bn / w),
        ev_cap=caller_ev_from_bn(cap_bn / w),
    )


def BISECT_ROOT(
    f: Callable[[float], float],
    lo: float = 0.0,
    hi: float = 1.0,
    *,
    xtol: float = 1e-10,
    max_iter: int = 80,
) -> tuple[float, bool, float, float]:
    """Approximate f(x)=0 on [lo, hi]. Returns (x, bracketed, f(lo), f(hi))."""
    f_lo = f(lo)
    f_hi = f(hi)
    if f_lo == 0.0 or abs(f_lo) < 1e-12:
        return lo, True, f_lo, f_hi
    if f_hi == 0.0 or abs(f_hi) < 1e-12:
        return hi, True, f_lo, f_hi
    bracketed = f_lo * f_hi < 0.0
    if not bracketed:
        x = lo if abs(f_lo) <= abs(f_hi) else hi
        return x, False, f_lo, f_hi
    a, b, fa = lo, hi, f_lo
    mid = 0.5 * (a + b)
    for _ in range(max_iter):
        mid = 0.5 * (a + b)
        fm = f(mid)
        if abs(b - a) < xtol or abs(fm) < 1e-12:
            return mid, True, f_lo, f_hi
        if fa * fm <= 0.0:
            b = mid
        else:
            a, fa = mid, fm
    return mid, True, f_lo, f_hi


def INDIFFERENCE_ROOT(
    deals: Sequence[Any] | None,
    value_buckets: frozenset[str] | set[str] = VALUE_FLUSH_PLUS,
    bluff_buckets: frozenset[str] | set[str] = BLUFF_TWO_PAIR_TRIPS,
    catcher_bucket: str = CATCHER_FLUSH,
    *,
    payoffs: Sequence[NODE_PAYOFF] | None = None,
    xtol: float = 1e-10,
) -> INDIFFERENCE_RESULT:
    """β (and α) s.t. catcher EV_call − EV_fold = 0 on the 3-bet subtree.

    Root-find; do not hand-tune. `deals` may be omitted when `payoffs` is given.
    """
    rows = payoffs if payoffs is not None else PRECOMPUTE_RAISE_NODE_PAYOFFS(deals or ())
    value = frozenset(value_buckets)
    bluff = frozenset(bluff_buckets)

    def _f(beta: float) -> float:
        mix = BN_POLAR_MIX(beta=beta, value_buckets=value, bluff_buckets=bluff)
        evs = CATCHER_EVS(rows, mix, catcher_bucket)
        return evs.call_minus_fold

    beta, bracketed, f0, f1 = BISECT_ROOT(_f, 0.0, 1.0, xtol=xtol)
    mix = BN_POLAR_MIX(beta=beta, value_buckets=value, bluff_buckets=bluff)
    catcher = CATCHER_EVS(rows, mix, catcher_bucket)
    alpha, n_value, n_bluff, _n_3bet = AIR_SHARE_OF_THREE_BETS(rows, mix)
    n_catcher = 0.0
    n_vs_value = 0.0
    n_vs_bluff = 0.0
    for p in rows:
        if p.caller_family != catcher_bucket:
            continue
        n_catcher += 1.0
        if p.bn_family in value:
            n_vs_value += 1.0
        elif p.bn_family in bluff:
            n_vs_bluff += 1.0
    return INDIFFERENCE_RESULT(
        beta=beta,
        alpha=alpha,
        bracketed=bracketed,
        catcher=catcher,
        n_value=n_value,
        n_bluff=n_bluff,
        n_catcher=n_catcher,
        n_catcher_vs_value=n_vs_value,
        n_catcher_vs_bluff=n_vs_bluff,
        f_at_0=f0,
        f_at_1=f1,
        f_at_beta=catcher.call_minus_fold,
    )


def BEST_RESPONSE(
    deals: Sequence[Any] | None,
    opponent_mix: BN_POLAR_MIX | CALLER_MIX,
    *,
    payoffs: Sequence[NODE_PAYOFF] | None = None,
    ev_tol: float = 0.05,
) -> dict[str, Any]:
    """Argmax action per own family bucket (no CFR).

    Pass a `BN_POLAR_MIX` to get the **caller's** BR vs that 3-bet mix.
    Pass a `CALLER_MIX` to get **BN's** BR (fold vs call vs 3-bet) vs that responder.
    """
    rows = payoffs if payoffs is not None else PRECOMPUTE_RAISE_NODE_PAYOFFS(deals or ())
    if isinstance(opponent_mix, BN_POLAR_MIX):
        return _caller_best_response(rows, opponent_mix, ev_tol=ev_tol)
    return _bn_best_response(rows, opponent_mix, ev_tol=ev_tol)


def _caller_best_response(
    payoffs: Sequence[NODE_PAYOFF], bn_mix: BN_POLAR_MIX, *, ev_tol: float
) -> dict[str, Any]:
    families = sorted({p.caller_family for p in payoffs})
    rows = []
    for fam in families:
        evs = CATCHER_EVS(payoffs, bn_mix, fam)
        if evs.n_weight <= 0.0:
            continue
        scored = (
            ("fold", evs.ev_fold),
            ("call", evs.ev_call),
            ("cap", evs.ev_cap),
        )
        best_act, best_ev = max(scored, key=lambda kv: kv[1])
        near = [a for a, e in scored if abs(e - best_ev) <= ev_tol]
        if "call" in near and "fold" in near and best_act in {"call", "fold"}:
            recommend = "indifferent"
        else:
            recommend = best_act
        rows.append(
            {
                "side": "caller",
                "bucket": fam,
                "n_weight": round(evs.n_weight, 5),
                "ev_fold": round(evs.ev_fold, 5),
                "ev_call": round(evs.ev_call, 5),
                "ev_cap": round(evs.ev_cap, 5),
                "recommend": recommend,
                "near_best": near,
            }
        )
    return {"side": "caller", "rows": rows}


def _bn_best_response(
    payoffs: Sequence[NODE_PAYOFF], caller_mix: CALLER_MIX, *, ev_tol: float
) -> dict[str, Any]:
    families = sorted({p.bn_family for p in payoffs})
    rows = []
    for fam in families:
        n = 0.0
        ev_fold = 0.0
        ev_call = 0.0
        ev_3bet = 0.0
        # A 3-bet from this family folds a cap iff it is a bluff family.
        probe = BN_POLAR_MIX(
            beta=1.0 if fam in BLUFF_TWO_PAIR_TRIPS else 0.0,
            value_buckets=frozenset({fam}) if fam not in BLUFF_TWO_PAIR_TRIPS else frozenset(),
            bluff_buckets=frozenset({fam}) if fam in BLUFF_TWO_PAIR_TRIPS else frozenset(),
        )
        for p in payoffs:
            if p.bn_family != fam:
                continue
            n += 1.0
            ev_fold += p.ev_bn_fold_raise
            ev_call += p.ev_bn_call
            act = caller_mix.action(p.caller_family)
            ev_3bet += _three_bet_ev_bn(p, act, probe)
        if n <= 0.0:
            continue
        ev_fold /= n
        ev_call /= n
        ev_3bet /= n
        scored = (
            ("fold", ev_fold),
            ("call", ev_call),
            ("three_bet", ev_3bet),
        )
        best_act, best_ev = max(scored, key=lambda kv: kv[1])
        near = [a for a, e in scored if abs(e - best_ev) <= ev_tol]
        recommend = "indifferent" if len(near) > 1 else best_act
        rows.append(
            {
                "side": "bn",
                "bucket": fam,
                "n": n,
                "ev_bn_fold_raise": round(ev_fold, 5),
                "ev_bn_call": round(ev_call, 5),
                "ev_bn_3bet": round(ev_3bet, 5),
                "delta_3bet_vs_fold": round(ev_3bet - ev_fold, 5),
                "delta_3bet_vs_call": round(ev_3bet - ev_call, 5),
                "delta_fold_vs_call": round(ev_fold - ev_call, 5),
                "recommend": recommend,
                "near_best": near,
            }
        )
    return {"side": "bn", "rows": rows}


def family_counts(payoffs: Sequence[NODE_PAYOFF]) -> dict[str, dict[str, float]]:
    bn: dict[str, float] = {}
    caller: dict[str, float] = {}
    for p in payoffs:
        bn[p.bn_family] = bn.get(p.bn_family, 0.0) + 1.0
        caller[p.caller_family] = caller.get(p.caller_family, 0.0) + 1.0
    return {"bn": bn, "caller": caller}
