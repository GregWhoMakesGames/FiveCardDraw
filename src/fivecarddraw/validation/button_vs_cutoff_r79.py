"""BN fold / call / raise vs CO opening at chart threshold r = 79%.

Frame: ``button_vs_cutoff_r79`` (docs/research/button_vs_cutoff_r79.md).

Laboratory. Seats 1–6 have passed. CO (seat 7) never sandbags two pair+ /
aces. At the signed CO open-chart threshold r = 79% CO opens:

  - AA+ / two pair+ always
  - JJ **only with ace or joker** (physical ace kicker or the bug)
  - QQ class average (every QQ)
  - KK class average (every KK)

BN (seat 8) faces that unraised open. Same locked leaves as the polar labs
(``button_vs_cutoff.py``, ``button_vs_cutoff_tight.py``): no multi-raise, no
live draw / post-draw Nash. Fold = 0 at the node.

Bug = ace kicker / fill, **not** a third rank (KK+joker is ``pair_K``).
"""

from __future__ import annotations

import json
import os
import random
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Sequence

from fivecarddraw.cards import BUG_ID, card_from_id, parse_hand
from fivecarddraw.validation.button_vs_cutoff import (
    BN_CALL_INVEST,
    BN_RAISE_INVEST,
    CALL_POT,
    CO_P_FOLD_AIR,
    DEFAULT_N_2TO1,
    DEFAULT_N_HU,
    DRAW_SPEC,
    FOLD_EV,
    FOCUS_SPECS,
    MADE_SPECS,
    RAISE_POT,
    _cell_seed,
    _deal_from_ids,
    decide_action,
    evaluate_deals,
    sample_bn_hand,
)
from fivecarddraw.validation.button_vs_cutoff_tight import recommend_action
from fivecarddraw.validation.cutoff_open_sandbag import has_physical_ace
from fivecarddraw.validation.draw_call_odds import DrawHandResult
from fivecarddraw.validation.postdraw_betting_m2 import _sample_disjoint_caller
from fivecarddraw.validation.postdraw_nonbluff_ev import HONEST_POLICY, LOCKED_BN_DRAW
from fivecarddraw.validation.showdown_matrix import (
    classify_opener,
    load_call_2to1_hands,
)


DEFAULT_SEED = 20260909
FRAME = "button_vs_cutoff_r79"
SANDBAG_RATE = 0.79
SANDBAG_RATE_PCT = 79

# Chart voice: ace = physical ace kicker or the joker.
PAIR_J_JOKER = parse_hand("Jh Jd Bu 9s 7h")
PAIR_J_ACE = parse_hand("Jh Jd As 7h 4c")
PAIR_J_BARE = parse_hand("Jh Jd 9s 7h 4c")
PAIR_Q_BARE = parse_hand("Qh Qd 9s 7h 4c")
PAIR_K_BARE = parse_hand("Kh Kd 9s 7h 4c")
PAIR_Q_JOKER = parse_hand("Qh Qd Bu 9s 7h")
PAIR_K_JOKER = parse_hand("Kh Kd Bu 9s 7h")


def _ids(cards) -> tuple[int, ...]:
    return tuple(sorted(c.card_id for c in cards))


def _cls_of_ids(ids: Sequence[int]) -> str | None:
    return classify_opener(tuple(card_from_id(i) for i in ids))


def jj_has_ace_or_joker(ids: Sequence[int]) -> bool:
    """JJ opens at r=79% iff the bug or a physical ace kicker is in the five."""
    return BUG_ID in set(ids) or has_physical_ace(ids)


def is_co_r79_open(opener_class: str | None, ids: Sequence[int]) -> bool:
    """CO range at r=79%: all legal except JJ without ace/joker.

    QQ and KK are class-average opens (no kicker filter). AA+ / two pair+
    always open. CO does not sandbag any of these.
    """
    if opener_class is None:
        return False
    if opener_class == "pair_J":
        return jj_has_ace_or_joker(ids)
    return True


def sample_r79_co_ids(
    rng: random.Random, *, blocked: set[int], tries: int = 400
) -> tuple[tuple[int, ...], str] | None:
    """Rejection-sample a combo-weighted r=79% CO five-set from the remainder."""
    pool = [i for i in range(53) if i not in blocked]
    if len(pool) < 5:
        return None
    for _ in range(tries):
        ids = tuple(sorted(rng.sample(pool, 5)))
        cls = _cls_of_ids(ids)
        if is_co_r79_open(cls, ids):
            assert cls is not None
            return ids, cls
    return None


