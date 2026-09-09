"""CO open chart: slowplay rate × blockers for JJ / QQ / KK.

Frame: ``cutoff_open_sandbag_v1``. Reuses the signed 0% leaves and 100%
deal-MC pins (class-average 40k; joker / ace-kicker 10k). Does **not**
rebuild those endpoints.

Interpolation: independent-seat Bayes p_ind(r), calibrated by
kappa = p_MC(1) / p_ind(1) from the card-removal MC. EV(open) =
(1 − p_cal(r)) · L + p_cal(r) · (−2). Ace / joker rows use the
reweighted 0% leaf (steal / 2:1 / BN-behind mix); street EVs stay
class-average cells.

CO never sandbags (two pair+ / aces as the opener).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from fivecarddraw.validation.cutoff_open_sandbag import (
    BLOCKER_CLASSES,
    WORLD,
    calibrated_p_raise_at_rate,
    default_fixture_path,
    independent_p_raise_at_rate,
    invert_calibrated_rate,
    mix_co_open,
)
from fivecarddraw.validation.sandbag_v1 import (
    DEFAULT_MC_SEED,
    FOLD_JJ_TO_RAISE_EV,
    PASS_EV,
)

CHART_FLAVORS = ("class_avg", "ace", "joker")
POLICY_OPEN_ALWAYS = "open_always"
POLICY_ACE_OR_JOKER = "open_ace_or_joker"
POLICY_JOKER_ONLY = "open_joker_only"
POLICY_PASS = "pass"
CLASS_LABELS = {"pair_J": "JJ", "pair_Q": "QQ", "pair_K": "KK"}
# 5% grid plus the playable integer thresholds around each r*.
DEFAULT_CHART_RATES: tuple[float, ...] = tuple(
    sorted(
        {
            i / 100.0
            for i in (
                *range(0, 101, 5),
                78,
                79,
                83,
                84,
                86,
                87,
                89,
                90,
                92,
                93,
                95,
                96,
            )
        }
    )
)


def playable_pct(r: float) -> int:
    """Nearest integer percent. r* > 1 means the flavor stays +EV at 100%."""
    if r > 1.0:
        return 100
    if r < 0.0:
        return 0
    return int(round(100.0 * r))


def opening_policy_at_rate(
    r: float,
    *,
    r_class: float,
    r_ace: float,
    r_joker: float,
) -> str:
    """Requirement to open this pair at slowplay rate r (EV > 0 bands).

    At the exact class-average r* the class EV is 0, so the rule upgrades
    to “need ace or joker” (same voice as the product examples).
    """
    if r < r_class:
        return POLICY_OPEN_ALWAYS
    if r < r_ace:
        return POLICY_ACE_OR_JOKER
    if r < r_joker:
        return POLICY_JOKER_ONLY
    return POLICY_PASS


def flavor_row(data: dict[str, Any], co_class: str, flavor: str) -> dict[str, Any]:
    """Locked mix row: 40k class average, or reweighted ace / joker 10k."""
    if flavor == "class_avg":
        for row in data["by_class"]:
            if row["co_class"] == co_class:
                return row
        raise KeyError(co_class)
    slug = co_class.lower()
    key = f"{slug}_ace_kicker" if flavor == "ace" else f"{slug}_bug"
    return data["blockers"][key]["reweighted_leaf_mix"]


def ev_at_rate(
    r: float,
    *,
    p_mc_1: float,
    p_ind_1: float,
    leaf: float,
    se_p_mc_1: float = 0.0,
    world: str = WORLD,
) -> dict[str, Any]:
    """Calibrated Bayes mix at interior r. p_cal(1) = p_MC(1) by construction."""
    if p_ind_1 <= 0.0:
        raise ValueError("independent p(1) must be positive")
    kappa = p_mc_1 / p_ind_1
    p = calibrated_p_raise_at_rate(r, kappa=kappa, world=world)
    mix = mix_co_open(p, leaf)
    p_ind_r = independent_p_raise_at_rate(r, world=world)
    se_p = se_p_mc_1 * (p_ind_r / p_ind_1) if p_ind_1 else 0.0
    se_ev = se_p * (leaf - FOLD_JJ_TO_RAISE_EV)
    ev = float(mix["ev_open"])
    return {
        "r": r,
        "p_raise": p,
        "p_ind": p_ind_r,
        "ev_open": ev,
        "se_p_raise": se_p,
        "se_ev_open": se_ev,
        "opening_is_positive_ev": ev > PASS_EV,
        "opening_is_negative_ev": ev < PASS_EV,
        "ev_within_1se_of_zero": abs(ev) <= se_ev if se_ev > 0.0 else ev == 0.0,
        "kappa": kappa,
        "leaf": leaf,
    }


def flavor_chart(
    row: dict[str, Any],
    *,
    rates: Sequence[float],
    p_ind_1: float,
    world: str = WORLD,
) -> dict[str, Any]:
    """Grid + r* for one (class, flavor) from a locked mix row. No new MC."""
    leaf = float(row["ev_no_raise_leaf"])
    p_mc_1 = float(row["p_raise"])
    se_p = float(row["se_p_raise"])
    rates_inv = invert_calibrated_rate(
        float(row["break_even_p_raise"]),
        p_mc_1=p_mc_1,
        p_ind_1=p_ind_1,
        world=world,
    )
    r_star = float(rates_inv["r"])
    grid = [
        {
            "r": pt["r"],
            "p_raise": pt["p_raise"],
            "ev_open": pt["ev_open"],
            "se_ev_open": pt["se_ev_open"],
            "opening_is_positive_ev": pt["opening_is_positive_ev"],
            "opening_is_negative_ev": pt["opening_is_negative_ev"],
        }
        for pt in (
            ev_at_rate(
                r,
                p_mc_1=p_mc_1,
                p_ind_1=p_ind_1,
                leaf=leaf,
                se_p_mc_1=se_p,
                world=world,
            )
            for r in rates
        )
    ]
    plus = [g for g in grid if g["opening_is_positive_ev"]]
    minus = [g for g in grid if g["opening_is_negative_ev"]]
    at_one = ev_at_rate(
        1.0,
        p_mc_1=p_mc_1,
        p_ind_1=p_ind_1,
        leaf=leaf,
        se_p_mc_1=se_p,
        world=world,
    )
    at_zero = ev_at_rate(
        0.0,
        p_mc_1=p_mc_1,
        p_ind_1=p_ind_1,
        leaf=leaf,
        se_p_mc_1=se_p,
        world=world,
    )
    return {
        "leaf": leaf,
        "p_mc_1": p_mc_1,
        "se_p_mc_1": se_p,
        "se_ev_100pct": float(row.get("se_ev_open_100pct") or se_p * (leaf + 2.0)),
        "ev_open_0pct": at_zero["ev_open"],
        "ev_open_100pct": float(row["ev_open_100pct"]),
        "ev_open_100pct_calibrated": at_one["ev_open"],
        "r_star": r_star,
        "r_star_linear": float(rates_inv["linear_r"]),
        "r_star_above_100pct": bool(rates_inv["above_100pct"] or r_star > 1.0),
        "r_star_playable_pct": playable_pct(r_star),
        "kappa": float(rates_inv["kappa"]),
        "n": int(row["deal_mc"]["n"]),
        "seed": int(row["deal_mc"]["seed"]),
        "grid": grid,
        "last_plus_ev_grid_r": None if not plus else plus[-1]["r"],
        "first_minus_ev_grid_r": None if not minus else minus[0]["r"],
        "ev_100pct_within_1se_of_zero": bool(row.get("ev_within_1se_of_zero")),
        "opening_is_positive_ev_100pct": bool(row["opening_is_positive_ev"]),
    }


def _playable_rules(
    co_class: str,
    *,
    r_class: float,
    r_ace: float,
    r_joker: float,
    joker_100: dict[str, Any],
) -> list[str]:
    label = CLASS_LABELS[co_class]
    pct_class = playable_pct(r_class)
    pct_ace = playable_pct(r_ace)
    lines = [
        (
            f"If players are slowplaying {pct_class}% of the time, don't open "
            f"{label} unless you have an ace."
        ),
        (
            f"If players are slowplaying {pct_ace}%, don't open {label} at all "
            f"unless you have a joker."
        ),
    ]
    if r_joker > 1.0:
        ev = float(joker_100["ev_open_100pct"])
        if joker_100["ev_100pct_within_1se_of_zero"]:
            lines.append(
                f"At 100%, {label}+joker is +EV inside 1 SE "
                f"(EV {ev:+.3f}; treat as a coin-flip, not a blowout)."
            )
        else:
            lines.append(
                f"At 100%, {label}+joker stays +EV (EV {ev:+.3f}); still open "
                f"with the joker."
            )
    else:
        pct_j = playable_pct(r_joker)
        lines.append(
            f"If players are slowplaying {pct_j}% or more, pass {label} even "
            "with the joker."
        )
    return lines


def class_bands(
    *,
    r_class: float,
    r_ace: float,
    r_joker: float,
) -> dict[str, Any]:
    return {
        POLICY_OPEN_ALWAYS: {
            "r_lo": 0.0,
            "r_hi": r_class,
            "r_hi_playable_pct": playable_pct(r_class),
            "inclusive_hi": False,
        },
        POLICY_ACE_OR_JOKER: {
            "r_lo": r_class,
            "r_hi": r_ace,
            "r_lo_playable_pct": playable_pct(r_class),
            "r_hi_playable_pct": playable_pct(r_ace),
            "inclusive_hi": False,
        },
        POLICY_JOKER_ONLY: {
            "r_lo": r_ace,
            "r_hi": min(r_joker, 1.0),
            "r_lo_playable_pct": playable_pct(r_ace),
            "r_hi_playable_pct": playable_pct(r_joker),
            "inclusive_hi": r_joker > 1.0,
            "through_100pct": r_joker > 1.0,
        },
        POLICY_PASS: {
            "r_lo": r_joker if r_joker <= 1.0 else None,
            "r_hi": 1.0 if r_joker <= 1.0 else None,
            "r_lo_playable_pct": playable_pct(r_joker) if r_joker <= 1.0 else None,
            "through_100pct": r_joker <= 1.0,
            "never_on_unit_interval": r_joker > 1.0,
        },
    }


def _policy_mid(lo: float, hi: float, inclusive_hi: bool) -> float:
    if inclusive_hi and hi >= 1.0:
        return 1.0
    return 0.5 * (lo + hi)


def combined_lookup_rows(
    stars: dict[str, dict[str, float]],
) -> list[dict[str, Any]]:
    """Merge JJ/QQ/KK r* onto one r-axis. Last band includes r=1."""
    cuts = {0.0, 1.0}
    for cls in BLOCKER_CLASSES:
        for flavor in CHART_FLAVORS:
            r = stars[cls][flavor]
            if 0.0 < r < 1.0:
                cuts.add(r)
    edges = sorted(cuts)
    rows: list[dict[str, Any]] = []
    for lo, hi in zip(edges, edges[1:]):
        inclusive_hi = hi >= 1.0
        mid = _policy_mid(lo, hi, inclusive_hi)
        policies = {
            cls: opening_policy_at_rate(
                mid,
                r_class=stars[cls]["class_avg"],
                r_ace=stars[cls]["ace"],
                r_joker=stars[cls]["joker"],
            )
            for cls in BLOCKER_CLASSES
        }
        rows.append(
            {
                "r_lo": lo,
                "r_hi": hi,
                "inclusive_hi": inclusive_hi,
                "r_lo_playable_pct": playable_pct(lo) if lo > 0.0 else 0,
                "r_hi_playable_pct": playable_pct(hi),
                **{CLASS_LABELS[cls]: policies[cls] for cls in BLOCKER_CLASSES},
                **{f"{cls}_policy": policies[cls] for cls in BLOCKER_CLASSES},
            }
        )
    return rows


def opening_policy_playable_pct(
    r_pct: int,
    *,
    pct_class: int,
    pct_ace: int,
    pct_joker: int,
    joker_through_100: bool,
) -> str:
    """Integer-percent rule: '79%' starts the ace requirement."""
    if r_pct < pct_class:
        return POLICY_OPEN_ALWAYS
    if r_pct < pct_ace:
        return POLICY_ACE_OR_JOKER
    if joker_through_100 or r_pct < pct_joker:
        return POLICY_JOKER_ONLY
    return POLICY_PASS


def playable_lookup_rows(
    stars: dict[str, dict[str, float]],
) -> list[dict[str, Any]]:
    """Integer-percent bands a human can memorize."""
    pct_by_class = {
        cls: {
            "class_avg": playable_pct(stars[cls]["class_avg"]),
            "ace": playable_pct(stars[cls]["ace"]),
            "joker": playable_pct(stars[cls]["joker"]),
            "joker_through_100": stars[cls]["joker"] > 1.0,
        }
        for cls in BLOCKER_CLASSES
    }
    pcts = {0, 100}
    for cls in BLOCKER_CLASSES:
        pcts.add(pct_by_class[cls]["class_avg"])
        pcts.add(pct_by_class[cls]["ace"])
        if not pct_by_class[cls]["joker_through_100"]:
            pcts.add(pct_by_class[cls]["joker"])
    edges = sorted(pcts)
    rows: list[dict[str, Any]] = []
    for lo, hi in zip(edges, edges[1:]):
        r_pct = lo if lo > 0 else 0
        if hi == 100 and lo == 100:
            continue
        policies = {
            cls: opening_policy_playable_pct(
                r_pct,
                pct_class=pct_by_class[cls]["class_avg"],
                pct_ace=pct_by_class[cls]["ace"],
                pct_joker=pct_by_class[cls]["joker"],
                joker_through_100=pct_by_class[cls]["joker_through_100"],
            )
            for cls in BLOCKER_CLASSES
        }
        rows.append(
            {
                "r_lo_pct": lo,
                "r_hi_pct": hi,
                "inclusive_hi": hi == 100,
                "label": f"{lo}–{hi}%" if hi < 100 else f"{lo}–100%",
                **{CLASS_LABELS[cls]: policies[cls] for cls in BLOCKER_CLASSES},
            }
        )
    return rows


def build_open_chart(
    data: dict[str, Any],
    *,
    rates: Sequence[float] | None = None,
) -> dict[str, Any]:
    """Build the CO open chart from locked 0%/100% pins. No live Nash / no new endpoint MC."""
    grid_rates = tuple(rates) if rates is not None else DEFAULT_CHART_RATES
    p_ind_1 = float(data["independent_p_raise_at_r1"])
    world = str(data["meta"].get("world", WORLD))
    by_class: dict[str, Any] = {}
    stars: dict[str, dict[str, float]] = {}
    for cls in BLOCKER_CLASSES:
        flavors: dict[str, Any] = {}
        for flavor in CHART_FLAVORS:
            row = flavor_row(data, cls, flavor)
            flavors[flavor] = flavor_chart(
                row, rates=grid_rates, p_ind_1=p_ind_1, world=world
            )
        r_class = flavors["class_avg"]["r_star"]
        r_ace = flavors["ace"]["r_star"]
        r_joker = flavors["joker"]["r_star"]
        stars[cls] = {
            "class_avg": r_class,
            "ace": r_ace,
            "joker": r_joker,
        }
        policy_0 = opening_policy_at_rate(
            0.0, r_class=r_class, r_ace=r_ace, r_joker=r_joker
        )
        policy_1 = opening_policy_at_rate(
            1.0, r_class=r_class, r_ace=r_ace, r_joker=r_joker
        )
        by_class[cls] = {
            "flavors": flavors,
            "bands": class_bands(r_class=r_class, r_ace=r_ace, r_joker=r_joker),
            "playable_rules": _playable_rules(
                cls,
                r_class=r_class,
                r_ace=r_ace,
                r_joker=r_joker,
                joker_100=flavors["joker"],
            ),
            "policy_at_0pct": policy_0,
            "policy_at_100pct": policy_1,
            "nested_r_star": r_class <= r_ace <= r_joker,
        }
    lookup = combined_lookup_rows(stars)
    playable = playable_lookup_rows(stars)
    jj = by_class["pair_J"]
    qq = by_class["pair_Q"]
    kk = by_class["pair_K"]
    return {
        "note": (
            "Cutoff opening requirements for JJ/QQ/KK vs seats 1–6 slowplay "
            "rate r. Class average = no extra blocker (40k pin). Ace = physical "
            "ace kicker, no bug (10k, reweighted L). Joker = bug as ace kicker, "
            "still pair_X not trips (10k, reweighted L). CO never sandbags."
        ),
        "method": (
            "p_cal(r)=kappa*p_ind(r) with kappa=p_MC(1)/p_ind(1) from the "
            "locked card-removal MC. EV=(1-p)*L+p*(-2). No live draw / "
            "post-draw Nash. No multi-raise. No HJ strategy. No BN vs CO."
        ),
        "world": world,
        "co_never_sandbags": True,
        "mc_pins": {
            "class_avg_n": 40_000,
            "flavor_n": 10_000,
            "n_leaf": 8_000,
            "seed": DEFAULT_MC_SEED,
        },
        "r_grid": list(grid_rates),
        "p_ind_1": p_ind_1,
        "by_class": by_class,
        "lookup_exact": lookup,
        "lookup_playable": playable,
        "answers": {
            "jj_open_always_below": jj["flavors"]["class_avg"]["r_star"],
            "jj_ace_or_joker_below": jj["flavors"]["ace"]["r_star"],
            "jj_joker_only_below": jj["flavors"]["joker"]["r_star"],
            "qq_open_always_below": qq["flavors"]["class_avg"]["r_star"],
            "qq_ace_or_joker_below": qq["flavors"]["ace"]["r_star"],
            "qq_joker_only_below": qq["flavors"]["joker"]["r_star"],
            "kk_open_always_below": kk["flavors"]["class_avg"]["r_star"],
            "kk_ace_or_joker_below": kk["flavors"]["ace"]["r_star"],
            "kk_joker_only_below": kk["flavors"]["joker"]["r_star"],
            "jj_policy_at_100pct": jj["policy_at_100pct"],
            "qq_policy_at_100pct": qq["policy_at_100pct"],
            "kk_policy_at_100pct": kk["policy_at_100pct"],
            "playable_jj_pcts": [
                playable_pct(jj["flavors"]["class_avg"]["r_star"]),
                playable_pct(jj["flavors"]["ace"]["r_star"]),
                playable_pct(jj["flavors"]["joker"]["r_star"]),
            ],
            "playable_qq_pcts": [
                playable_pct(qq["flavors"]["class_avg"]["r_star"]),
                playable_pct(qq["flavors"]["ace"]["r_star"]),
                playable_pct(qq["flavors"]["joker"]["r_star"]),
            ],
            "playable_kk_pcts": [
                playable_pct(kk["flavors"]["class_avg"]["r_star"]),
                playable_pct(kk["flavors"]["ace"]["r_star"]),
                playable_pct(kk["flavors"]["joker"]["r_star"]),
            ],
        },
    }


def merge_chart_into_fixture(path: Path | None = None) -> Path:
    """Keep locked 40k / 10k pins; add the interpolated open chart."""
    path = path or default_fixture_path()
    data = json.loads(path.read_text(encoding="utf-8"))
    data["open_chart"] = build_open_chart(data)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def _policy_cell(policy: str) -> str:
    return {
        POLICY_OPEN_ALWAYS: "open",
        POLICY_ACE_OR_JOKER: "ace or joker",
        POLICY_JOKER_ONLY: "joker only",
        POLICY_PASS: "pass",
    }[policy]


def format_playable_table(chart: dict[str, Any]) -> str:
    lines = [
        "| Slowplay r | JJ | QQ | KK |",
        "| --- | --- | --- | --- |",
    ]
    n = len(chart["lookup_playable"])
    for i, row in enumerate(chart["lookup_playable"]):
        lo, hi = row["r_lo_pct"], row["r_hi_pct"]
        if i == 0:
            band = f"r < {hi}%"
        elif i == n - 1:
            band = f"r ≥ {lo}%"
        else:
            band = f"{lo}–{hi}%"
        lines.append(
            f"| {band} | {_policy_cell(row['JJ'])} | {_policy_cell(row['QQ'])} | "
            f"{_policy_cell(row['KK'])} |"
        )
    return "\n".join(lines)


def _print_chart(chart: dict[str, Any]) -> None:
    print(format_playable_table(chart))
    print()
    for cls in BLOCKER_CLASSES:
        block = chart["by_class"][cls]
        print(f"{CLASS_LABELS[cls]}  0%={block['policy_at_0pct']}  "
              f"100%={block['policy_at_100pct']}")
        for line in block["playable_rules"]:
            print(f"  {line}")
        for flavor in CHART_FLAVORS:
            frow = block["flavors"][flavor]
            print(
                f"  {flavor:10} L={frow['leaf']:+.4f} p(1)={frow['p_mc_1']:.4f} "
                f"r*={frow['r_star']:.4f} ({frow['r_star_playable_pct']}%) "
                f"EV(100%)={frow['ev_open_100pct']:+.4f}"
            )
    a = chart["answers"]
    print(
        "playable pcts JJ={playable_jj_pcts} QQ={playable_qq_pcts} "
        "KK={playable_kk_pcts}".format(**a)
    )


def default_chart_fixture_path() -> Path:
    return default_fixture_path()


def load_open_chart(path: Path | None = None) -> dict[str, Any]:
    data = json.loads((path or default_fixture_path()).read_text(encoding="utf-8"))
    if "open_chart" not in data:
        raise KeyError("fixture has no open_chart; run --write-chart")
    return data["open_chart"]


def main_write_chart(path: Path | None = None) -> Path:
    out = merge_chart_into_fixture(path)
    data = json.loads(out.read_text(encoding="utf-8"))
    print(f"Wrote open_chart into {out}")
    _print_chart(data["open_chart"])
    return out
