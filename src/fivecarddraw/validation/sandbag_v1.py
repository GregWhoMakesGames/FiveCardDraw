"""Sandbag-set v1: seat predicates and folded-to-BN raise probability.

Frame: ``button_open_sandbag_v1``. Seats 1–7 pass the v1 sandbag-set 100%
and always raise a BN open; BN always folds JJ to that raise (−$2).

The no-raise leaf (nobody in 1–7 has a sandbag-set hand either) is the
0% sandbag JJ open: steal + 2:1 call, locked-draw §3.4 pair_J d=3.
This module does **not** rebuild post-draw Nash / Ring 1.

Seats 1–8: UTG … LJ, HJ, CO, BN. Aces sandbag is HJ+CO (6 and 7), not LJ.
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
ACES_SANDBAG_SEATS = frozenset({SEAT_HJ, SEAT_CO})  # HJ+CO, not LJ

TWO_PAIR_PLUS_CLASSES = frozenset(TWO_PAIR_CLASSES + TRIPS_CLASSES + STRAIGHT_PLUS_CLASSES)

# Accounting (already pinned in the sandbag ticket).
PASS_EV = 0.0
STEAL_EV = 2.0
FOLD_JJ_TO_RAISE_EV = -2.0
# Called street: pot $6, EV_bn is BN's share; net vs pass is EV_bn − $2,
# so EV(open) = 2 + p_call * (EV_bn − 4). See button_open_no_sandbagging.md.
CALLED_POT = 6.0

# Reused 0% sandbag JJ open pieces — do not resimulate the vs-draw street.
# pair_J d=3 EV_bn from tests/fixtures/validation/postdraw_nonbluff_ev_summary.json
# (locked draws; docs round to +3.08).
PAIR_J_D3_EV_BN = 3.0755
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


def is_sandbag_set(cls: str | None, seat: int) -> bool:
    """True if ``seat`` (1–7) 100% passes this opener class in v1.

    Seats 1–7: two pair or better. Seats 6 (HJ) and 7 (CO) also pair of aces.
    LJ (seat 5) still opens aces. Non-openers and BN are never sandbag-set.
    """
    if cls is None or seat not in SEATS_BEFORE_BN:
        return False
    if is_two_pair_plus(cls):
        return True
    return cls == "pair_A" and seat in ACES_SANDBAG_SEATS


def is_voluntary_opener(cls: str | None, seat: int) -> bool:
    """Open-legal minus that seat's sandbag-set. Under 100% sandbag, this opens."""
    if cls is None or seat not in SEATS_BEFORE_BN:
        return False
    return not is_sandbag_set(cls, seat)


def classify_cards(cards: Iterable[Card] | Sequence[int]) -> str | None:
    """``classify_opener`` over cards or card ids."""
    seq = tuple(cards)
    if seq and isinstance(seq[0], int):
        seq = tuple(card_from_id(i) for i in seq)  # type: ignore[misc]
    return classify_opener(seq)


def _opener_combo_counts() -> dict[str, int]:
    return dict(load_showdown_matrix()["opener_combo_counts"])


def sandbag_set_combo_count(seat: int) -> int:
    """Unconditional combo count of the v1 sandbag-set for ``seat`` (1–7)."""
    counts = _opener_combo_counts()
    two_pair_plus = sum(counts[c] for c in TWO_PAIR_PLUS_CLASSES)
    if seat in ACES_SANDBAG_SEATS:
        return two_pair_plus + int(counts["pair_A"])
    return two_pair_plus


def voluntary_combo_count(seat: int) -> int:
    counts = _opener_combo_counts()
    open_legal = sum(counts.values())
    return open_legal - sandbag_set_combo_count(seat)


def not_open_legal_count() -> int:
    counts = _opener_combo_counts()
    return TOTAL_HANDS - sum(counts.values())


def p_sandbag_given_passed_unconditional(seat: int) -> float:
    """P(sandbag-set | not voluntary) with no card removal."""
    s = sandbag_set_combo_count(seat)
    n = not_open_legal_count()
    return s / (s + n)


def independent_p_raise_unconditional() -> dict[str, float]:
    """Independent-seat P(raise | 1–7 passed) ignoring BN's cards."""
    p_no = 1.0
    by_seat: dict[str, float] = {}
    for seat in SEATS_BEFORE_BN:
        p_n_given_passed = 1.0 - p_sandbag_given_passed_unconditional(seat)
        by_seat[str(seat)] = p_n_given_passed
        p_no *= p_n_given_passed
    return {
        "p_no_raise": p_no,
        "p_raise": 1.0 - p_no,
        **{f"p_neither_given_passed_seat_{k}": v for k, v in by_seat.items()},
    }


def ev_jj_no_sandbag_open(
    *,
    p_call: float = P_ANY_2TO1_FOLDED_TO_BN_MC,
    ev_bn_called: float = PAIR_J_D3_EV_BN,
) -> float:
    """0% sandbag JJ open EV vs pass=0: steal + 2:1 call at §3.4 pair_J d=3."""
    return STEAL_EV + p_call * (ev_bn_called - CALLED_POT + STEAL_EV)


def ev_jj_open_100pct_sandbag(p_raise: float, *, ev_no_raise: float | None = None) -> float:
    """Mix: no-raise leaf reuses 0% sandbag JJ EV; raise leaf is fold JJ (−$2)."""
    leaf = ev_jj_no_sandbag_open() if ev_no_raise is None else ev_no_raise
    return (1.0 - p_raise) * leaf + p_raise * FOLD_JJ_TO_RAISE_EV


