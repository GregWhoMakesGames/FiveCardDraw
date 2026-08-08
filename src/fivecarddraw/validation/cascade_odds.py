"""Stored calling / cascade odds for dealer-open validation.

Numbers are exact combinatorial counts where noted, or documented
approximations (suit haircuts, blocker-adjusted outs, outs/48 hits).

Import ``CASCADE_ODDS`` / ``load_cascade_odds`` for downstream EV work and tests.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from math import comb
from pathlib import Path
from typing import Any


TOTAL_HANDS = comb(53, 5)  # 2_869_685
UNKNOWN = 48
SEATS_FACING = 7

# --- Stage-A / Stage-B combo inventories (from draw_call_odds enumeration) ---
BUG_2TO1_COMBOS = 17_280
FFS16_COMBOS = 1_116  # four_flush_straight, exactly 16 outs, no bug
FFS13_COMBOS = 4_224  # four_flush_straight, exactly 13 outs, no bug
CALL_2TO1_COMBOS = BUG_2TO1_COMBOS + FFS16_COMBOS  # 18_396

# Bug outs among 2:1 bug hands: Counter({16: 14436, 19: 2088, 22: 756})
BUG_OUTS_MEAN = (16 * 14436 + 19 * 2088 + 22 * 756) / BUG_2TO1_COMBOS  # 16.625

# Suit-conflict haircuts (measured on disjoint samples)
SUIT_HAIRCUT_BUG_FFS = 0.15
SUIT_HAIRCUT_FFS_FFS = 0.12

# Exact ordered disjoint pair counts: # {(hand_a, hand_b)} with disjoint cards
# Denominator per ordered seat pair: C(53,5)*C(48,5)
ORDERED_DISJOINT_BUG_FFS16 = 12_237_684
ORDERED_DISJOINT_FFS16_FFS16 = 842_556
ORDERED_DISJOINT_BUG_FFS13 = 47_417_400
ORDERED_DISJOINT_FFS16_FFS13 = 3_161_976

TOTAL2 = TOTAL_HANDS * comb(48, 5)  # 4_913_773_104_240


def _pair_prob_unordered(ordered_disjoint_ab: int, *, symmetric_both_orientations: bool) -> float:
    """P(specific unordered seat pair hosts the two hand classes)."""
    # For fixed seats {i,j}, labeled (i,j) denominator is TOTAL2.
    # If classes differ, both orientations: (n_ab + n_ba) / TOTAL2 with n_ab == n_ba.
    # If same class (two FFS16), ordered count already assigns hand_i × hand_j.
    if symmetric_both_orientations:
        return (2 * ordered_disjoint_ab) / TOTAL2
    return ordered_disjoint_ab / TOTAL2


def raw_cascade_components(seats: int = SEATS_FACING) -> dict[str, float]:
    """Raw A, B, C1, C2, C among ``seats`` hands (no haircuts / order factor)."""
    pairs = comb(seats, 2)
    p_a = pairs * _pair_prob_unordered(ORDERED_DISJOINT_BUG_FFS16, symmetric_both_orientations=True)
    p_b = pairs * _pair_prob_unordered(ORDERED_DISJOINT_FFS16_FFS16, symmetric_both_orientations=False)
    p_c1 = pairs * _pair_prob_unordered(ORDERED_DISJOINT_BUG_FFS13, symmetric_both_orientations=True)
    p_c2 = pairs * _pair_prob_unordered(ORDERED_DISJOINT_FFS16_FFS13, symmetric_both_orientations=True)
    return {
        "A_raw": p_a,
        "B_raw": p_b,
        "C1_raw": p_c1,
        "C2_raw": p_c2,
        "C_raw": p_c1 + p_c2,
    }


def adjusted_cascade_components(seats: int = SEATS_FACING) -> dict[str, float]:
    """A′, B′, C/2 with suit haircuts (15% / 12%) and order factor on C."""
    raw = raw_cascade_components(seats)
    a_adj = raw["A_raw"] * (1.0 - SUIT_HAIRCUT_BUG_FFS)
    b_adj = raw["B_raw"] * (1.0 - SUIT_HAIRCUT_FFS_FFS)
    c_half = raw["C_raw"] / 2.0
    return {
        **raw,
        "A_prime": a_adj,
        "B_prime": b_adj,
        "C_half": c_half,
        "cascade_to_2": a_adj + b_adj + c_half,
    }


# --- Blocker-adjusted outs (documented approximation) -----------------------------
# User rule: with a bug in the other hand, FFS16→15 and FFS13→12 (bug is an out).
# Measured extra blockers from the other four cards (disjoint samples, n≈2–3k):
#   FFS16 outs in bug hand: mean ≈ 2.19  ⇒ extra beyond bug ≈ 1.19
#   FFS13 outs in bug hand: mean ≈ 1.98  ⇒ extra ≈ 0.98
#   FFS16 outs in other FFS16: mean ≈ 1.48
#   Bug outs in FFS16 hand: mean ≈ 1.68
# Effective outs ≈ nominal_after_bug_rule - extra_blockers.

@dataclass(frozen=True)
class DrawOutsApprox:
    """Effective outs after bug removal + quick mutual blocker haircut."""

    label: str
    outs: float
    notes: str


# Cascade type → (hand_a outs, hand_b outs) after adjustments
CASCADE_OUTS = {
    "A_bug_ffs16": (
        DrawOutsApprox(
            "bug",
            BUG_OUTS_MEAN - 1.68,
            "mean bug 2:1 outs 16.625 minus ~1.68 blocked by FFS16 hole cards",
        ),
        DrawOutsApprox(
            "ffs16",
            16 - 2.19,
            "16 outs; measured ~2.19 blocked by disjoint bug hand (includes bug)",
        ),
    ),
    "B_ffs16_ffs16": (
        DrawOutsApprox(
            "ffs16_a",
            16 - 1.48,
            "16 outs minus ~1.48 blocked by other FFS16",
        ),
        DrawOutsApprox(
            "ffs16_b",
            16 - 1.48,
            "symmetric",
        ),
    ),
    "C1_bug_ffs13": (
        DrawOutsApprox(
            "bug",
            BUG_OUTS_MEAN - 1.68,
            "reuse FFS16 blocker mean as proxy for FFS13 hole-card blockage on bug",
        ),
        DrawOutsApprox(
            "ffs13",
            13 - 1.98,
            "13 outs; measured ~1.98 blocked by disjoint bug hand (includes bug)",
        ),
    ),
    "C2_ffs16_ffs13": (
        DrawOutsApprox(
            "ffs16",
            16 - 1.48,
            "proxy: same mutual FFS blockage scale as B",
        ),
        DrawOutsApprox(
            "ffs13",
            13 - 1.48,
            "proxy: ~1.48 outs blocked by FFS16 partner",
        ),
    ),
}


def hit_prob(outs: float, unknown: int = UNKNOWN) -> float:
    return max(0.0, min(1.0, outs / unknown))


def both_hit_prob(outs_a: float, outs_b: float) -> float:
    """Independent outs/48 approximation for two one-card draws."""
    return hit_prob(outs_a) * hit_prob(outs_b)


def at_least_one_hit_prob(outs_a: float, outs_b: float) -> float:
    pa, pb = hit_prob(outs_a), hit_prob(outs_b)
    return pa + pb - pa * pb


def cascade_improve_and_win(
    seats: int = SEATS_FACING,
) -> dict[str, Any]:
    """Cascade rates × post-draw improve probs; win vs AA+ ≈ ≥1 hand hits straight+.

    Beating an opener that is AA or better (AA, two pair, trips, …) is approximated
    as: at least one cascading caller improves to category ≥ straight. Pat opener
    straight+/boat/flush rarities are ignored here (caller straight still loses to
    higher made hands — deferred).
    """
    adj = adjusted_cascade_components(seats)
    # Weight C_half between C1 and C2 by raw mass
    c1, c2 = adj["C1_raw"], adj["C2_raw"]
    c_raw = c1 + c2
    w_c1 = (c1 / c_raw) if c_raw else 0.0
    w_c2 = (c2 / c_raw) if c_raw else 0.0

    components = {
        "A_prime": {
            "rate": adj["A_prime"],
            "outs": CASCADE_OUTS["A_bug_ffs16"],
        },
        "B_prime": {
            "rate": adj["B_prime"],
            "outs": CASCADE_OUTS["B_ffs16_ffs16"],
        },
        "C_half_as_C1": {
            "rate": adj["C_half"] * w_c1,
            "outs": CASCADE_OUTS["C1_bug_ffs13"],
        },
        "C_half_as_C2": {
            "rate": adj["C_half"] * w_c2,
            "outs": CASCADE_OUTS["C2_ffs16_ffs13"],
        },
    }

    p_both = 0.0
    p_least = 0.0
    detail = {}
    for name, comp in components.items():
        oa, ob = comp["outs"]
        outs_a, outs_b = oa.outs, ob.outs
        bh = both_hit_prob(outs_a, outs_b)
        ah = at_least_one_hit_prob(outs_a, outs_b)
        rate = comp["rate"]
        p_both += rate * bh
        p_least += rate * ah
        detail[name] = {
            "rate": rate,
            "outs_a": outs_a,
            "outs_b": outs_b,
            "p_both_hit": bh,
            "p_at_least_one_hit": ah,
            "rate_times_both": rate * bh,
            "rate_times_at_least_one": rate * ah,
            "out_notes": [oa.notes, ob.notes],
        }

    return {
        "cascade_to_2": adj["cascade_to_2"],
        "p_cascade_and_both_improve": p_both,
        "p_cascade_and_at_least_one_improves": p_least,
        "p_cascade_beats_aa_plus_approx": p_least,
        "aa_plus_win_assumption": (
            "Caller improve to ≥ straight beats opener AA / two pair / trips; "
            "ignores opener already holding straight+ / flush / boat."
        ),
        "components": detail,
        "adjusted": adj,
    }


def single_16plus_call_and_win(seats: int = SEATS_FACING) -> dict[str, Any]:
    """P(a lone 16+ drawing call among ``seats`` hits ≥ straight) vs AA+ approx.

    Lone = has a 16+ call hand but not in the cascade-to-2 event set (A∪B∪C raw,
    before haircuts — slightly conservative removal of multi-call deals).
    """
    adj = adjusted_cascade_components(seats)
    p_bug = seats * BUG_2TO1_COMBOS / TOTAL_HANDS  # mutually exclusive across seats
    p_ffs16 = seats * FFS16_COMBOS / TOTAL_HANDS  # light overcount if 2+ FFS16; rare

    # Remove deals that are cascade-shaped (raw A, B, C) so we do not double-count
    # with cascade_improve_and_win.
    p_cascade_raw = adj["A_raw"] + adj["B_raw"] + adj["C_raw"]
    # Bug-only singles: bug present, no FFS16/FFS13 partner in the 7
    p_bug_single = max(0.0, p_bug - adj["A_raw"] - adj["C1_raw"])
    # FFS16 singles: approximate as p_ffs16 minus pairs already in A,B,C2
    # Each A/C2 deal has one FFS16; each B deal has two.
    p_ffs16_single = max(
        0.0, p_ffs16 - adj["A_raw"] - 2 * adj["B_raw"] - adj["C2_raw"]
    )

    # Hit probs without a cascade partner (no bug out-removal for lone FFS16;
    # lone bug uses mean outs).
    p_hit_bug = hit_prob(BUG_OUTS_MEAN)
    p_hit_ffs16 = hit_prob(16.0)

    p_win = p_bug_single * p_hit_bug + p_ffs16_single * p_hit_ffs16
    return {
        "p_bug_among_seats": p_bug,
        "p_ffs16_among_seats_lin": p_ffs16,
        "p_cascade_raw_removed": p_cascade_raw,
        "p_bug_single": p_bug_single,
        "p_ffs16_single": p_ffs16_single,
        "p_hit_bug": p_hit_bug,
        "p_hit_ffs16": p_hit_ffs16,
        "p_single_16plus_hits_straight": p_win,
        "p_single_beats_aa_plus_approx": p_win,
        "aa_plus_win_assumption": (
            "Improve to ≥ straight beats opener AA / two pair / trips; "
            "same caveat as cascade path."
        ),
    }


def combined_draw_call_wins_vs_aa_plus(seats: int = SEATS_FACING) -> dict[str, Any]:
    cas = cascade_improve_and_win(seats)
    single = single_16plus_call_and_win(seats)
    total = (
        cas["p_cascade_beats_aa_plus_approx"]
        + single["p_single_beats_aa_plus_approx"]
    )
    return {
        "seats_facing": seats,
        "cascade": cas,
        "single_16plus": single,
        "p_combined_beats_aa_plus_approx": total,
        "notes": (
            "Combined ≈ lone 16+ hit + cascade (≥1 of 2 hits). "
            "Does not yet include draws to pairs beating JJ/QQ/KK only."
        ),
    }


def build_cascade_odds_payload(seats: int = SEATS_FACING) -> dict[str, Any]:
    """Full JSON-serializable payload for fixtures / outputs."""
    adj = adjusted_cascade_components(seats)
    combined = combined_draw_call_wins_vs_aa_plus(seats)
    outs_serialized = {
        k: [
            {"label": a.label, "outs": a.outs, "notes": a.notes},
            {"label": b.label, "outs": b.outs, "notes": b.notes},
        ]
        for k, (a, b) in CASCADE_OUTS.items()
    }
    return {
        "meta": {
            "total_hands": TOTAL_HANDS,
            "unknown_cards": UNKNOWN,
            "seats_facing": seats,
            "outs_denominator": "48 (independent events)",
            "suit_haircut_bug_ffs": SUIT_HAIRCUT_BUG_FFS,
            "suit_haircut_ffs_ffs": SUIT_HAIRCUT_FFS_FFS,
        },
        "combos": {
            "bug_2to1": BUG_2TO1_COMBOS,
            "ffs16": FFS16_COMBOS,
            "ffs13": FFS13_COMBOS,
            "call_2to1_total": CALL_2TO1_COMBOS,
            "bug_outs_mean": BUG_OUTS_MEAN,
        },
        "exact_pair_counts": {
            "ordered_disjoint_bug_ffs16": ORDERED_DISJOINT_BUG_FFS16,
            "ordered_disjoint_ffs16_ffs16": ORDERED_DISJOINT_FFS16_FFS16,
            "ordered_disjoint_bug_ffs13": ORDERED_DISJOINT_BUG_FFS13,
            "ordered_disjoint_ffs16_ffs13": ORDERED_DISJOINT_FFS16_FFS13,
            "total2": TOTAL2,
        },
        "cascade_rates": adj,
        "effective_outs": outs_serialized,
        "combined_vs_aa_plus": combined,
    }


def default_fixture_path() -> Path:
    return Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "validation" / "cascade_odds.json"


def write_cascade_odds_fixture(
    path: Path | None = None,
    seats: int = SEATS_FACING,
) -> Path:
    path = path or default_fixture_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_cascade_odds_payload(seats)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def load_cascade_odds(path: Path | None = None) -> dict[str, Any]:
    path = path or default_fixture_path()
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Write cascade odds fixture / print summary")
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Fixture path (default: tests/fixtures/validation/cascade_odds.json)",
    )
    p.add_argument(
        "--also-outputs",
        action="store_true",
        help="Also write outputs/validation/cascade_odds.json",
    )
    args = p.parse_args()
    path = write_cascade_odds_fixture(args.output)
    print(f"Wrote {path}")
    if args.also_outputs:
        out = Path("outputs/validation/cascade_odds.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(build_cascade_odds_payload(), indent=2) + "\n")
        print(f"Wrote {out}")

    c = build_cascade_odds_payload()
    rates = c["cascade_rates"]
    comb = c["combined_vs_aa_plus"]
    print()
    print(f"cascade_to_2 A'+B'+C/2 = {rates['cascade_to_2']:.8f} ({100*rates['cascade_to_2']:.4f}%)")
    print(
        f"cascade & ≥1 improves = "
        f"{comb['cascade']['p_cascade_and_at_least_one_improves']:.8f} "
        f"({100*comb['cascade']['p_cascade_and_at_least_one_improves']:.4f}%)"
    )
    print(
        f"single 16+ hits = "
        f"{comb['single_16plus']['p_single_16plus_hits_straight']:.8f} "
        f"({100*comb['single_16plus']['p_single_16plus_hits_straight']:.4f}%)"
    )
    print(
        f"combined beat AA+ ≈ "
        f"{comb['p_combined_beats_aa_plus_approx']:.8f} "
        f"({100*comb['p_combined_beats_aa_plus_approx']:.4f}%)"
    )


if __name__ == "__main__":
    main()
