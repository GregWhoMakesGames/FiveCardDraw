"""Raise / re-raise / call-raise lines on the pre-draw street."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from tqdm import tqdm

from fivecarddraw.predraw.model import (
    BucketFeatures,
    effective_hand_score,
    equity_vs_range,
)
from fivecarddraw.predraw.opening import OpeningResult
from fivecarddraw.predraw.response import ResponseResult
from fivecarddraw.rules import GameConfig, SEAT_NAMES


@dataclass(slots=True)
class RaiseTreeResult:
    records: list[dict]


def solve_raise_tree(
    feat: BucketFeatures,
    opening: OpeningResult,
    responses: ResponseResult,
    config: GameConfig,
    show_progress: bool = True,
) -> RaiseTreeResult:
    """Approximate decisions facing a raise or re-raise.

    Builds Super System–style rows for:
    - facing an open-raise (as opener)
    - facing a re-raise (cap-aware)

    `config.max_raises` controls whether we model bet+3 or bet+1.
    """
    n_seats = config.num_players
    n_buckets = len(feat.labels)
    sb = config.small_bet
    pot0 = config.starting_pot
    records: list[dict] = []

    # Opponent aggressor range: mix of opening raises from response solver
    raise_mass = np.zeros(n_buckets, dtype=np.float64)
    for seat in range(n_seats):
        raise_mass += feat.weight * responses.raise_freq[seat]
    if raise_mass.sum() <= 0:
        raise_mass = feat.weight * feat.open_legal.astype(np.float64)
    agg_scores = np.array([effective_hand_score(feat, i) for i in range(n_buckets)])

    lines = [
        ("face_raise_as_opener", 2, pot0 + 3 * sb),  # open + raise; to_call = sb
        ("face_reraise", 3, pot0 + 5 * sb),  # deeper
    ]
    if config.max_raises >= 3:
        lines.append(("face_cap_raise", 4, pot0 + 7 * sb))

    line_iter = lines
    if show_progress:
        line_iter = tqdm(lines, desc="raise-tree lines", unit="line")

    for line_name, bets_in_front, pot_face in line_iter:
        to_call = sb
        # Cap check: if this line would exceed max bets on street, skip
        # bets_in_front counts bet increments already put in by aggressor side
        if bets_in_front - 1 > config.max_raises:
            continue

        can_re_raise = (bets_in_front) < (1 + config.max_raises)

        for seat in range(n_seats):
            for i in range(n_buckets):
                score = effective_hand_score(feat, i)
                # Only consider hands that would have continued prior action
                prior_cont = max(
                    float(opening.open_freq[seat, i]),
                    float(responses.call_freq[seat, i]),
                    float(responses.raise_freq[seat, i]),
                )
                if prior_cont < 0.05 and feat.draw_power[i] < 0.55:
                    continue

                eq = equity_vs_range(score, agg_scores, raise_mass)
                ev_fold = 0.0
                ev_call = -to_call + eq * (pot_face + to_call)

                ev_raise = -1e9
                action_raise_ok = False
                if can_re_raise:
                    invest = 2 * sb  # call + raise
                    # Tighten aggressor continue range
                    cont = raise_mass.copy()
                    for j in range(n_buckets):
                        if effective_hand_score(feat, j) < 0.55:
                            cont[j] *= 0.2
                    eq_r = equity_vs_range(score, agg_scores, cont)
                    fold_eq = float(
                        np.clip(1.0 - cont.sum() / max(raise_mass.sum(), 1e-9), 0.05, 0.6)
                    )
                    ev_raise = fold_eq * pot_face + (1.0 - fold_eq) * (
                        -invest + eq_r * (pot_face + invest + sb)
                    )
                    action_raise_ok = True

                best = ev_fold
                action = "Fold"
                c_f, r_f = 0.0, 0.0
                if ev_call > best:
                    best = ev_call
                    action = "Call"
                    c_f = 1.0
                if action_raise_ok and ev_raise > best:
                    best = ev_raise
                    action = "Raise"
                    c_f, r_f = 0.0, 1.0

                if action == "Fold" and score < 0.5 and feat.draw_power[i] < 0.6:
                    continue

                records.append(
                    {
                        "line": line_name,
                        "seat": SEAT_NAMES[seat],
                        "seat_index": seat,
                        "max_raises": config.max_raises,
                        "bucket": feat.labels[i],
                        "weight": feat.weight[i],
                        "action": action,
                        "call_freq": round(c_f, 4),
                        "raise_freq": round(r_f, 4),
                        "ev_call": round(ev_call, 4),
                        "ev_raise": round(ev_raise, 4) if action_raise_ok else "",
                        "equity": round(eq, 4),
                        "open_legal": bool(feat.open_legal[i]),
                    }
                )

    records.sort(key=lambda r: (r["line"], r["seat_index"], -r["raise_freq"], -r["call_freq"]))
    return RaiseTreeResult(records=records)


def compare_raise_caps(
    feat: BucketFeatures,
    opening: OpeningResult,
    responses: ResponseResult,
    base_config: GameConfig,
) -> list[dict]:
    """Benchmark tree sizes for bet+3 vs bet+1."""
    rows = []
    for max_raises in (3, 1):
        cfg = GameConfig(
            num_players=base_config.num_players,
            ante=base_config.ante,
            small_bet=base_config.small_bet,
            big_bet=base_config.big_bet,
            max_raises=max_raises,
        )
        result = solve_raise_tree(feat, opening, responses, cfg, show_progress=False)
        rows.append(
            {
                "max_raises": max_raises,
                "structure": f"bet+{max_raises}",
                "rows": len(result.records),
                "raise_actions": sum(1 for r in result.records if r["action"] == "Raise"),
                "call_actions": sum(1 for r in result.records if r["action"] == "Call"),
            }
        )
    return rows
