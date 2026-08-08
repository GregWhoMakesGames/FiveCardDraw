"""Shared approximate EV model for pre-draw decisions.

This is intentionally approximate (position-by-position), not full multiway Nash.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from fivecarddraw.abstraction import AbstractionTable
from fivecarddraw.rules import GameConfig


@dataclass(slots=True)
class BucketFeatures:
    strength: np.ndarray  # 0..1 percentile-like made-hand strength
    draw_power: np.ndarray  # 0..1 draw strength for non-made / speculative
    open_legal: np.ndarray
    weight: np.ndarray
    faces: np.ndarray
    has_bug: np.ndarray
    labels: list[str]


def extract_features(table: AbstractionTable) -> BucketFeatures:
    n = table.num_buckets
    strength = np.zeros(n, dtype=np.float64)
    draw_power = np.zeros(n, dtype=np.float64)
    faces = np.zeros(n, dtype=np.float64)
    has_bug = np.zeros(n, dtype=np.float64)
    open_legal = np.array(table.bucket_open_legal, dtype=bool)
    weight = np.array(table.bucket_weight, dtype=np.float64)

    for i, label in enumerate(table.bucket_labels):
        parts = label.split("|")
        category = parts[0]
        detail = parts[1]
        face_s = parts[2]  # facesN
        bug_s = parts[4]
        draw = parts[5]
        faces[i] = float(face_s.replace("faces", ""))
        has_bug[i] = 1.0 if bug_s == "Bu" else 0.0
        strength[i] = _category_strength(category, detail)
        draw_power[i] = _draw_power(draw, category)

    # Normalize strength by weight percentile among all buckets
    order = np.argsort(strength)
    cdf = np.zeros(n, dtype=np.float64)
    total_w = weight.sum()
    running = 0.0
    for idx in order:
        running += weight[idx]
        cdf[idx] = running / total_w
    # Blend raw category score with weight percentile
    strength = 0.6 * strength + 0.4 * cdf

    return BucketFeatures(
        strength=strength,
        draw_power=draw_power,
        open_legal=open_legal,
        weight=weight,
        faces=faces,
        has_bug=has_bug,
        labels=list(table.bucket_labels),
    )


def _category_strength(category: str, detail: str) -> float:
    base = {
        "high_card": 0.05,
        "one_pair": 0.25,
        "two_pair": 0.55,
        "three_of_a_kind": 0.68,
        "straight": 0.78,
        "flush": 0.82,
        "full_house": 0.90,
        "four_of_a_kind": 0.95,
        "straight_flush": 0.98,
        "five_aces": 1.0,
    }.get(category, 0.1)

    if category == "one_pair" and detail.startswith("pair"):
        # pair14:... etc
        try:
            pair_rank = int(detail.split(":")[0].replace("pair", ""))
            base = 0.15 + (pair_rank - 2) * (0.35 / 12.0)
        except ValueError:
            pass
    return float(np.clip(base, 0.0, 1.0))


def _draw_power(draw: str, category: str) -> float:
    if draw.startswith("made_"):
        return 0.0
    mapping = {
        "bug_sf_draw_high": 0.95,
        "bug_sf_draw_med": 0.80,
        "bug_flush_or_better": 0.85,
        "bug_flush_draw": 0.70,
        "bug_sf_draw_low": 0.55,
        "four_flush": 0.60,
        "bug_straight_draw_4": 0.65,
        "bug_straight_draw_3": 0.50,
        "bug_straight_draw_2": 0.35,
        "straight_draw_4": 0.40,
        "straight_draw_3": 0.28,
        "straight_draw_2": 0.18,
        "three_flush": 0.20,
        "bug_ace_material": 0.25,
        "no_draw": 0.05,
    }
    return mapping.get(draw, 0.1)


def effective_hand_score(feat: BucketFeatures, i: int) -> float:
    """Combined playability for call/raise: made strength or big draw."""
    return float(max(feat.strength[i], 0.85 * feat.draw_power[i] + 0.15 * feat.strength[i]))


def blocker_open_multiplier(feat: BucketFeatures, i: int) -> float:
    """Opponents open slightly less often when we hold faces/aces/bug."""
    # Each face blocks openers; bug/aces block ace openers
    mult = 1.0 - 0.03 * feat.faces[i] - 0.04 * feat.has_bug[i]
    if "A" in feat.labels[i].split("|")[1] or "|A" in feat.labels[i]:
        mult -= 0.02
    return float(np.clip(mult, 0.70, 1.0))


def equity_vs_range(
    hero_score: float,
    range_scores: np.ndarray,
    range_weights: np.ndarray,
) -> float:
    """Sigmoid-ish equity from score differences."""
    w = range_weights.sum()
    if w <= 0:
        return 0.55
    # P(win) ≈ mean sigmoid(scale * (hero - villain))
    delta = hero_score - range_scores
    p = 1.0 / (1.0 + np.exp(-6.0 * delta))
    # ties ~ small
    equity = float(np.sum(p * range_weights) / w)
    return float(np.clip(equity, 0.02, 0.98))


def normalize_weights(w: np.ndarray) -> np.ndarray:
    s = w.sum()
    if s <= 0:
        return w
    return w / s


def open_freq_prior(feat: BucketFeatures, config: GameConfig) -> np.ndarray:
    """Baseline open frequencies before seat-specific solving (open-legal only)."""
    freq = np.zeros(feat.weight.shape[0], dtype=np.float64)
    for i in range(len(freq)):
        if not feat.open_legal[i]:
            continue
        # Stronger made hands open more often in the prior
        s = feat.strength[i]
        if s >= 0.55:
            freq[i] = 1.0
        elif s >= 0.35:
            freq[i] = 0.7
        elif s >= 0.28:
            freq[i] = 0.25
        else:
            freq[i] = 0.05
    return freq
