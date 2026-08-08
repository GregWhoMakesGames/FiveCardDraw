"""Acceptance pins for cascade / drawing-call odds fixtures."""

from math import comb

from fivecarddraw.validation.cascade_odds import (
    BUG_2TO1_COMBOS,
    CALL_2TO1_COMBOS,
    FFS13_COMBOS,
    FFS16_COMBOS,
    SUIT_HAIRCUT_BUG_FFS,
    SUIT_HAIRCUT_FFS_FFS,
    TOTAL_HANDS,
    adjusted_cascade_components,
    build_cascade_odds_payload,
    combined_draw_call_wins_vs_aa_plus,
    load_cascade_odds,
    write_cascade_odds_fixture,
)


def test_combo_inventory_matches_enumeration():
    assert TOTAL_HANDS == comb(53, 5) == 2_869_685
    assert BUG_2TO1_COMBOS == 17_280
    assert FFS16_COMBOS == 1_116
    assert FFS13_COMBOS == 4_224
    assert CALL_2TO1_COMBOS == 18_396


def test_cascade_to_2_rate_pinned():
    rates = adjusted_cascade_components()
    # A'+B'+C/2 ≈ 0.0308%
    assert abs(rates["cascade_to_2"] - 0.00030824) < 5e-7
    assert abs(rates["A_prime"] - rates["A_raw"] * (1 - SUIT_HAIRCUT_BUG_FFS)) < 1e-15
    assert abs(rates["B_prime"] - rates["B_raw"] * (1 - SUIT_HAIRCUT_FFS_FFS)) < 1e-15
    assert abs(rates["C_half"] - rates["C_raw"] / 2) < 1e-15


def test_bug_call_in_first_six_seats():
    p = 6 * BUG_2TO1_COMBOS / TOTAL_HANDS
    assert abs(p - 0.0361294) < 1e-8


def test_fixture_roundtrip(tmp_path):
    path = write_cascade_odds_fixture(tmp_path / "cascade_odds.json")
    loaded = load_cascade_odds(path)
    assert loaded["combos"]["call_2to1_total"] == 18_396
    assert "cascade_to_2" in loaded["cascade_rates"]
    assert loaded["combined_vs_aa_plus"]["p_combined_beats_aa_plus_approx"] > 0


def test_checked_in_fixture_matches_module():
    fixture = load_cascade_odds()
    live = build_cascade_odds_payload()
    assert abs(fixture["cascade_rates"]["cascade_to_2"] - live["cascade_rates"]["cascade_to_2"]) < 1e-12
    assert abs(
        fixture["combined_vs_aa_plus"]["p_combined_beats_aa_plus_approx"]
        - live["combined_vs_aa_plus"]["p_combined_beats_aa_plus_approx"]
    ) < 1e-12


def test_combined_exceeds_cascade_alone():
    comb = combined_draw_call_wins_vs_aa_plus()
    assert comb["p_combined_beats_aa_plus_approx"] > comb["cascade"][
        "p_cascade_beats_aa_plus_approx"
    ]
    assert build_cascade_odds_payload()["cascade_rates"]["cascade_to_2"] > 0
