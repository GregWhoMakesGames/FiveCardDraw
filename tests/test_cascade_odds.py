"""Acceptance pins for cascade / drawing-call odds fixtures."""

from math import comb

from fivecarddraw.validation.cascade_odds import (
    BUG_2TO1_COMBOS,
    CALL_2TO1_COMBOS,
    FFS13_COMBOS,
    FFS16_COMBOS,
    HANDS_NO_BUG,
    SUIT_HAIRCUT_BUG_FFS,
    SUIT_HAIRCUT_FFS_FFS,
    TOTAL_HANDS,
    adjusted_cascade_components,
    bn_bug_conditioned_2to1_rates,
    build_cascade_odds_payload,
    combined_draw_call_wins_vs_aa_plus,
    load_cascade_odds,
    p_one_seat_2to1,
    write_cascade_odds_fixture,
)


def test_combo_inventory_matches_enumeration():
    assert TOTAL_HANDS == comb(53, 5) == 2_869_685
    assert HANDS_NO_BUG == comb(52, 5) == 2_598_960
    assert BUG_2TO1_COMBOS == 17_280
    assert FFS16_COMBOS == 1_116
    assert FFS13_COMBOS == 4_224
    assert CALL_2TO1_COMBOS == 18_396


def test_bn_bug_conditioned_2to1_rates():
    """Exact one-seat rates; independent union for any of seats 1–7."""
    assert p_one_seat_2to1(bn_has_bug=True) == FFS16_COMBOS / HANDS_NO_BUG
    rates = bn_bug_conditioned_2to1_rates()
    # Mixture recovers the unconditional one-seat rate (law of total probability).
    p_bn_bug = comb(52, 4) / TOTAL_HANDS
    p_bn_no_bug = HANDS_NO_BUG / TOTAL_HANDS
    mix = (
        p_bn_bug * rates["p_one_seat_given_bn_has_bug"]
        + p_bn_no_bug * rates["p_one_seat_given_bn_no_bug"]
    )
    assert abs(mix - rates["p_one_seat_uncond"]) < 1e-15
    # Pins for the button_open_no_sandbagging Q1/Q2 table.
    assert abs(rates["p_any_independent_given_bn_has_bug"] - 0.00300194836447909) < 1e-12
    assert abs(rates["p_any_independent_given_bn_no_bug"] - 0.0482076295491638) < 1e-12
    assert abs(rates["p_any_independent_uncond"] - 0.0440194051518219) < 1e-12


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