def generate_bn_vs_co_r79_deals(
    spec: str,
    *,
    n_deals: int,
    seed: int,
    draw_policy=LOCKED_BN_DRAW,
) -> list:
    """HU: BN ``spec`` × CO r=79% range. CO draws first, then BN."""
    rng = random.Random(seed)
    deals = []
    tries = 0
    cap = max(n_deals * 80, 8_000)
    while len(deals) < n_deals and tries < cap:
        tries += 1
        sampled = sample_bn_hand(spec, rng)
        if sampled is None:
            continue
        bn_ids, bn_cls = sampled
        co = sample_r79_co_ids(rng, blocked=set(bn_ids))
        if co is None:
            continue
        co_ids, co_cls = co
        left = [i for i in range(53) if i not in bn_ids and i not in co_ids]
        rng.shuffle(left)
        try:
            deals.append(
                _deal_from_ids(
                    co_ids=co_ids,
                    co_cls=co_cls,
                    bn_ids=bn_ids,
                    bn_cls=bn_cls,
                    rem=left,
                    draw_policy=draw_policy,
                )
            )
        except ValueError:
            continue
    return deals


def generate_bn_2to1_vs_co_r79_deals(
    callers: Sequence[DrawHandResult],
    *,
    n_deals: int,
    seed: int,
    draw_policy=LOCKED_BN_DRAW,
) -> list:
    """BN is a 2:1 keep-4 caller; CO is the r=79% open range."""
    rng = random.Random(seed)
    deals = []
    tries = 0
    cap = max(n_deals * 80, 8_000)
    while len(deals) < n_deals and tries < cap:
        tries += 1
        co = sample_r79_co_ids(rng, blocked=set())
        if co is None:
            continue
        co_ids, co_cls = co
        caller = _sample_disjoint_caller(callers, set(co_ids), rng)
        if caller is None:
            continue
        bn_ids = tuple(sorted(c.card_id for c in caller.cards))
        left = [i for i in range(53) if i not in co_ids and i not in bn_ids]
        rng.shuffle(left)
        try:
            deals.append(
                _deal_from_ids(
                    co_ids=co_ids,
                    co_cls=co_cls,
                    bn_ids=bn_ids,
                    bn_cls="all_2to1",
                    rem=left,
                    draw_policy=draw_policy,
                    bn_is_2to1=True,
                    bn_keep=caller.keep,
                )
            )
        except ValueError:
            continue
    return deals


def evaluate_bn_spec(
    spec: str,
    *,
    n_deals: int,
    seed: int,
    callers: Sequence[DrawHandResult] | None = None,
    progress: bool = False,
) -> dict[str, Any]:
    if progress:
        print(f"  {spec}: n={n_deals}…", flush=True)
    if spec == DRAW_SPEC:
        if not callers:
            raise ValueError("two_to_one requires loaded 2:1 callers")
        deals = generate_bn_2to1_vs_co_r79_deals(
            callers, n_deals=n_deals, seed=seed
        )
    else:
        deals = generate_bn_vs_co_r79_deals(spec, n_deals=n_deals, seed=seed)
    row = evaluate_deals(deals)
    row["bn_spec"] = spec
    row["seed"] = seed
    row["kind"] = "draw_2to1" if spec == DRAW_SPEC else "made"
    # Tight-lab value-raise cross-check (P(win)>1/2). Same pots as polar.
    row["recommend_tight_rule"] = recommend_action(
        ev_call=row["ev_call"],
        ev_raise=row["ev_raise_checkdown"],
        se_call=row["se_call"],
        se_raise=row["se_raise_checkdown"],
        p_bn_win=row["p_bn_wins_final"],
    )
    return row


def _cell_job(item: tuple[str, int, int]) -> dict[str, Any]:
    spec, n_deals, seed = item
    return evaluate_bn_spec(spec, n_deals=n_deals, seed=seed, progress=False)


