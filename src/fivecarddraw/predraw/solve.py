"""Orchestrate pre-draw solve stages with progress and CSV output."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from fivecarddraw.abstraction import AbstractionTable, audit_abstraction, build_abstraction
from fivecarddraw.predraw.model import extract_features
from fivecarddraw.predraw.opening import opening_summary, solve_opening
from fivecarddraw.predraw.raise_tree import compare_raise_caps, solve_raise_tree
from fivecarddraw.predraw.response import solve_responses
from fivecarddraw.report import print_table, strategy_df_from_records, write_csv
from fivecarddraw.rules import DEFAULT_CONFIG, GameConfig, SEAT_NAMES


def run_predraw_solve(
    output_dir: Path,
    config: GameConfig = DEFAULT_CONFIG,
    show_progress: bool = True,
    skip_abstraction_cache: bool = False,
) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timings: dict[str, float] = {}

    cache_path = output_dir / "abstraction_cache.json"
    table: AbstractionTable | None = None

    t0 = time.perf_counter()
    if cache_path.exists() and not skip_abstraction_cache:
        table = _load_abstraction_cache(cache_path)
        if show_progress:
            print(f"Loaded abstraction cache: {table.num_buckets} buckets")
    if table is None:
        table = build_abstraction(include_bug=config.include_bug, progress=show_progress)
        _save_abstraction_cache(cache_path, table)
    timings["abstraction_sec"] = time.perf_counter() - t0

    audit_text = audit_abstraction(table)
    (output_dir / "abstraction_audit.txt").write_text(audit_text + "\n", encoding="utf-8")
    if show_progress:
        print(audit_text)

    feat = extract_features(table)

    t1 = time.perf_counter()
    opening = solve_opening(feat, config, show_progress=show_progress)
    timings["opening_sec"] = time.perf_counter() - t1
    open_df = strategy_df_from_records(opening.records)
    write_csv(open_df, output_dir / "opening_by_seat.csv")
    summary_df = strategy_df_from_records(opening_summary(opening, feat, config))
    write_csv(summary_df, output_dir / "opening_summary.csv")
    readable_df = _opening_readable_chart(open_df)
    write_csv(readable_df, output_dir / "opening_chart_readable.csv")
    if show_progress:
        print_table(summary_df, "Opening summary (% of all hands)")
        print_table(readable_df, "Readable opening chart (by class)")
        print_table(
            open_df[open_df["open_freq"] >= 0.5].head(40),
            "Sample opening chart (freq>=0.5)",
        )

    t2 = time.perf_counter()
    responses = solve_responses(feat, opening, config, show_progress=show_progress)
    timings["response_sec"] = time.perf_counter() - t2
    resp_df = strategy_df_from_records(responses.records)
    write_csv(resp_df, output_dir / "call_raise_vs_open.csv")
    if show_progress:
        print_table(resp_df.head(40), "Sample call/raise vs open")

    t3 = time.perf_counter()
    raises = solve_raise_tree(feat, opening, responses, config, show_progress=show_progress)
    timings["raise_tree_sec"] = time.perf_counter() - t3
    raise_df = strategy_df_from_records(raises.records)
    write_csv(raise_df, output_dir / "raise_tree.csv")

    cap_rows = compare_raise_caps(feat, opening, responses, config)
    cap_df = strategy_df_from_records(cap_rows)
    write_csv(cap_df, output_dir / "raise_cap_comparison.csv")
    if show_progress:
        print_table(cap_df, "Raise-cap tree size comparison")
        print_table(raise_df.head(40), "Sample raise-tree lines")

    meta = {
        "config": {
            "num_players": config.num_players,
            "ante": config.ante,
            "small_bet": config.small_bet,
            "big_bet": config.big_bet,
            "max_raises": config.max_raises,
            "starting_pot": config.starting_pot,
        },
        "num_buckets": table.num_buckets,
        "num_hands": int(sum(table.bucket_weight)),
        "timings_sec": timings,
        "approximations": [
            "position-by-position approximate GTO (not full 8-way Nash)",
            "no sandbagging in v1",
            "pre-draw only",
            "multiway equity via score-vs-range sigmoid model",
            "drawing hands included in call/raise even when not open-legal",
        ],
    }
    (output_dir / "solve_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    if show_progress:
        print(json.dumps(meta, indent=2))
    return meta


def _opening_readable_chart(open_df):
    """Collapse bucket rows into Super System–style class × seat actions."""
    import pandas as pd

    if open_df is None or open_df.empty:
        return pd.DataFrame()

    def hand_class(bucket: str) -> str:
        parts = bucket.split("|")
        cat, detail = parts[0], parts[1]
        if cat == "one_pair":
            return detail.split(":")[0].replace("pair", "pair_")
        if cat == "two_pair":
            return "two_pair"
        if cat in {"three_of_a_kind", "straight", "flush", "full_house", "four_of_a_kind", "straight_flush", "five_aces"}:
            return cat
        return cat

    rows = []
    for seat, sdf in open_df.groupby("seat", sort=False):
        sdf = sdf.copy()
        sdf["hand_class"] = sdf["bucket"].map(hand_class)
        for cls, cdf in sdf.groupby("hand_class"):
            w = cdf["weight"].sum()
            if w <= 0:
                continue
            freq = float((cdf["weight"] * cdf["open_freq"]).sum() / w)
            if freq >= 0.85:
                action = "Open"
            elif freq <= 0.15:
                action = "Pass"
            else:
                action = f"Mix:{freq:.2f}"
            rows.append(
                {
                    "seat": seat,
                    "hand_class": cls,
                    "action": action,
                    "open_freq": round(freq, 3),
                    "combos": round(w, 1),
                }
            )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    # Pivot-friendly sort
    seat_order = {n: i for i, n in enumerate(SEAT_NAMES)}
    out["seat_index"] = out["seat"].map(seat_order)
    out = out.sort_values(["seat_index", "hand_class"]).drop(columns=["seat_index"])
    return out.reset_index(drop=True)


def _save_abstraction_cache(path: Path, table: AbstractionTable) -> None:
    """Save compact cache (labels/weights/flags only — enough to re-solve)."""
    payload = {
        "bucket_labels": table.bucket_labels,
        "bucket_weight": table.bucket_weight,
        "bucket_open_legal": table.bucket_open_legal,
        "examples": table.examples,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _load_abstraction_cache(path: Path) -> AbstractionTable:
    payload = json.loads(path.read_text(encoding="utf-8"))
    # hand_to_bucket omitted from cache; empty map is OK for solve path
    return AbstractionTable(
        bucket_labels=payload["bucket_labels"],
        hand_to_bucket={},
        bucket_weight=payload["bucket_weight"],
        bucket_open_legal=payload["bucket_open_legal"],
        examples=payload.get("examples", {}),
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Solve pre-draw five-card draw charts")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("outputs"),
        help="Directory for CSV/JSON outputs",
    )
    parser.add_argument("--ante", type=float, default=DEFAULT_CONFIG.ante)
    parser.add_argument("--small-bet", type=float, default=DEFAULT_CONFIG.small_bet)
    parser.add_argument("--big-bet", type=float, default=DEFAULT_CONFIG.big_bet)
    parser.add_argument(
        "--max-raises",
        type=int,
        default=DEFAULT_CONFIG.max_raises,
        help="Raise cap (3 = bet+3 raises; 1 = simplified bet+1)",
    )
    parser.add_argument(
        "--rebuild-abstraction",
        action="store_true",
        help="Ignore abstraction cache and rebuild",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    config = GameConfig(
        ante=args.ante,
        small_bet=args.small_bet,
        big_bet=args.big_bet,
        max_raises=args.max_raises,
    )
    run_predraw_solve(
        output_dir=args.output_dir,
        config=config,
        show_progress=not args.quiet,
        skip_abstraction_cache=args.rebuild_abstraction,
    )


if __name__ == "__main__":
    main()
