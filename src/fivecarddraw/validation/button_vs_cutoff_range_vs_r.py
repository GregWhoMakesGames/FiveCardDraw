"""BN-vs-CO: decompose the two signed switches into CO range vs 1–6 trap rate.

Frame: ``button_vs_cutoff_range_vs_r``
(docs/research/button_vs_cutoff_range_vs_r.md). Ticket item 1:
docs/NEXT_STAGE_CO_OPEN_CONSIDERATIONS.md.

The signed lookup maps table slowplay *r* → *ideal* CO chart range → BN
action. Those BN-vs-CO labs are **HU vs the constructed range** (trap weight
0 at BN's fold/call/raise node). Real CO may open a different range than the
chart at that *r*, and seats 1–6 may still raise after CO opens.

This module holds one factor fixed and varies the other. It **reuses locked
fixtures** (polar + interior BN-vs-CO leaves, CO open-chart kappa, sandbag
world ``co_vs_seats_1_6``). It does **not** rebuild post-draw Nash, restart
the open chart, restart the polar labs, or mix-solve a raise tree.

Primary action rule (no multi-raise):

- Call line mixes ``(1 − p(r)) · EV_call_HU(range) + p(r) · trap_call_leaf``.
- Raise line stays the HU checkdown vs CO (a 1–6 3-bet is the later
  multi-raise ticket).
- ``p_win`` stays HU vs CO. Value-raise iff favorite and raise-cd +EV.
- Same ``recommend_action`` helper as the tight / chart labs.

Trap-call leaves (AA / two pair do not assume fold in sandbag_v1):

- ``fold_bound`` = −$2 (even folding the 1–6 raise after the $2 call).
- ``tight_proxy`` = tight-polar HU call EV (optimistic: the trap set is
  two pair+ / HJ aces, stronger than tight CO).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Sequence

from fivecarddraw.validation.button_vs_cutoff_tight import (
    CALL_INVEST,
    FOLD_EV,
    RAISE_INVEST,
    RAISE_POT,
    recommend_action,
)
from fivecarddraw.validation.cutoff_open_sandbag import (
    WORLD,
    calibrated_p_raise_at_rate,
    independent_p_raise_at_rate,
    load_fixture as load_co_sandbag_fixture,
)
from fivecarddraw.validation.sandbag_v1 import FOLD_JJ_TO_RAISE_EV


FRAME = "button_vs_cutoff_range_vs_r"
FOCUS_BN = ("pair_A", "two_pair")
TRAP_RATES_PCT: tuple[int, ...] = (0, 79, 86, 87, 96, 100)
# Chart-range at the wrong r, and the two polars as non-chart endpoints.
CROSS_RANGES: tuple[str, ...] = (
    "all_legal",
    "r79",
    "r86",
    "r87",
    "tight",
)
PRIMARY_TRAP_LEAF = "fold_bound"
PROXY_TRAP_LEAF = "tight_proxy"
# Folding a 3-bet after BN invested $4. Out of scope (multi-raise); sensitivity only.
FOLD_TO_THREEBET_EV = -RAISE_INVEST

RANGE_FILES: dict[str, str] = {
    "all_legal": "button_vs_cutoff_all_legal.json",
    "r79": "button_vs_cutoff_r79.json",
    "r84": "button_vs_cutoff_r84.json",
    "r86": "button_vs_cutoff_r86.json",
    "r87": "button_vs_cutoff_r87.json",
    "r90": "button_vs_cutoff_r90.json",
    "r93": "button_vs_cutoff_r93.json",
    "r96": "button_vs_cutoff_r96.json",
    "tight": "button_vs_cutoff_tight.json",
}

# Chart r the range belongs to. Polars: 0% all-legal, ~100% tight.
RANGE_CHART_R_PCT: dict[str, int] = {
    "all_legal": 0,
    "r79": 79,
    "r84": 84,
    "r86": 86,
    "r87": 87,
    "r90": 90,
    "r93": 93,
    "r96": 96,
    "tight": 100,
}

RANGE_LABELS: dict[str, str] = {
    "all_legal": "all legal (chart at r=0%)",
    "r79": "chart r=79% (JJ ace/joker; QQ/KK any)",
    "r84": "chart r=84%",
    "r86": "chart r=86% (KK still any kicker)",
    "r87": "chart r=87% (KK needs ace/joker)",
    "r90": "chart r=90%",
    "r93": "chart r=93%",
    "r96": "chart r=96% (matches tight polar)",
    "tight": "tight polar (AA+ plus QQ/KK+joker)",
}


def fixtures_dir() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "validation"
    )


def default_fixture_path() -> Path:
    return fixtures_dir() / f"{FRAME}.json"


def load_range_fixture(slug: str) -> dict[str, Any]:
    try:
        name = RANGE_FILES[slug]
    except KeyError as exc:
        raise KeyError(f"unknown CO range slug {slug!r}") from exc
    path = fixtures_dir() / name
    return json.loads(path.read_text(encoding="utf-8"))


def _row_key(row: dict[str, Any]) -> str | None:
    if "key" in row:
        return str(row["key"])
    if "bn_spec" in row:
        return str(row["bn_spec"])
    if row.get("flavor", "class") == "class" and "bn_class" in row:
        return str(row["bn_class"])
    return None


def extract_hu_cell(payload: dict[str, Any], bn_key: str) -> dict[str, Any]:
    """Class-average HU cell for ``bn_key`` from a locked BN-vs-CO fixture."""
    rows: Iterable[dict[str, Any]]
    if "by_row" in payload:
        rows = payload["by_row"]
    elif "by_spec" in payload:
        rows = payload["by_spec"]
    else:
        raise KeyError("fixture has neither by_row nor by_spec")
    for row in rows:
        if _row_key(row) != bn_key:
            continue
        if row.get("flavor") not in (None, "class"):
            continue
        rec = row.get("recommend") or row.get("recommend_tight_rule") or {}
        action = rec.get("action") or row.get("action")
        return {
            "bn_class": bn_key,
            "n": float(row["n"]),
            "ev_call": float(row["ev_call"]),
            "se_call": float(row["se_call"]),
            "ev_raise_checkdown": float(row["ev_raise_checkdown"]),
            "se_raise_checkdown": float(
                row.get("se_raise_checkdown") or row.get("se_raise_cd") or 0.0
            ),
            "p_bn_wins_final": float(row["p_bn_wins_final"]),
            "hu_action": str(action),
        }
    raise KeyError(f"no class-average cell for {bn_key!r}")


def signed_hu_action(cell: dict[str, Any]) -> str:
    rec = recommend_action(
        ev_call=float(cell["ev_call"]),
        ev_raise=float(cell["ev_raise_checkdown"]),
        se_call=float(cell["se_call"]),
        se_raise=float(cell["se_raise_checkdown"]),
        p_bn_win=float(cell["p_bn_wins_final"]),
    )
    return str(rec["action"])


def chart_kappa(sandbag: dict[str, Any] | None = None) -> dict[str, float]:
    """Locked JJ class-average kappa from the CO sandbag fixture. No new MC."""
    data = sandbag if sandbag is not None else load_co_sandbag_fixture()
    p_ind_1 = float(data["independent_p_raise_at_r1"])
    jj = next(r for r in data["by_class"] if r["co_class"] == "pair_J")
    p_mc_1 = float(jj["p_raise"])
    return {
        "p_ind_1": p_ind_1,
        "p_mc_1_jj": p_mc_1,
        "kappa": p_mc_1 / p_ind_1,
        "world": str(data["meta"].get("world", WORLD)),
        "jj_leaf": float(jj["ev_no_raise_leaf"]),
    }


def p_trap_at_rate_pct(r_pct: int, *, kappa: float, world: str = WORLD) -> dict[str, float]:
    r = r_pct / 100.0
    p_ind = independent_p_raise_at_rate(r, world=world)
    p_cal = calibrated_p_raise_at_rate(r, kappa=kappa, world=world) if r > 0.0 else 0.0
    if r_pct >= 100:
        p_cal = calibrated_p_raise_at_rate(1.0, kappa=kappa, world=world)
        p_ind = independent_p_raise_at_rate(1.0, world=world)
    return {
        "r_pct": int(r_pct),
        "r": round(r_pct / 100.0 if r_pct < 100 else 1.0, 5),
        "p_ind": round(p_ind, 5),
        "p_trap": round(p_cal, 5),
    }


def mix_call(ev_hu: float, p_trap: float, trap_leaf: float) -> float:
    return (1.0 - p_trap) * ev_hu + p_trap * trap_leaf


def mix_se(se_hu: float, p_trap: float) -> float:
    """Trap leaf is a constant bound; SE scales with the HU piece only."""
    return (1.0 - p_trap) * se_hu


def trap_call_leaf(bn_key: str, kind: str, tight_cells: dict[str, dict[str, Any]]) -> float:
    if kind == PRIMARY_TRAP_LEAF:
        return FOLD_JJ_TO_RAISE_EV
    if kind == PROXY_TRAP_LEAF:
        return float(tight_cells[bn_key]["ev_call"])
    raise ValueError(f"unknown trap leaf {kind!r}")


def decide_no_multiraise(
    *,
    ev_call_mixed: float,
    se_call_mixed: float,
    ev_raise_hu: float,
    se_raise_hu: float,
    p_win_hu: float,
) -> dict[str, Any]:
    rec = recommend_action(
        ev_call=ev_call_mixed,
        ev_raise=ev_raise_hu,
        se_call=se_call_mixed,
        se_raise=se_raise_hu,
        p_bn_win=p_win_hu,
    )
    rec["raise_line"] = "hu_vs_co_no_multiraise"
    return rec


def decide_fold_threebet(
    *,
    ev_call_mixed: float,
    se_call_mixed: float,
    ev_raise_hu: float,
    se_raise_hu: float,
    p_trap: float,
    p_win_hu: float,
) -> dict[str, Any]:
    """Sensitivity only: mix the raise line with fold-to-3-bet = −$4."""
    ev_raise = mix_call(ev_raise_hu, p_trap, FOLD_TO_THREEBET_EV)
    rec = recommend_action(
        ev_call=ev_call_mixed,
        ev_raise=ev_raise,
        se_call=se_call_mixed,
        se_raise=mix_se(se_raise_hu, p_trap),
        p_bn_win=p_win_hu,
    )
    rec["raise_line"] = "fold_to_threebet_out_of_scope"
    rec["ev_raise_mixed"] = round(ev_raise, 5)
    return rec


def _round_cell(cell: dict[str, Any]) -> dict[str, Any]:
    out = dict(cell)
    for k in (
        "ev_call",
        "se_call",
        "ev_raise_checkdown",
        "se_raise_checkdown",
        "p_bn_wins_final",
        "ev_call_mixed",
        "se_call_mixed",
        "p_trap",
        "trap_leaf",
        "ev_raise_mixed",
    ):
        if k in out and isinstance(out[k], float):
            out[k] = round(float(out[k]), 5)
    return out


def cross_cell(
    hu: dict[str, Any],
    *,
    p_trap: float,
    trap_leaf: float,
    trap_kind: str,
    range_slug: str,
    r_pct: int,
) -> dict[str, Any]:
    ev_call_m = mix_call(hu["ev_call"], p_trap, trap_leaf)
    se_call_m = mix_se(hu["se_call"], p_trap)
    rec = decide_no_multiraise(
        ev_call_mixed=ev_call_m,
        se_call_mixed=se_call_m,
        ev_raise_hu=hu["ev_raise_checkdown"],
        se_raise_hu=hu["se_raise_checkdown"],
        p_win_hu=hu["p_bn_wins_final"],
    )
    sens = decide_fold_threebet(
        ev_call_mixed=ev_call_m,
        se_call_mixed=se_call_m,
        ev_raise_hu=hu["ev_raise_checkdown"],
        se_raise_hu=hu["se_raise_checkdown"],
        p_trap=p_trap,
        p_win_hu=hu["p_bn_wins_final"],
    )
    return _round_cell(
        {
            "bn_class": hu["bn_class"],
            "co_range": range_slug,
            "trap_r_pct": r_pct,
            "p_trap": p_trap,
            "trap_leaf_kind": trap_kind,
            "trap_leaf": trap_leaf,
            "ev_call_hu": hu["ev_call"],
            "ev_call_mixed": ev_call_m,
            "se_call_mixed": se_call_m,
            "ev_raise_hu": hu["ev_raise_checkdown"],
            "p_bn_wins_final": hu["p_bn_wins_final"],
            "hu_action": hu["hu_action"],
            "action": rec["action"],
            "recommend": rec,
            "fold_threebet_action": sens["action"],
            "fold_threebet": sens,
        }
    )


def _action_at(
    grid: dict[str, dict[str, Any]],
    bn_key: str,
    range_slug: str,
    r_pct: int,
    trap_kind: str,
) -> str:
    return str(grid[f"{bn_key}|{range_slug}|{r_pct}|{trap_kind}"]["action"])


def derive_answers(
    *,
    hu_by_range: dict[str, dict[str, dict[str, Any]]],
    grid: dict[str, dict[str, Any]],
    p_by_r: dict[int, dict[str, float]],
) -> dict[str, Any]:
    """Attribution for the two signed switches. No lookup rewrite."""

    def act(bn: str, rng: str, r: int, kind: str = PRIMARY_TRAP_LEAF) -> str:
        return _action_at(grid, bn, rng, r, kind)

    aa_range_only = act("pair_A", "r79", 0)
    aa_trap_only = act("pair_A", "all_legal", 79)
    aa_both = act("pair_A", "r79", 79)
    aa_loose_at_79 = act("pair_A", "all_legal", 79)
    aa_tight_at_0 = act("pair_A", "tight", 0)

    tp_range_only = act("two_pair", "r87", 0)
    tp_trap_only = act("two_pair", "r86", 87)
    tp_both = act("two_pair", "r87", 87)
    tp_both_proxy = act("two_pair", "r87", 87, PROXY_TRAP_LEAF)
    tp_loose_at_87 = act("two_pair", "all_legal", 87)
    tp_tight_at_0 = act("two_pair", "tight", 0)

    aa_hu_0 = hu_by_range["all_legal"]["pair_A"]["hu_action"]
    aa_hu_79 = hu_by_range["r79"]["pair_A"]["hu_action"]
    tp_hu_86 = hu_by_range["r86"]["two_pair"]["hu_action"]
    tp_hu_87 = hu_by_range["r87"]["two_pair"]["hu_action"]

    aa_range_flips = aa_hu_0 == "raise" and aa_range_only == "fold"
    aa_trap_flips = aa_hu_0 == "raise" and aa_trap_only != "raise"
    tp_range_flips = tp_hu_86 == "raise" and tp_range_only == "call"
    tp_trap_flips = tp_hu_86 == "raise" and tp_trap_only != "raise"

    # fold_bound on the *matching* r=87 two-pair call can go fold (pessimistic).
    tp_matching_fold_bound = tp_both
    lookup_row_added = False

    return {
        "aa_signed_from": aa_hu_0,
        "aa_signed_to": aa_hu_79,
        "aa_range_only_r79_at_trap0": aa_range_only,
        "aa_trap_only_all_legal_at_r79": aa_trap_only,
        "aa_coupled_r79_range_at_r79": aa_both,
        "aa_loose_co_all_legal_at_r79": aa_loose_at_79,
        "aa_tight_co_at_r0": aa_tight_at_0,
        "aa_switch_is_range": aa_range_flips,
        "aa_switch_is_trap": aa_trap_flips,
        "two_pair_signed_from": tp_hu_86,
        "two_pair_signed_to": tp_hu_87,
        "two_pair_range_only_r87_at_trap0": tp_range_only,
        "two_pair_trap_only_r86_at_r87": tp_trap_only,
        "two_pair_coupled_r87_range_at_r87_fold_bound": tp_matching_fold_bound,
        "two_pair_coupled_r87_range_at_r87_tight_proxy": tp_both_proxy,
        "two_pair_loose_co_all_legal_at_r87": tp_loose_at_87,
        "two_pair_tight_co_at_r0": tp_tight_at_0,
        "two_pair_switch_is_range": tp_range_flips,
        "two_pair_switch_is_trap": tp_trap_flips,
        "lookup_row_added": lookup_row_added,
        "p_trap_79": round(p_by_r[79]["p_trap"], 5),
        "p_trap_86": round(p_by_r[86]["p_trap"], 5),
        "p_trap_87": round(p_by_r[87]["p_trap"], 5),
        "headline": (
            "Both signed switches are CO range, not 1–6 trap rate. "
            "Chart-range at trap=0 already flips AA (r79) and two pair (r87). "
            "All-legal CO at r=79% still value-raises AA; r=86% CO at r=87% "
            "still value-raises two pair. No lookup row."
        ),
        "note": (
            "Primary mix: fold-bound −$2 on the call line only; raise stays HU "
            "(no multi-raise). tight_proxy is an optimistic vs-trap call leaf. "
            "fold_threebet on the raise line is sensitivity, not product."
        ),
    }


def build_range_vs_r_payload(
    *,
    ranges: Sequence[str] | None = None,
    trap_rates: Sequence[int] | None = None,
) -> dict[str, Any]:
    use_ranges = list(ranges) if ranges is not None else list(CROSS_RANGES)
    use_rates = list(trap_rates) if trap_rates is not None else list(TRAP_RATES_PCT)
    # Always need tight cells for the proxy leaf, and the switch endpoints.
    load_slugs = sorted(set(use_ranges) | {"tight", "all_legal", "r79", "r86", "r87"})
    fixtures = {slug: load_range_fixture(slug) for slug in load_slugs}
    hu_by_range: dict[str, dict[str, dict[str, Any]]] = {}
    for slug in load_slugs:
        hu_by_range[slug] = {
            bn: extract_hu_cell(fixtures[slug], bn) for bn in FOCUS_BN
        }
        for bn, cell in hu_by_range[slug].items():
            recomputed = signed_hu_action(cell)
            cell["recommend_action"] = recomputed
            cell["recommend_matches_fixture"] = recomputed == cell["hu_action"]
    kappa_info = chart_kappa()
    kappa = float(kappa_info["kappa"])
    world = str(kappa_info["world"])
    p_by_r = {
        r: p_trap_at_rate_pct(r, kappa=kappa, world=world) for r in use_rates
    }
    tight_cells = hu_by_range["tight"]
    grid: dict[str, dict[str, Any]] = {}
    for slug in use_ranges:
        for r_pct in use_rates:
            p = float(p_by_r[r_pct]["p_trap"])
            for bn in FOCUS_BN:
                hu = hu_by_range[slug][bn]
                for kind in (PRIMARY_TRAP_LEAF, PROXY_TRAP_LEAF):
                    leaf = trap_call_leaf(bn, kind, tight_cells)
                    cell = cross_cell(
                        hu,
                        p_trap=p,
                        trap_leaf=leaf,
                        trap_kind=kind,
                        range_slug=slug,
                        r_pct=r_pct,
                    )
                    grid[f"{bn}|{slug}|{r_pct}|{kind}"] = cell
    answers = derive_answers(hu_by_range=hu_by_range, grid=grid, p_by_r=p_by_r)
    hu_view = {
        slug: {bn: _round_cell(dict(cell)) for bn, cell in by_bn.items()}
        for slug, by_bn in hu_by_range.items()
        if slug in set(use_ranges) | {"tight"}
    }
    return {
        "meta": {
            "frame": FRAME,
            "item": "docs/NEXT_STAGE_CO_OPEN_CONSIDERATIONS.md §1",
            "doc": f"docs/research/{FRAME}.md",
            "world": world,
            "kappa": kappa_info,
            "accounting": {
                "fold": FOLD_EV,
                "call_invest": CALL_INVEST,
                "raise_invest": RAISE_INVEST,
                "raise_pot": RAISE_POT,
                "fold_to_raise_call": FOLD_JJ_TO_RAISE_EV,
                "fold_to_threebet": FOLD_TO_THREEBET_EV,
                "primary": (
                    "call mixes trap; raise is HU vs CO; no multi-raise Nash"
                ),
            },
            "co_never_sandbags": True,
            "bug": "ace kicker, not trips",
            "reuse": [
                "button_vs_cutoff*.json locked HU leaves",
                "cutoff_open_sandbag_v1.json kappa / p_ind(1)",
                "sandbag world co_vs_seats_1_6",
                "recommend_action from button_vs_cutoff_tight",
            ],
            "out_of_scope": [
                "BN bluff-raises",
                "multi-raise Nash",
                "draw / post-draw Nash",
                "HJ mixes",
                "3:1 / 4:1 inventory",
                "pair concealment",
                "Ring 1",
                "UTG re-solve",
                "restart CO open chart / polar labs / threshold lookup",
            ],
            "regenerate": (
                "python -m fivecarddraw.validation.button_vs_cutoff_range_vs_r "
                "--write-fixture"
            ),
        },
        "p_trap_by_r": {str(k): v for k, v in p_by_r.items()},
        "hu_by_range": hu_view,
        "range_labels": {k: RANGE_LABELS[k] for k in hu_view},
        "range_chart_r_pct": {k: RANGE_CHART_R_PCT[k] for k in hu_view},
        "cross": list(grid.values()),
        "answers": answers,
    }


def write_summary_fixture(
    payload: dict[str, Any], path: Path | None = None
) -> Path:
    path = path or default_fixture_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def load_summary_fixture(path: Path | None = None) -> dict[str, Any]:
    path = path or default_fixture_path()
    return json.loads(path.read_text(encoding="utf-8"))


def write_markdown_summary(payload: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    a = payload["answers"]
    p79 = payload["p_trap_by_r"]["79"]["p_trap"]
    p87 = payload["p_trap_by_r"]["87"]["p_trap"]
    lines = [
        f"# {FRAME}",
        "",
        a["headline"],
        "",
        f"p_trap(79%)={p79:.4f}; p_trap(87%)={p87:.4f} (JJ-kappa curve).",
        "",
        "## AA raise→fold",
        "",
        f"- Signed: {a['aa_signed_from']} → {a['aa_signed_to']}",
        f"- Range-only (r79 CO, trap 0): **{a['aa_range_only_r79_at_trap0']}**",
        f"- Trap-only (all-legal CO, trap 79%): **{a['aa_trap_only_all_legal_at_r79']}**",
        f"- Range is the switch: {a['aa_switch_is_range']}; "
        f"trap flips it: {a['aa_switch_is_trap']}",
        "",
        "## Two pair raise→call",
        "",
        f"- Signed: {a['two_pair_signed_from']} → {a['two_pair_signed_to']}",
        f"- Range-only (r87 CO, trap 0): **{a['two_pair_range_only_r87_at_trap0']}**",
        f"- Trap-only (r86 CO, trap 87%): **{a['two_pair_trap_only_r86_at_r87']}**",
        f"- Matching fold-bound call mix: **{a['two_pair_coupled_r87_range_at_r87_fold_bound']}**",
        f"- Matching tight-proxy call mix: **{a['two_pair_coupled_r87_range_at_r87_tight_proxy']}**",
        f"- Range is the switch: {a['two_pair_switch_is_range']}; "
        f"trap flips it: {a['two_pair_switch_is_trap']}",
        "",
        f"Lookup row added: {a['lookup_row_added']}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(
        description=(
            "Decompose BN-vs-CO AA / two-pair switches into CO range vs "
            "1–6 trap rate (locked leaves only)"
        )
    )
    p.add_argument("-o", "--output-dir", type=Path, default=None)
    p.add_argument("--write-fixture", action="store_true")
    args = p.parse_args()
    payload = build_range_vs_r_payload()
    out_dir = args.output_dir or Path("outputs/validation")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{FRAME}.json"
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
    print(a["headline"])
    print(
        f"  AA range-only {a['aa_range_only_r79_at_trap0']}  "
        f"trap-only {a['aa_trap_only_all_legal_at_r79']}  "
        f"range? {a['aa_switch_is_range']} trap? {a['aa_switch_is_trap']}"
    )
    print(
        f"  two_pair range-only {a['two_pair_range_only_r87_at_trap0']}  "
        f"trap-only {a['two_pair_trap_only_r86_at_r87']}  "
        f"range? {a['two_pair_switch_is_range']} trap? {a['two_pair_switch_is_trap']}"
    )
    print(f"  lookup_row_added={a['lookup_row_added']}")


if __name__ == "__main__":
    main()
