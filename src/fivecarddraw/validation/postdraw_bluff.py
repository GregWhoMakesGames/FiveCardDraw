"""Ring 1: post-draw bluff 3-bet indifference on the raise node.

BN always 3-bets flush+, always calls straights, and 3-bets two pair/trips with
frequency β. Caller SF caps; flushes are the call-vs-fold indifference target.
Root-find β so flush EV_call = EV_fold. Report α = air share of 3-bets.

Reuses `play_raise_node` / `on_raise_node` / `family_bucket` / the cap deal
generator. Does not re-grid class × d. Ring 2 (Nash/CFR) is out of scope.

Doc: `docs/NEXT_STAGE_POSTDRAW_BLUFF.md`.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Sequence

from fivecarddraw.validation.bluff_indifference import (
    BLUFF_TWO_PAIR_TRIPS,
    BnPolarMix,
    CALL_3BET,
    CATCHER_FLUSH,
    CallerMix,
    POT_AFTER_3BET,
    POT_ODDS_CALL_3BET,
    RING1_CALLER_CALL_FLUSH,
    RING1_CALLER_FOLD_CATCHERS,
    VALUE_BOAT_PLUS,
    VALUE_FLUSH_PLUS,
    air_share_of_three_bets,
    best_response,
    catcher_evs,
    family_counts,
    indifference_root,
    precompute_raise_node_payoffs,
    strategy_ev,
)
from fivecarddraw.validation.postdraw_betting_m2 import BIG, CAP_POT, PREDRAW_POT
from fivecarddraw.validation.postdraw_cap import (
    EXTRA_BN_CLASSES,
    on_raise_node,
)
from fivecarddraw.validation.postdraw_nonbluff_ev import (
    CALLER_ALL,
    HONEST_POLICY,
    LOCKED_BN_DRAW,
    NonbluffDeal,
    generate_locked_range_deals,
    generate_nonbluff_deals,
)
from fivecarddraw.validation.showdown_matrix import (
    build_opener_inventory,
    load_call_2to1_hands,
)


DEFAULT_SEED = 20260902
DEFAULT_N_RANGE = 40_000
DEFAULT_N_PER_CLASS = 4_000
FLUSH_EV_TOL = 0.05

CALL_IT_DOWN_MIX = BnPolarMix(
    beta=0.0, value_buckets=frozenset(), bluff_buckets=frozenset()
)


def _round_obj(obj: Any) -> Any:
    if isinstance(obj, float):
        return round(obj, 4)
    if isinstance(obj, dict):
        return {k: _round_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round_obj(x) for x in obj]
    return obj


def _indifference_as_dict(result) -> dict[str, Any]:
    c = result.catcher
    return {
        "beta": result.beta,
        "alpha": result.alpha,
        "bracketed": result.bracketed,
        "n_value": result.n_value,
        "n_bluff": result.n_bluff,
        "n_catcher": result.n_catcher,
        "n_catcher_vs_value": result.n_catcher_vs_value,
        "n_catcher_vs_bluff": result.n_catcher_vs_bluff,
        "flush_ev_fold": c.ev_fold,
        "flush_ev_call": c.ev_call,
        "flush_ev_cap": c.ev_cap,
        "flush_call_minus_fold": c.call_minus_fold,
        "flush_n_weight": c.n_weight,
        "f_at_0": result.f_at_0,
        "f_at_1": result.f_at_1,
        "f_at_beta": result.f_at_beta,
    }


def _strategy_as_dict(ev) -> dict[str, Any]:
    return {
        "ev_bn": ev.ev_bn,
        "ev_caller": ev.ev_caller,
        "n": ev.n,
        "p_3bet": ev.p_3bet,
        "p_cap": ev.p_cap,
        "p_fold_3bet": ev.p_fold_3bet,
    }


def _caller_report(
    payoffs, mix: BnPolarMix, bucket: str
) -> dict[str, Any]:
    evs = catcher_evs(payoffs, mix, bucket)
    scored = (
        ("fold", evs.ev_fold),
        ("call", evs.ev_call),
        ("cap", evs.ev_cap),
    )
    best = max(scored, key=lambda kv: kv[1])[0]
    return {
        "bucket": bucket,
        "n_weight": evs.n_weight,
        "ev_fold": evs.ev_fold,
        "ev_call": evs.ev_call,
        "ev_cap": evs.ev_cap,
        "call_minus_fold": evs.call_minus_fold,
        "pure_action": best,
        "still_folds": best == "fold",
        "still_caps": best == "cap",
        "indifferent_call_fold": abs(evs.call_minus_fold) <= FLUSH_EV_TOL
        and best in {"fold", "call"},
    }


def _fine_catcher_rows(
    payoffs, mix: BnPolarMix, *, family: str
) -> list[dict[str, Any]]:
    by_fine: dict[str, list] = defaultdict(list)
    for p in payoffs:
        if p.caller_family != family:
            continue
        by_fine[p.caller_fine].append(p)
    rows = []
    for name, group in sorted(by_fine.items(), key=lambda kv: -len(kv[1])):
        evs = catcher_evs(group, mix, name, caller_key="fine")
        rows.append(
            {
                "bucket": name,
                "n": float(len(group)),
                "n_weight": evs.n_weight,
                "ev_fold": evs.ev_fold,
                "ev_call": evs.ev_call,
                "ev_cap": evs.ev_cap,
                "call_minus_fold": evs.call_minus_fold,
                "source": "extra_plus_weighted",
            }
        )
    return rows


def evaluate_ring1(
    payoffs,
    *,
    value_buckets: frozenset[str] = VALUE_FLUSH_PLUS,
    label: str = "flush+",
) -> dict[str, Any]:
    root = indifference_root(
        None,
        value_buckets=value_buckets,
        bluff_buckets=BLUFF_TWO_PAIR_TRIPS,
        catcher_bucket=CATCHER_FLUSH,
        payoffs=payoffs,
    )
    mix = BnPolarMix(
        beta=root.beta,
        value_buckets=frozenset(value_buckets),
        bluff_buckets=BLUFF_TWO_PAIR_TRIPS,
    )
    no_air = BnPolarMix(
        beta=0.0,
        value_buckets=frozenset(value_buckets),
        bluff_buckets=BLUFF_TWO_PAIR_TRIPS,
    )
    # Joint node EV: at β* flushes are indifferent, so fold vs call matches.
    ev_star_fold = strategy_ev(None, mix, RING1_CALLER_FOLD_CATCHERS, payoffs=payoffs)
    ev_star_call = strategy_ev(None, mix, RING1_CALLER_CALL_FLUSH, payoffs=payoffs)
    ev_call_down = strategy_ev(
        None, CALL_IT_DOWN_MIX, RING1_CALLER_FOLD_CATCHERS, payoffs=payoffs
    )
    ev_no_air_fold = strategy_ev(
        None, no_air, RING1_CALLER_FOLD_CATCHERS, payoffs=payoffs
    )
    # Cap-module "honest" hold: cap SF, call rest (no air).
    call_rest = CallerMix(
        {"straight": "call", "flush": "call", "boat_plus": "cap"}
    )
    ev_no_air_call_rest = strategy_ev(None, no_air, call_rest, payoffs=payoffs)

    alpha, n_value, n_bluff, n_3bet = air_share_of_three_bets(payoffs, mix)
    flush = _caller_report(payoffs, mix, "flush")
    straight = _caller_report(payoffs, mix, "straight")
    boat = _caller_report(payoffs, mix, "boat_plus")
    caller_br = best_response(None, mix, payoffs=payoffs)
    bn_br = best_response(None, RING1_CALLER_FOLD_CATCHERS, payoffs=payoffs)

    return {
        "value_range": label,
        "beta_star": root.beta,
        "alpha_star": alpha,
        "bracketed": root.bracketed,
        "n_value": n_value,
        "n_bluff": n_bluff,
        "n_3bet_mass": n_3bet,
        "indifference": _indifference_as_dict(root),
        "caller_flush": flush,
        "caller_straight": straight,
        "caller_boat_plus": boat,
        "node_ev": {
            "beta_star_flush_folds": _strategy_as_dict(ev_star_fold),
            "beta_star_flush_calls": _strategy_as_dict(ev_star_call),
            "call_it_down": _strategy_as_dict(ev_call_down),
            "no_air_flush_plus_fold_non_sf": _strategy_as_dict(ev_no_air_fold),
            "no_air_flush_plus_call_rest": _strategy_as_dict(ev_no_air_call_rest),
        },
        "delta_ev_bn_vs_call_it_down": ev_star_fold.ev_bn - ev_call_down.ev_bn,
        "delta_ev_bn_vs_no_air_fold_non_sf": (
            ev_star_fold.ev_bn - ev_no_air_fold.ev_bn
        ),
        "delta_ev_bn_vs_no_air_call_rest": (
            ev_star_fold.ev_bn - ev_no_air_call_rest.ev_bn
        ),
        "caller_best_response": caller_br["rows"],
        "bn_best_response_vs_fold_catchers": bn_br["rows"],
    }


def _derive_findings(primary: dict[str, Any], boat_only: dict[str, Any]) -> dict[str, Any]:
    flush = primary["caller_flush"]
    straight = primary["caller_straight"]
    boat = primary["caller_boat_plus"]
    beta = primary["beta_star"]
    alpha = primary["alpha_star"]
    d_no_air = primary["delta_ev_bn_vs_no_air_fold_non_sf"]
    d_cid = primary["delta_ev_bn_vs_call_it_down"]
    return {
        "beta_star": beta,
        "alpha_star": alpha,
        "flush_ev_fold": flush["ev_fold"],
        "flush_ev_call": flush["ev_call"],
        "flush_ev_cap": flush["ev_cap"],
        "flush_call_minus_fold": flush["call_minus_fold"],
        "flush_indifferent": abs(flush["call_minus_fold"]) <= FLUSH_EV_TOL,
        "straight_ev_fold": straight["ev_fold"],
        "straight_ev_call": straight["ev_call"],
        "straight_still_folds": straight["still_folds"],
        "sf_still_caps": boat["still_caps"],
        "node_ev_bn_at_beta_star": primary["node_ev"]["beta_star_flush_folds"]["ev_bn"],
        "node_ev_bn_call_it_down": primary["node_ev"]["call_it_down"]["ev_bn"],
        "node_ev_bn_no_air_flush_plus": primary["node_ev"][
            "no_air_flush_plus_fold_non_sf"
        ]["ev_bn"],
        "node_ev_bn_no_air_call_rest": primary["node_ev"][
            "no_air_flush_plus_call_rest"
        ]["ev_bn"],
        "delta_vs_call_it_down": d_cid,
        "delta_vs_no_air_flush_plus": d_no_air,
        "boat_plus_only_beta_star": boat_only["beta_star"],
        "boat_plus_only_alpha_star": boat_only["alpha_star"],
        "hypothesis_beta_in_unit_interval": 0.0 < beta < 1.0 and primary["bracketed"],
        "hypothesis_flush_indifferent": abs(flush["call_minus_fold"]) <= FLUSH_EV_TOL,
        "hypothesis_straights_still_fold": straight["still_folds"],
        "hypothesis_sf_still_caps": boat["still_caps"],
        "hypothesis_bluff_delta_vs_no_air_positive": d_no_air > 0.0,
        "hypothesis_bluff_delta_vs_call_it_down_positive": d_cid > 0.0,
        "hypothesis_boat_plus_value_needs_more_air": (
            boat_only["alpha_star"] > alpha
        ),
        "nonbluff_grid_excludes_bluff_3bet": True,
        "cap_table_excludes_bluff_3bet": True,
        "pot_odds_call_3bet": POT_ODDS_CALL_3BET,
        "polar_sketch_alpha": (POT_ODDS_CALL_3BET - 0.05) / 0.95,
        "alpha_not_pinned_to_sketch": True,
    }


def run_analysis(
    *,
    n_range: int = DEFAULT_N_RANGE,
    n_per_class: int = DEFAULT_N_PER_CLASS,
    seed: int = DEFAULT_SEED,
    progress: bool = True,
    extra_classes: Sequence[str] | None = EXTRA_BN_CLASSES,
) -> dict[str, Any]:
    if progress:
        print("Loading 2:1 callers + BN opener inventory…")
    callers = load_call_2to1_hands(progress=progress)
    inventory = build_opener_inventory(progress=progress)

    if progress:
        print(f"Combo-weighted locked range ({n_range} deals, {LOCKED_BN_DRAW.name})…")
    weighted = generate_locked_range_deals(
        inventory,
        callers,
        caller_d=1,
        caller_class=CALLER_ALL,
        n_deals=n_range,
        seed=seed,
        draw_policy=LOCKED_BN_DRAW,
    )
    node_weighted = [d for d in weighted if on_raise_node(d)]
    if progress:
        print(f"  raise-node deals: {len(node_weighted)} / {len(weighted)}")

    extra: list[NonbluffDeal] = []
    use_extra = list(extra_classes) if extra_classes else []
    if n_per_class > 0:
        for cls in use_extra:
            if progress:
                print(f"  extra {cls} ({n_per_class} deals, labeled, not in β*)…")
            extra.extend(
                generate_nonbluff_deals(
                    inventory,
                    callers,
                    cls,
                    LOCKED_BN_DRAW.n_draw_for(cls),
                    caller_d=1,
                    caller_class=CALLER_ALL,
                    n_deals=n_per_class,
                    seed=seed + 17 + sum(ord(c) for c in cls),
                )
            )
    node_extra = [d for d in extra if on_raise_node(d)]

    if progress:
        print(f"Precomputing raise-node payoffs ({len(node_weighted)} weighted)…")
    pay_w = precompute_raise_node_payoffs(node_weighted)
    pay_extra = precompute_raise_node_payoffs(node_extra) if node_extra else []
    pay_labeled = pay_w + pay_extra

    if progress:
        print("Root-finding β* (flush EV_call = EV_fold)…")
    primary = evaluate_ring1(pay_w, value_buckets=VALUE_FLUSH_PLUS, label="flush+")
    boat_only = evaluate_ring1(
        pay_w, value_buckets=VALUE_BOAT_PLUS, label="boat+"
    )
    mix_star = BnPolarMix(
        beta=primary["beta_star"],
        value_buckets=VALUE_FLUSH_PLUS,
        bluff_buckets=BLUFF_TWO_PAIR_TRIPS,
    )
    flush_fine = _fine_catcher_rows(pay_labeled, mix_star, family="flush")
    counts_w = family_counts(pay_w)
    findings = _derive_findings(primary, boat_only)

    return {
        "meta": {
            "seed": seed,
            "n_range": len(weighted),
            "n_per_class_extra": n_per_class,
            "n_node_weighted": len(node_weighted),
            "n_node_extra": len(node_extra),
            "predraw_pot": PREDRAW_POT,
            "big_bet": BIG,
            "pot_after_3bet": POT_AFTER_3BET,
            "to_call_3bet": CALL_3BET,
            "pot_odds_call_3bet": POT_ODDS_CALL_3BET,
            "cap_pot": CAP_POT,
            "max_raises_default_m2": 1,
            "max_raises_this_module": 3,
            "matchup": "BN (seat 8) opener vs one 2:1 drawing caller",
            "predraw": "open + call only (no raise)",
            "honest_m2_policy": HONEST_POLICY.key,
            "locked_bn_draw": {
                "name": LOCKED_BN_DRAW.name,
                "pair_d": LOCKED_BN_DRAW.pair_d,
                "two_pair_d": LOCKED_BN_DRAW.two_pair_d,
                "trips_d": LOCKED_BN_DRAW.trips_d,
                "quads_d": LOCKED_BN_DRAW.quads_d,
            },
            "node": "BN two_pair+ (bets) ∩ caller straight+ (raises)",
            "ring": 1,
            "value_3bet": "flush+",
            "bluff_3bet": "two_pair_or_trips mix β",
            "bn_straights": "always call (not mixed)",
            "catcher": "caller flush (call vs fold)",
            "sf": "always cap",
            "doc": "docs/NEXT_STAGE_POSTDRAW_BLUFF.md",
            "regenerate": (
                "analyze-postdraw-bluff --n-range 40000 --n-per-class 4000 --write-fixture"
            ),
            "notes": [
                "β* is root-found on the combo-weighted raise-node sample. Extra "
                "per-class deals fill thin flush cells and are labeled; they do "
                "not enter the root-find.",
                "M2 / non-bluff EV tables stay bet+1. The cap value table is the "
                "no-air baseline; it does not already include bluff 3-bets.",
                "Ring 2 (bucketed Nash / CFR) is out of scope.",
            ],
        },
        "family_counts_weighted": counts_w,
        "primary": primary,
        "sensitivity_boat_plus_only": boat_only,
        "caller_flush_fine_labeled": flush_fine,
        "findings": findings,
    }


def build_summary_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return _round_obj(
        {
            "meta": payload["meta"],
            "family_counts_weighted": payload["family_counts_weighted"],
            "primary": {
                k: payload["primary"][k]
                for k in (
                    "value_range",
                    "beta_star",
                    "alpha_star",
                    "bracketed",
                    "n_value",
                    "n_bluff",
                    "n_3bet_mass",
                    "indifference",
                    "caller_flush",
                    "caller_straight",
                    "caller_boat_plus",
                    "node_ev",
                    "delta_ev_bn_vs_call_it_down",
                    "delta_ev_bn_vs_no_air_fold_non_sf",
                    "delta_ev_bn_vs_no_air_call_rest",
                    "caller_best_response",
                    "bn_best_response_vs_fold_catchers",
                )
            },
            "sensitivity_boat_plus_only": {
                k: payload["sensitivity_boat_plus_only"][k]
                for k in (
                    "value_range",
                    "beta_star",
                    "alpha_star",
                    "bracketed",
                    "n_value",
                    "n_bluff",
                    "n_3bet_mass",
                    "caller_flush",
                    "delta_ev_bn_vs_call_it_down",
                    "delta_ev_bn_vs_no_air_fold_non_sf",
                )
            },
            "caller_flush_fine_labeled": payload["caller_flush_fine_labeled"],
            "findings": payload["findings"],
        }
    )


def write_markdown_summary(payload: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = payload if "findings" in payload else build_summary_payload(payload)
    f = summary["findings"]
    meta = summary["meta"]
    p = summary["primary"]
    s = summary["sensitivity_boat_plus_only"]
    counts = summary["family_counts_weighted"]
    lines = [
        "# Post-draw bluff 3-bet (Ring 1 indifference)",
        "",
        f"BN vs one 2:1 caller on the raise node. Seed `{meta['seed']}`, "
        f"`{meta['n_range']}` combo-weighted deals "
        f"({meta['n_node_weighted']} on the node). After a 3-bet the pot is "
        f"${meta['pot_after_3bet']:.0f} with ${meta['to_call_3bet']:.0f} to call "
        f"(break-even {meta['pot_odds_call_3bet']:.4f} = 4/30).",
        "",
        "The non-bluff class × d table and the cap value table do **not** "
        "already include bluff 3-bets. This is the polar mix on that node.",
        "",
        "Doc: `docs/NEXT_STAGE_POSTDRAW_BLUFF.md`.",
        "",
        "## Family mass (combo-weighted node)",
        "",
        "| Side | Family | n |",
        "| --- | --- | ---: |",
    ]
    for fam, n in sorted(counts["bn"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| BN | {fam} | {n:.0f} |")
    for fam, n in sorted(counts["caller"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| caller | {fam} | {n:.0f} |")
    lines += [
        "",
        "## β* (root-find; flush EV_call = EV_fold)",
        "",
        f"- **β\\*** = P(3-bet | two pair or trips) = **{f['beta_star']:.4f}**",
        f"- **α\\*** = air share of 3-bets = **{f['alpha_star']:.4f}**",
        f"- Polar sketch (not pinned): α ≈ {f['polar_sketch_alpha']:.3f} "
        "given ~5% flush equity vs a pure flush+ range.",
        f"- Bracketed in (0, 1): **{p['bracketed']}**",
        "",
        "## Caller vs the 3-bet at β* (3-bet subtree)",
        "",
        "| Bucket | n_weight | EV fold | EV call | EV cap | Δ call−fold | Action |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in (p["caller_flush"], p["caller_straight"], p["caller_boat_plus"]):
        lines.append(
            f"| {row['bucket']} | {row['n_weight']:.1f} | {row['ev_fold']:.3f} | "
            f"{row['ev_call']:.3f} | {row['ev_cap']:.3f} | "
            f"{row['call_minus_fold']:+.3f} | {row['pure_action']} |"
        )
    lines += [
        "",
        "Fine flush cells (weighted + extra; labeled, not used for β*):",
        "",
        "| Flush | n | EV fold | EV call | Δ call−fold |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for r in summary["caller_flush_fine_labeled"]:
        lines.append(
            f"| {r['bucket']} | {r['n']:.0f} | {r['ev_fold']:.3f} | "
            f"{r['ev_call']:.3f} | {r['call_minus_fold']:+.3f} |"
        )
    nev = p["node_ev"]
    lines += [
        "",
        "## Node EV_bn (combo-weighted)",
        "",
        "| Line | EV_bn | Δ vs call-it-down |",
        "| --- | ---: | ---: |",
        f"| Call-it-down | {nev['call_it_down']['ev_bn']:.4f} | 0 |",
        f"| No-air flush+ 3-bet / fold non-SF | "
        f"{nev['no_air_flush_plus_fold_non_sf']['ev_bn']:.4f} | "
        f"{nev['no_air_flush_plus_fold_non_sf']['ev_bn'] - nev['call_it_down']['ev_bn']:+.4f} |",
        f"| No-air flush+ 3-bet / call rest (cap SF) | "
        f"{nev['no_air_flush_plus_call_rest']['ev_bn']:.4f} | "
        f"{nev['no_air_flush_plus_call_rest']['ev_bn'] - nev['call_it_down']['ev_bn']:+.4f} |",
        f"| β* polar (flush fold ≡ call) | "
        f"{nev['beta_star_flush_folds']['ev_bn']:.4f} | "
        f"{p['delta_ev_bn_vs_call_it_down']:+.4f} |",
        "",
        f"Bluff delta vs no-air flush+ 3-bet (fold non-SF): "
        f"**{p['delta_ev_bn_vs_no_air_fold_non_sf']:+.4f}**.",
        "",
        "## Sensitivity: value range = boat+ only",
        "",
        f"β* = {s['beta_star']:.4f}, α* = {s['alpha_star']:.4f} "
        f"(more air than flush+ value: {s['alpha_star'] > p['alpha_star']}).",
        "",
        "## Hypotheses",
        "",
        f"- β* ∈ (0, 1): **{f['hypothesis_beta_in_unit_interval']}** "
        f"(β={f['beta_star']:.4f})",
        f"- Flush call ≈ fold (±{FLUSH_EV_TOL} chips): "
        f"**{f['hypothesis_flush_indifferent']}** "
        f"(Δ={f['flush_call_minus_fold']:.4f})",
        f"- Straights still fold: **{f['hypothesis_straights_still_fold']}**",
        f"- SF still caps: **{f['hypothesis_sf_still_caps']}**",
        f"- Bluff delta vs no-air flush+ > 0: "
        f"**{f['hypothesis_bluff_delta_vs_no_air_positive']}** "
        f"({f['delta_vs_no_air_flush_plus']:+.4f})",
        f"- Bluff delta vs call-it-down > 0: "
        f"**{f['hypothesis_bluff_delta_vs_call_it_down_positive']}** "
        f"({f['delta_vs_call_it_down']:+.4f})",
        f"- Boat+-only value needs more air: "
        f"**{f['hypothesis_boat_plus_value_needs_more_air']}**",
        "",
        "Do **not** substitute these for the §3.4 class × d cells or the §3.5 "
        "cap value table. Ring 2 Nash is a later ticket.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def default_summary_fixture_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "validation"
        / "postdraw_bluff_summary.json"
    )


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

    parser = argparse.ArgumentParser(
        description=(
            "Ring 1: root-find BN two-pair/trips 3-bet frequency so caller "
            "flushes are indifferent to calling the 3-bet"
        )
    )
    parser.add_argument("--n-range", type=int, default=DEFAULT_N_RANGE)
    parser.add_argument("--n-per-class", type=int, default=DEFAULT_N_PER_CLASS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--quick", action="store_true", help="Tiny sample for smoke runs")
    parser.add_argument("-o", "--output", type=Path, default=None)
    parser.add_argument(
        "--write-fixture",
        action="store_true",
        help="Refresh tests/fixtures/validation/postdraw_bluff_summary.json",
    )
    args = parser.parse_args()
    n_range = 2_000 if args.quick else args.n_range
    n_class = 0 if args.quick else args.n_per_class
    extra = EXTRA_BN_CLASSES if n_class else []
    payload = run_analysis(
        n_range=n_range,
        n_per_class=n_class,
        seed=args.seed,
        progress=True,
        extra_classes=extra,
    )
    out = args.output or Path("outputs/validation/postdraw_bluff.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out}")
    md = out.with_suffix(".md")
    write_markdown_summary(payload, md)
    print(f"Wrote {md}")
    if args.write_fixture:
        fix = write_summary_fixture(payload)
        print(f"Wrote fixture {fix}")
    print()
    f = payload["findings"]
    print(
        f"β*={f['beta_star']:.4f}  α*={f['alpha_star']:.4f}  "
        f"flush Δ={f['flush_call_minus_fold']:+.4f}  "
        f"straight folds={f['straight_still_folds']}  "
        f"Δ vs no-air={f['delta_vs_no_air_flush_plus']:+.4f}  "
        f"Δ vs call-it-down={f['delta_vs_call_it_down']:+.4f}"
    )


if __name__ == "__main__":
    main()
