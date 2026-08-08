"""Position-by-position opening charts (no sandbagging in v1)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from tqdm import tqdm

from fivecarddraw.predraw.model import (
    BucketFeatures,
    blocker_open_multiplier,
    effective_hand_score,
    equity_vs_range,
    normalize_weights,
    open_freq_prior,
)
from fivecarddraw.rules import GameConfig, SEAT_NAMES


@dataclass(slots=True)
class OpeningResult:
    # seat -> open frequency per bucket [0,1]
    open_freq: np.ndarray  # shape (num_seats, num_buckets)
    open_ev: np.ndarray  # EV of opening vs pass (pass=0)
    records: list[dict]


def _mass_open_prob(feat: BucketFeatures, open_freq: np.ndarray) -> float:
    """Unconditional P(a random hand opens) under open_freq policy."""
    w = feat.weight
    return float(np.sum(w * open_freq) / w.sum())


def _range_after_open(feat: BucketFeatures, open_freq: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    w = feat.weight * open_freq
    scores = np.array([effective_hand_score(feat, i) for i in range(len(w))])
    return scores, w


def solve_opening(
    feat: BucketFeatures,
    config: GameConfig,
    show_progress: bool = True,
) -> OpeningResult:
    """Solve opening frequencies seat-by-seat from the dealer backward to UTG.

    Assumptions (explicit):
    - No sandbagging: open-legal hands either open or pass; they do not check strong hands.
    - Later seats use already-solved policies; earlier seats assume those policies.
    - Multiway interactions after open are approximated via steal / single-call EV.
    """
    n_seats = config.num_players
    n_buckets = len(feat.labels)
    open_freq = np.zeros((n_seats, n_buckets), dtype=np.float64)
    open_ev = np.zeros((n_seats, n_buckets), dtype=np.float64)

    # Initialize late-position prior for bootstrapping dealer
    prior = open_freq_prior(feat, config)

    seat_iter = range(n_seats - 1, -1, -1)
    if show_progress:
        seat_iter = tqdm(list(seat_iter), desc="opening seats", unit="seat")

    for seat in seat_iter:
        behind = n_seats - seat - 1
        # Policy of a representative player still to act:
        # use next seat's solved policy if available, else prior.
        if seat + 1 < n_seats:
            behind_policy = open_freq[seat + 1]
            # Blend remaining seats toward average of solved later seats
            later = open_freq[seat + 1 :]
            behind_policy = later.mean(axis=0) if later.size else prior
        else:
            behind_policy = prior

        p_open_raw = _mass_open_prob(feat, behind_policy)
        call_scores, call_w = _range_after_open(feat, behind_policy)
        # Cold-callers also include big draws that cannot open — approximate by
        # adding draw-heavy pass hands into a "continue" range at reduced weight.
        continue_w = call_w.copy()
        for i in range(n_buckets):
            if feat.open_legal[i]:
                continue
            if feat.draw_power[i] >= 0.55:
                continue_w[i] += feat.weight[i] * 0.35

        records_seat: list[dict] = []
        bucket_range = range(n_buckets)
        if show_progress:
            bucket_range = tqdm(
                bucket_range,
                desc=f"  {SEAT_NAMES[seat]} buckets",
                leave=False,
                unit="bucket",
            )

        for i in bucket_range:
            if not feat.open_legal[i]:
                open_freq[seat, i] = 0.0
                open_ev[seat, i] = 0.0
                continue

            mult = blocker_open_multiplier(feat, i)
            p_open_one = float(np.clip(p_open_raw * mult, 0.0, 0.95))
            p_steal = (1.0 - p_open_one) ** behind if behind > 0 else 1.0

            # Steal: win starting pot (antes). Fold EV = 0 at decision node.
            pot0 = config.starting_pot
            sb = config.small_bet
            ev_steal = pot0

            # When not stealing: approximate as getting exactly one caller who matched.
            # Pot ~ pot0 + 2*sb, we have invested sb; equity vs continue range.
            hero = effective_hand_score(feat, i)
            eq = equity_vs_range(hero, call_scores, continue_w if continue_w.sum() else call_w)
            pot_called = pot0 + 2 * sb
            # Net chip EV relative to fold: -sb + eq * pot_called
            ev_called = -sb + eq * pot_called

            # Raise pressure: with small probability someone raises; then we continue
            # only with stronger hands. Approximate EV penalty for medium hands.
            p_raise = min(0.25, 0.08 * behind) * (0.5 + 0.5 * p_open_one)
            if hero >= 0.62:
                ev_raised = -2 * sb + 0.58 * (pot0 + 4 * sb)  # rough
            elif hero >= 0.45:
                ev_raised = -2 * sb + 0.40 * (pot0 + 4 * sb)
            else:
                ev_raised = -2 * sb  # fold to raise often → lose open+call

            ev = (
                p_steal * ev_steal
                + (1.0 - p_steal) * (1.0 - p_raise) * ev_called
                + (1.0 - p_steal) * p_raise * ev_raised
            )
            open_ev[seat, i] = ev

            # Pure strategy unless near indifference
            if ev > 0.05 * sb:
                freq = 1.0
            elif ev < -0.05 * sb:
                freq = 0.0
            else:
                # Mix near indifference
                freq = float(np.clip(0.5 + ev / sb, 0.0, 1.0))
            open_freq[seat, i] = freq

        # After solving seat, keep policy for earlier seats

    records: list[dict] = []
    for seat in range(n_seats):
        for i in range(n_buckets):
            if not feat.open_legal[i] and open_freq[seat, i] == 0:
                # Skip pass-only non-openers in opening chart for readability
                continue
            if open_freq[seat, i] <= 0 and open_ev[seat, i] <= 0:
                # Still include open-legal folds? Include open-legal with any EV for charts
                if not feat.open_legal[i]:
                    continue
            action = "Open" if open_freq[seat, i] >= 0.999 else (
                "Pass" if open_freq[seat, i] <= 0.001 else f"Mix:{open_freq[seat, i]:.2f}"
            )
            if open_freq[seat, i] <= 0.001 and feat.open_legal[i]:
                # include borderline passes for open-legal only when EV computed
                if open_ev[seat, i] < -0.25 * config.small_bet:
                    # omit clear passes to keep Super System–style tables shorter
                    continue
            records.append(
                {
                    "seat": SEAT_NAMES[seat],
                    "seat_index": seat,
                    "bucket": feat.labels[i],
                    "weight": feat.weight[i],
                    "action": action,
                    "open_freq": round(float(open_freq[seat, i]), 4),
                    "ev_open": round(float(open_ev[seat, i]), 4),
                    "open_legal": bool(feat.open_legal[i]),
                }
            )

    # Sort: seat, then open_freq desc, weight desc
    records.sort(key=lambda r: (r["seat_index"], -r["open_freq"], -r["weight"]))
    return OpeningResult(open_freq=open_freq, open_ev=open_ev, records=records)


def opening_summary(result: OpeningResult, feat: BucketFeatures, config: GameConfig) -> list[dict]:
    """Per-seat aggregate open % of hands."""
    rows = []
    total = feat.weight.sum()
    for seat in range(config.num_players):
        mass = float(np.sum(feat.weight * result.open_freq[seat]) / total)
        rows.append(
            {
                "seat": SEAT_NAMES[seat],
                "open_hand_pct": round(100.0 * mass, 3),
                "open_combos": round(float(np.sum(feat.weight * result.open_freq[seat])), 1),
            }
        )
    return rows