def _ids_to_cls(ids: Sequence[int]) -> str | None:
    return classify_opener(tuple(card_from_id(i) for i in ids))


def independent_p_raise_bn_pair_j_blocked(
    *,
    n_bn: int = DEFAULT_REMOVAL_BN_N,
    n_hands_per_bn: int = DEFAULT_REMOVAL_HANDS_PER_BN,
    seed: int = DEFAULT_MC_SEED,
) -> dict[str, Any]:
    """Independent-seat P(raise | passed) with BN pair_J card removal.

    Sample BN pair_J, then sample 5-card hands from the remaining 48.
    Seat type only relabels pair_A (voluntary UTG–LJ, sandbag HJ/CO).
    """
    rng = random.Random(seed)
    deck = list(range(53))
    n_early_s = n_early_v = n_early_n = 0
    n_late_s = n_late_v = n_late_n = 0
    n_bn_ok = 0
    n_bn_bug = 0
    tries = 0
    while n_bn_ok < n_bn:
        rng.shuffle(deck)
        tries += 1
        bn_ids = deck[:5]
        cls = _ids_to_cls(bn_ids)
        if cls != "pair_J":
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
                n_late_n += 1
            elif is_sandbag_set(ocls, SEAT_UTG):
                n_early_s += 1
            else:
                n_early_v += 1
            if ocls is None:
                pass
            elif is_sandbag_set(ocls, SEAT_HJ):
                n_late_s += 1
            else:
                n_late_v += 1

    def _p_n_given_passed(n_s: int, n_n: int) -> float:
        return n_n / (n_s + n_n) if (n_s + n_n) else 1.0

    p_n_early = _p_n_given_passed(n_early_s, n_early_n)
    p_n_late = _p_n_given_passed(n_late_s, n_late_n)
    p_no = (p_n_early ** 5) * (p_n_late ** 2)
    n_other = n_bn * n_hands_per_bn
    return {
        "n_bn": n_bn,
        "n_hands_per_bn": n_hands_per_bn,
        "n_other_hands": n_other,
        "n_bn_tries": tries,
        "p_bn_has_bug": n_bn_bug / n_bn if n_bn else 0.0,
        "p_sandbag_early": n_early_s / n_other,
        "p_voluntary_early": n_early_v / n_other,
        "p_neither_early": n_early_n / n_other,
        "p_sandbag_hj_co": n_late_s / n_other,
        "p_voluntary_hj_co": n_late_v / n_other,
        "p_neither_hj_co": n_late_n / n_other,
        "p_neither_given_passed_early": p_n_early,
        "p_neither_given_passed_hj_co": p_n_late,
        "p_no_raise": p_no,
        "p_raise": 1.0 - p_no,
        "seed": seed,
    }


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

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def deal_mc_p_raise_given_passed_bn_pair_j(
    *,
    n: int = DEFAULT_MC_N,
    seed: int = DEFAULT_MC_SEED,
) -> DealMcResult:
    """Seeded 8-way deal MC: P(≥1 sandbag-set | 1–7 no voluntary, BN pair_J)."""
    rng = random.Random(seed)
    deck = list(range(53))
    n_tried = 0
    n_bn_pair_j = 0
    n_cond = 0
    n_raise = 0
    n_bug = 0
    hist: dict[int, int] = {k: 0 for k in range(8)}
    while n_cond < n:
        rng.shuffle(deck)
        n_tried += 1
        bn_ids = deck[35:40]
        bn_cls = _ids_to_cls(bn_ids)
        if bn_cls != "pair_J":
            continue
        n_bn_pair_j += 1
        n_sandbag = 0
        rejected = False
        for seat in SEATS_BEFORE_BN:
            start = 5 * (seat - 1)
            cls = _ids_to_cls(deck[start : start + 5])
            if is_voluntary_opener(cls, seat):
                rejected = True
                break
            if is_sandbag_set(cls, seat):
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
        n_bn_pair_j=n_bn_pair_j,
        n_conditioned=n_cond,
        n_raise=n_raise,
        p_raise=p,
        p_bn_has_bug=n_bug / n_cond if n_cond else 0.0,
        n_tried=n_tried,
        sandbag_seats_hist={str(k): hist[k] for k in range(8)},
        se_p_raise=se,
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
        "independent_bn_pair_j_blocked": removal,
        "deal_mc": mc.as_dict(),
        "findings": {
            **mix,
            "sensitivity_p_call_independent_6pct": mix_ind_call,
            "independent_unconditional_p_raise": uncond["p_raise"],
            "independent_blocked_p_raise": removal["p_raise"],
        },
    }


def default_fixture_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "validation"
        / "sandbag_v1.json"
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


def load_sandbag_v1(path: Path | None = None) -> dict[str, Any]:
    path = path or default_fixture_path()
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(
        description="Sandbag-set v1: P(raise | 7 passed, BN pair_J) and JJ open EV"
    )
    p.add_argument("-o", "--output", type=Path, default=None)
    p.add_argument("--n", type=int, default=DEFAULT_MC_N)
    p.add_argument("--seed", type=int, default=DEFAULT_MC_SEED)
    p.add_argument("--n-bn", type=int, default=DEFAULT_REMOVAL_BN_N)
    p.add_argument("--n-hands-per-bn", type=int, default=DEFAULT_REMOVAL_HANDS_PER_BN)
    p.add_argument("--write-fixture", action="store_true")
    args = p.parse_args()
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
