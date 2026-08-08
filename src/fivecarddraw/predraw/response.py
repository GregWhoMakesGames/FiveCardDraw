"""Call / raise decisions facing an open (includes non-opening draws)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from tqdm import tqdm

from fivecarddraw.predraw.model import (
    BucketFeatures,
    effective_hand_score,
    equity_vs_range,
    normalize_weights,
)
from fivecarddraw.predraw.opening import OpeningResult
from fivecarddraw.rules import GameConfig, SEAT_NAMES


@dataclass(slots=True)
class ResponseResult:
    # Indexed by hero_seat, opener_seat is summarized via opener range from that seat
    records: list[dict]
    # call_freq[hero_seat, bucket], raise_freq[hero_seat, bucket] vs a typical earlier open
    call_freq: np.ndarray
    raise_freq: np.ndarray


def _opener_range(
    feat: BucketFeatures, opening: OpeningResult, opener_seat: int
) -> tuple[np.ndarray, np.ndarray]:
    freq = opening.open_freq[opener_seat]
    w = feat.weight * freq
    scores = np.array([effective_hand_score(feat, i) for i in range(len(w))])
    return scores, w


def solve_responses(
    feat: BucketFeatures,
    opening: OpeningResult,
    config: GameConfig,
    show_progress: bool = True,
) -> ResponseResult:
    """For each hero seat, compute fold/call/raise vs an open from an earlier seat.

    Uses the nearest earlier seat's opening range as the opener model (UTG if none).
    Drawing hands that cannot open are fully included.
    """
    n_seats = config.num_players
    n_buckets = len(feat.labels)
    call_freq = np.zeros((n_seats, n_buckets), dtype=np.float64)
    raise_freq = np.zeros((n_seats, n_buckets), dtype=np.float64)
    records: list[dict] = []

    pot0 = config.starting_pot
    sb = config.small_bet

    seat_iter = range(1, n_seats)  # UTG never faces an earlier open in this model
    if show_progress:
        seat_iter = tqdm(list(seat_iter), desc="response seats", unit="seat")

    for hero in seat_iter:
        opener_seat = 0 if hero == 1 else hero - 1
        # Prefer earliest opener model for multiway feel: average opens of seats before hero
        opener_freq = opening.open_freq[:hero].mean(axis=0)
        opp_scores = np.array([effective_hand_score(feat, i) for i in range(n_buckets)])
        opp_w = feat.weight * opener_freq
        if opp_w.sum() <= 0:
            opp_w = feat.weight * (feat.open_legal.astype(np.float64))

        # Players still left after hero may squeeze — light penalty
        behind = n_seats - hero - 1

        for i in range(n_buckets):
            hero_score = effective_hand_score(feat, i)
            eq = equity_vs_range(hero_score, opp_scores, opp_w)

            # Facing open: to_call = sb, pot ≈ pot0 + sb
            pot_face = pot0 + sb
            to_call = sb
            ev_fold = 0.0
            # Call then heads-up-ish showdown/draw approx
            pot_if_call = pot_face + to_call
            ev_call = -to_call + eq * pot_if_call
            # Extra callers behind reduce equity slightly
            if behind:
                ev_call -= 0.08 * behind * sb * max(0.0, 0.5 - eq)

            # Raise (open raise): invest 2*sb total on this street vs open
            # (call sb + raise sb). Approx pot and equity vs continuing opener.
            invest_raise = 2 * sb
            # Opener continues denser with strong range
            continue_thresh = 0.42
            cont_w = opp_w.copy()
            for j in range(n_buckets):
                if effective_hand_score(feat, j) < continue_thresh:
                    cont_w[j] *= 0.15
            eq_raise = equity_vs_range(hero_score, opp_scores, cont_w)
            fold_equity = float(np.clip(1.0 - cont_w.sum() / max(opp_w.sum(), 1e-9), 0.05, 0.70))
            pot_after_raise = pot_face + invest_raise  # if opener folds later terms differ
            ev_raise = (
                fold_equity * (pot_face)  # opener folds — win current pot (hero's raise comes back net pot_face)
                + (1.0 - fold_equity) * (-invest_raise + eq_raise * (pot_face + invest_raise + sb))
            )
            # Behind squeeze risk
            ev_raise -= 0.10 * behind * sb

            # Choose action
            best = ev_fold
            action = "Fold"
            c_f, r_f = 0.0, 0.0
            if ev_call > best + 1e-9:
                best = ev_call
                action = "Call"
                c_f = 1.0
            if ev_raise > best + 1e-9:
                best = ev_raise
                action = "Raise"
                c_f, r_f = 0.0, 1.0

            # Near ties → mix call/raise
            if abs(ev_call - ev_raise) < 0.05 * sb and max(ev_call, ev_raise) > ev_fold:
                action = "MixCallRaise"
                # weight toward higher EV
                total = max(ev_call, 0) + max(ev_raise, 0) + 1e-9
                c_f = max(ev_call, 0) / total
                r_f = max(ev_raise, 0) / total

            call_freq[hero, i] = c_f
            raise_freq[hero, i] = r_f

            # Keep rows that continue or are strong draws / openers
            if action == "Fold" and feat.draw_power[i] < 0.5 and feat.strength[i] < 0.4:
                continue
            records.append(
                {
                    "hero_seat": SEAT_NAMES[hero],
                    "hero_seat_index": hero,
                    "vs_opener_model": "avg_earlier",
                    "bucket": feat.labels[i],
                    "weight": feat.weight[i],
                    "action": action,
                    "call_freq": round(c_f, 4),
                    "raise_freq": round(r_f, 4),
                    "ev_fold": 0.0,
                    "ev_call": round(ev_call, 4),
                    "ev_raise": round(ev_raise, 4),
                    "equity_vs_opener": round(eq, 4),
                    "open_legal": bool(feat.open_legal[i]),
                    "draw_power": round(float(feat.draw_power[i]), 3),
                }
            )

    records.sort(
        key=lambda r: (r["hero_seat_index"], -r["raise_freq"], -r["call_freq"], -r["weight"])
    )
    return ResponseResult(records=records, call_freq=call_freq, raise_freq=raise_freq)
