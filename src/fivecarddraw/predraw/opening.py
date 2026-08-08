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
    open_freq_prior,
)
from fivecarddraw.rules import GameConfig, SEAT_NAMES


@dataclass(slots=True)
class OpeningResult:
    # seat -> open frequency per bucket [0,1]
    open_freq: np.ndarray  # shape (num_seats, num_buckets)
    open_ev: np.ndarray  # EV of opening vs pass (pass=0)
    records: list[dict]


def _mass_weighted(feat: BucketFeatures, freq: np.ndarray) -> float:
    w = feat.weight
    return float(np.sum(w * freq) / w.sum())


def solve_opening(
    feat: BucketFeatures,
    config: GameConfig,
    show_progress: bool = True,
) -> OpeningResult:
    """Solve opening frequencies seat-by-seat from the dealer backward to UTG.

    Assumptions (explicit):
    - No sandbagging: open-legal hands either open or pass; they do not check strong hands.
    - Later seats use already-solved policies; earlier seats assume those policies.
    - Multiway interactions after open are approximated via steal / multi-caller EV.
    """
    n_seats = config.num_players
    n_buckets = len(feat.labels)
    open_freq = np.zeros((n_seats, n_buckets), dtype=np.float64)
    open_ev = np.zeros((n_seats, n_buckets), dtype=np.float64)

    prior = open_freq_prior(feat, config)
    scores = np.array([effective_hand_score(feat, i) for i in range(n_buckets)])

    seat_iter = range(n_seats - 1, -1, -1)
    if show_progress:
        seat_iter = tqdm(list(seat_iter), desc="opening seats", unit="seat")

    for seat in seat_iter:
        behind = n_seats - seat - 1
        if seat + 1 < n_seats:
            later = open_freq[seat + 1 :]
            behind_open = later.mean(axis=0)
        else:
            behind_open = prior

        p_open_raw = _mass_weighted(feat, behind_open)

        # Hands that continue vs an open: openers + strong draws (cannot open).
        continue_freq = behind_open.copy()
        for i in range(n_buckets):
            if feat.open_legal[i]:
                continue
            if feat.draw_power[i] >= 0.55:
                continue_freq[i] = max(continue_freq[i], 0.55)
            elif feat.draw_power[i] >= 0.35:
                continue_freq[i] = max(continue_freq[i], 0.20)
        p_cont_raw = _mass_weighted(feat, continue_freq)

        # Range weights for equity when called / raised
        call_w = feat.weight * continue_freq
        open_w = feat.weight * behind_open
        if call_w.sum() <= 0:
            call_w = feat.weight * feat.open_legal.astype(np.float64)

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
            p_cont = float(np.clip(p_cont_raw * mult, 0.01, 0.90))
            p_open_one = float(np.clip(p_open_raw * mult, 0.0, 0.85))

            # Steal only if nobody continues (call or raise)
            p_steal = (1.0 - p_cont) ** behind if behind > 0 else 1.0

            pot0 = config.starting_pot
            sb = config.small_bet
            hero = scores[i]

            # Expected continuers conditional on ≥1 continuer
            if behind == 0:
                exp_cont = 0.0
            else:
                # Unconditional expected continuers; if steal fails use at least 1
                exp_cont = max(1.0, behind * p_cont)

            # Equity vs a calling-oriented range (down-weight premium made hands a bit
            # so one high pair is not crushed by an opener-heavy two-pair range).
            call_w_adj = call_w.copy()
            for j in range(n_buckets):
                if feat.strength[j] >= 0.70:
                    call_w_adj[j] *= 0.55
            eq_hu = equity_vs_range(hero, scores, call_w_adj)
            # Soft multiway penalty (power laws are too harsh on premium pairs)
            eq_multi = eq_hu / (1.0 + 0.28 * max(0.0, exp_cont - 1.0))
            eq_multi = float(np.clip(eq_multi, 0.02, 0.95))

            pot_called = pot0 + sb * (1.0 + exp_cont)
            ev_steal = pot0
            ev_called = -sb + eq_multi * pot_called

            # Raise pressure from behind (subset of continuers)
            p_raise_one = min(p_open_one * 0.30, 0.10)
            p_face_raise = 1.0 - (1.0 - p_raise_one) ** behind if behind else 0.0
            if hero >= 0.62:
                ev_raised = -2 * sb + 0.58 * (pot0 + 4 * sb)
            elif hero >= 0.52:
                ev_raised = -2 * sb + 0.42 * (pot0 + 4 * sb)
            elif hero >= 0.45:
                ev_raised = -1.25 * sb
            else:
                ev_raised = -sb

            # Mix: when not steal, sometimes raised vs called
            p_action = 1.0 - p_steal
            ev = (
                p_steal * ev_steal
                + p_action * (1.0 - p_face_raise) * ev_called
                + p_action * p_face_raise * ev_raised
            )

            # Position risk premium scales up for weaker openers (JJ more than AA)
            weakness = float(np.clip(0.70 - hero, 0.0, 0.40))
            risk_premium = (0.05 * sb * behind) * (1.0 + 3.0 * weakness)
            adj_ev = ev - risk_premium
            open_ev[seat, i] = adj_ev

            if adj_ev > 0.08 * sb:
                freq = 1.0
            elif adj_ev < -0.08 * sb:
                freq = 0.0
            else:
                freq = float(np.clip(0.5 + adj_ev / sb, 0.0, 1.0))
            open_freq[seat, i] = freq

    records: list[dict] = []
    for seat in range(n_seats):
        for i in range(n_buckets):
            if not feat.open_legal[i]:
                continue
            freq = float(open_freq[seat, i])
            # Keep opens and near-indifferent; drop clear passes for table length
            if freq <= 0.001 and open_ev[seat, i] < -0.25 * config.small_bet:
                continue
            if freq >= 0.999:
                action = "Open"
            elif freq <= 0.001:
                action = "Pass"
            else:
                action = f"Mix:{freq:.2f}"
            records.append(
                {
                    "seat": SEAT_NAMES[seat],
                    "seat_index": seat,
                    "bucket": feat.labels[i],
                    "weight": feat.weight[i],
                    "action": action,
                    "open_freq": round(freq, 4),
                    "ev_open": round(float(open_ev[seat, i]), 4),
                    "open_legal": True,
                    "score": round(float(scores[i]), 3),
                }
            )

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