def derive_answers(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by = {r["bn_spec"]: r for r in rows}
    chart = {spec: by[spec]["action"] for spec in by}
    close = [r["bn_spec"] for r in rows if r.get("needs_later_tree")]
    made_fold = [
        r["bn_spec"] for r in rows if r["kind"] == "made" and r["action"] == "fold"
    ]
    made_call = [
        r["bn_spec"] for r in rows if r["kind"] == "made" and r["action"] == "call"
    ]
    made_raise = [
        r["bn_spec"] for r in rows if r["kind"] == "made" and r["action"] == "raise"
    ]
    aa = by.get("pair_A")
    aa_action = None if aa is None else aa["action"]
    aa_tight = None if aa is None else aa["recommend_tight_rule"]["action"]
    return {
        "sandbag_rate": SANDBAG_RATE,
        "sandbag_rate_pct": SANDBAG_RATE_PCT,
        "co_range_note": (
            "CO opens AA+ / two pair+ always; JJ only with ace or joker; "
            "QQ and KK class average (every combo). CO never sandbags."
        ),
        "fold_equity_vs_air": 0.0,
        "fold_equity_note": (
            "CO’s r=79% range is still 100% jacks-or-better (no junk). A BN "
            "raise has no fold equity vs air; raise is value/protection vs "
            "the constructed range. p_CO_fold_air = 0."
        ),
        "chart": chart,
        "made_fold": made_fold,
        "made_call": made_call,
        "made_raise": made_raise,
        "close_or_needs_later": close,
        "pair_J_action": None if "pair_J" not in by else by["pair_J"]["action"],
        "pair_J_ev_call": None if "pair_J" not in by else by["pair_J"]["ev_call"],
        "pair_Q_action": None if "pair_Q" not in by else by["pair_Q"]["action"],
        "pair_K_action": None if "pair_K" not in by else by["pair_K"]["action"],
        "pair_A_action": aa_action,
        "pair_A_ev_call": None if aa is None else aa["ev_call"],
        "pair_A_ev_raise_checkdown": None if aa is None else aa["ev_raise_checkdown"],
        "pair_A_p_win": None if aa is None else aa["p_bn_wins_final"],
        "aa_still_raises": aa_action == "raise",
        "aa_tight_rule_action": aa_tight,
        "two_pair_action": None if "two_pair" not in by else by["two_pair"]["action"],
        "two_pair_aces_up_action": (
            None
            if "two_pair_aces_up" not in by
            else by["two_pair_aces_up"]["action"]
        ),
        "trips_plus_action": (
            None if "trips_plus" not in by else by["trips_plus"]["action"]
        ),
        "two_to_one_action": (
            None if "two_to_one" not in by else by["two_to_one"]["action"]
        ),
        "inflection_note": (
            "Polar r=0% (all-legal): AA raises. Polar r≈100% (tight): AA "
            "folds. This row asks whether AA still raises vs the r=79% CO "
            "range (JJ restricted to ace/joker; QQ/KK still class-average)."
        ),
    }


def run_button_vs_cutoff_r79(
    *,
    n_hu: int = DEFAULT_N_HU,
    n_2to1: int = DEFAULT_N_2TO1,
    seed: int = DEFAULT_SEED,
    specs: Sequence[str] | None = None,
    progress: bool = True,
    callers: Sequence[DrawHandResult] | None = None,
    include_draws: bool = True,
    workers: int | None = None,
) -> dict[str, Any]:
    use = list(specs) if specs else list(FOCUS_SPECS)
    if not include_draws:
        use = [s for s in use if s != DRAW_SPEC]
    need_draws = DRAW_SPEC in use
    if need_draws and callers is None:
        if progress:
            print("Loading 2:1 callers…", flush=True)
        callers = load_call_2to1_hands(progress=progress)
    jobs = []
    for spec in use:
        n = n_2to1 if spec == DRAW_SPEC else n_hu
        jobs.append((spec, n, _cell_seed(seed, "r79", spec)))
    n_workers = workers if workers is not None else min(len(jobs), os.cpu_count() or 4)
    if progress:
        print(
            f"BN vs CO r=79%: {len(jobs)} cells, n_hu={n_hu}, "
            f"n_2to1={n_2to1}, workers={n_workers}",
            flush=True,
        )
    # 2:1 needs the caller inventory in-process; run it on the parent.
    draw_jobs = [j for j in jobs if j[0] == DRAW_SPEC]
    made_jobs = [j for j in jobs if j[0] != DRAW_SPEC]
    out_rows: list[dict[str, Any]] = []
    if made_jobs:
        if n_workers <= 1 or len(made_jobs) == 1:
            out_rows.extend(_cell_job(j) for j in made_jobs)
        else:
            with ProcessPoolExecutor(max_workers=n_workers) as pool:
                out_rows.extend(pool.map(_cell_job, made_jobs))
    for spec, n, cell_seed in draw_jobs:
        out_rows.append(
            evaluate_bn_spec(
                spec,
                n_deals=n,
                seed=cell_seed,
                callers=callers,
                progress=progress,
            )
        )
    by_key = {r["bn_spec"]: r for r in out_rows}
    ordered = [by_key[s] for s in use]
    answers = derive_answers(ordered)
    return {
        "meta": {
            "seed": seed,
            "n_hu": n_hu,
            "n_2to1": n_2to1,
            "frame": FRAME,
            "sandbag_rate": SANDBAG_RATE,
            "sandbag_rate_pct": SANDBAG_RATE_PCT,
            "co_range": {
                "threshold_r": SANDBAG_RATE,
                "include": (
                    "pair_A, two_pair, two_pair_aces_up, trips*, straight+, "
                    "pair_Q class average, pair_K class average, "
                    "pair_J with ace kicker or joker"
                ),
                "exclude": "pair_J without ace or joker; any non-legal",
                "sandbag": "CO does not sandbag these hands — they open them",
                "jj": "ace or joker",
                "qq": "open (class average)",
                "kk": "open (class average)",
                "bug": (
                    "Joker is an ace, not trips. JJ+joker = two jacks + ace "
                    "kicker; KK+joker = two kings + ace kicker."
                ),
            },
            "matchup": (
                "Seats 1–6 passed. CO opens the r=79% chart range (JJ only "
                "with ace or joker; QQ/KK class average; AA+ / two pair+ "
                "always). BN fold / call / raise vs that open. Raise: CO "
                "always continues (no air). No multi-raise."
            ),
            "accounting": {
                "fold": FOLD_EV,
                "antes_already_in": 2.0,
                "co_open_pot": 4.0,
                "call_invest": BN_CALL_INVEST,
                "call_pot": CALL_POT,
                "call_net": "EV_street_bn - $2 (honest $6 leaf)",
                "call_checkdown_net": "checkdown $6 - $2 (fair vs raise-cd)",
                "raise_invest": BN_RAISE_INVEST,
                "raise_pot": RAISE_POT,
                "raise_net": "checkdown $10 - $4; CO always calls",
                "p_co_folds_air": CO_P_FOLD_AIR,
            },
            "draw_order": "CO first, then BN (BN last)",
            "locked_draws": {
                "name": LOCKED_BN_DRAW.name,
                "pair_d": LOCKED_BN_DRAW.pair_d,
                "two_pair_d": LOCKED_BN_DRAW.two_pair_d,
                "trips_d": LOCKED_BN_DRAW.trips_d,
                "quads_d": LOCKED_BN_DRAW.quads_d,
            },
            "honest_policy": HONEST_POLICY.key,
            "bug": "ace or straight/flush fill; not a third rank (KK+joker = pair_K)",
            "action_rule": (
                "Published chart uses button_vs_cutoff.decide_action "
                "(matching checkdowns). Tight recommend_action is stored as "
                "recommend_tight_rule for the AA inflection cross-check."
            ),
            "out_of_scope": [
                "other chart thresholds (84, 86, 87, 90, 93, 96) — other agents",
                "polar 0% / ~100% restarts",
                "multi-raise Nash",
                "live draw solver / post-draw Nash",
                "HJ mixes / reverse-blockers / 3:1 inventories",
            ],
            "doc": "docs/research/button_vs_cutoff_r79.md",
            "regenerate": (
                "python -m fivecarddraw.validation.button_vs_cutoff_r79 "
                "--n-hu 4000 --n-2to1 2000 --write-fixture"
            ),
            "parent_frame": "cutoff_open_sandbag_v1",
            "polar_frames": [
                "button_vs_cutoff_all_legal",
                "button_vs_cutoff_tight",
            ],
        },
        "by_spec": ordered,
        "answers": answers,
    }


def default_fixture_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "validation"
        / "button_vs_cutoff_r79.json"
    )


