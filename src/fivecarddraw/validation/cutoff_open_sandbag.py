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
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

from fivecarddraw.cards import card_from_id
from fivecarddraw.validation.cascade_odds import TOTAL_HANDS
from fivecarddraw.validation.cutoff_open import load_summary_fixture as load_cutoff_open
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
from fivecarddraw.validation.showdown_matrix import classify_opener, load_showdown_matrix

WORLD = SANDBAG_WORLD_CO_VS_SEATS_1_6
FOCUS_CLASSES = FOLD_TO_RAISE_CLASSES  # pair_J, pair_Q, pair_K
SEATS_1_6 = tuple(range(1, 7))
# Writeup planning masses (combo / C(53,5)); tests pin the live inventory.
P_JUNK_WRITEUP = 0.7760
P_SANDBAG_EARLY_WRITEUP = 0.0821
P_SANDBAG_HJ_WRITEUP = 0.1302


def _ids_to_cls(ids: Sequence[int]) -> str | None:
    return classify_opener(tuple(card_from_id(i) for i in ids))


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
        )


def deal_mc_p_raise_given_passed_co(
    *,
    n: int = DEFAULT_MC_N,
    seed: int = DEFAULT_MC_SEED,
    co_class: str = "pair_J",
    world: str = WORLD,
) -> CoDealMcResult:
    """P(≥1 of 1–6 sandbag-set | 1–6 no voluntary, CO holds ``co_class``).

    BN is dealt and **not** filtered (unlike folded-to-BN worlds). CO is the
    hero, so CO is not a sandbag raiser in this world.
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
            if is_voluntary_opener(cls, seat, world):
                rejected = True
                break
            if is_sandbag_set(cls, seat, world):
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
    return {
        "co_class": mc.co_class,
        "world": mc.world,
        **mix,
        "ev_open_0pct": mix_0["ev_open"],
        "ev_open_100pct": mix["ev_open"],
        "se_p_raise": mc.se_p_raise,
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
        "--classes",
        type=str,
        default=None,
        help="Comma-separated CO classes (default: pair_J,pair_Q,pair_K)",
    )
    args = p.parse_args()
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