def write_summary_fixture(payload: dict[str, Any], path: Path | None = None) -> Path:
    path = path or default_fixture_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    slim = {
        "meta": payload["meta"],
        "by_spec": payload["by_spec"],
        "answers": payload["answers"],
    }
    path.write_text(json.dumps(slim, indent=2) + "\n", encoding="utf-8")
    return path


def load_summary_fixture(path: Path | None = None) -> dict[str, Any]:
    path = path or default_fixture_path()
    return json.loads(path.read_text(encoding="utf-8"))


def write_markdown_summary(payload: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    a = payload["answers"]
    meta = payload["meta"]
    aa_line = (
        "AA **still raises** vs this CO range."
        if a["aa_still_raises"]
        else "AA **does not raise** vs this CO range (inflection already hit)."
    )
    lines = [
        "# Button vs cutoff, r = 79%",
        "",
        f"Seed `{meta['seed']}`, n_hu={meta['n_hu']}, n_2to1={meta['n_2to1']}.",
        "",
        a["co_range_note"],
        "",
        a["fold_equity_note"],
        "",
        aa_line,
        "",
        f"Chart: `{a['chart']}`",
        "",
        "| BN spec | action | EV fold | EV call honest (SE) | EV call-cd | EV raise-cd (SE) | P(win) | later? |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for r in payload["by_spec"]:
        later = "yes" if r.get("needs_later_tree") else "no"
        lines.append(
            f"| {r['bn_spec']} | **{r['action']}** | {r['ev_fold']:+.2f} | "
            f"{r['ev_call']:+.3f} ({r['se_call']:.3f}) | "
            f"{r.get('ev_call_checkdown', 0):+.3f} | "
            f"{r['ev_raise_checkdown']:+.3f} ({r['se_raise_checkdown']:.3f}) | "
            f"{r['p_bn_wins_final']:.3f} | {later} |"
        )
    lines += ["", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(
        description=(
            "BN fold/call/raise vs CO opening at chart r=79% "
            "(JJ ace-or-joker; QQ/KK class average; AA+ always)"
        )
    )
    p.add_argument("--n-hu", type=int, default=DEFAULT_N_HU)
    p.add_argument("--n-2to1", type=int, default=DEFAULT_N_2TO1)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--quick", action="store_true")
    p.add_argument("--no-draws", action="store_true")
    p.add_argument("--workers", type=int, default=None)
    p.add_argument(
        "--specs",
        type=str,
        default=None,
        help="Comma-separated BN specs (default: pairs, two_pair, trips_plus, 2:1)",
    )
    p.add_argument("-o", "--output", type=Path, default=None)
    p.add_argument("--write-fixture", action="store_true")
    args = p.parse_args()
    n_hu, n_2to1 = args.n_hu, args.n_2to1
    if args.quick:
        n_hu, n_2to1 = 250, 150
    specs = (
        [c.strip() for c in args.specs.split(",") if c.strip()]
        if args.specs
        else None
    )
    payload = run_button_vs_cutoff_r79(
        n_hu=n_hu,
        n_2to1=n_2to1,
        seed=args.seed,
        specs=specs,
        progress=True,
        include_draws=not args.no_draws,
        workers=args.workers,
    )
    out = args.output or Path("outputs/validation/button_vs_cutoff_r79.json")
    out.parent.mkdir(parents=True, exist_ok=True)
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
    print("Chart:", a["chart"])
    print("AA still raises:", a["aa_still_raises"])
    print(a["fold_equity_note"])
    for r in payload["by_spec"]:
        flag = "  [close]" if r.get("needs_later_tree") else ""
        print(
            f"  {r['bn_spec']:<18} {r['action']:<6}  "
            f"call={r['ev_call']:+.3f}±{r['se_call']:.3f}  "
            f"call_cd={r.get('ev_call_checkdown', 0):+.3f}  "
            f"raise={r['ev_raise_checkdown']:+.3f}±{r['se_raise_checkdown']:.3f}  "
            f"p_win={r['p_bn_wins_final']:.3f}{flag}"
        )


if __name__ == "__main__":
    main()
