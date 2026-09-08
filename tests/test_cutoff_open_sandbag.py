"""CO open vs seats 1–6 sandbag rate (fold-to-raise bound)."""

from __future__ import annotations

import json
from pathlib import Path

from fivecarddraw.cards import parse_hand
from fivecarddraw.validation.cutoff_open_sandbag import (
    FOCUS_CLASSES,
    WORLD,
    break_even_p_raise,
    class_row,
    deal_mc_p_raise_given_passed_co,
    independent_p_raise_at_rate,
    invert_calibrated_rate,
    invert_independent_rate,
    load_co_zero_sandbag_leaf,
    mix_co_open,
)
from fivecarddraw.validation.sandbag_v1 import (
    FOLD_JJ_TO_RAISE_EV,
    PASS_EV,
    SANDBAG_WORLD_CO_VS_SEATS_1_6,
    SANDBAG_WORLD_SEATS_1_6_ONLY,
    SEAT_CO,
    SEAT_HJ,
    SEAT_LJ,
    aces_sandbag_seats,
    independent_p_raise_unconditional,
    is_sandbag_set,
    is_voluntary_opener,
    sandbag_seats,
)
from fivecarddraw.validation.showdown_matrix import classify_opener


FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "validation"
    / "cutoff_open_sandbag_v1.json"
)
CO_0PCT = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "validation"
    / "cutoff_open_summary.json"
)


def test_world_matches_seats_1_6_only_predicates():
    aa = classify_opener(parse_hand("As Ad 9c 8h 2d"))
    jj = classify_opener(parse_hand("Js Jd 9c 8h 2d"))
    tp = classify_opener(parse_hand("Ks Kd 9c 9h 2d"))
    assert WORLD == SANDBAG_WORLD_CO_VS_SEATS_1_6
    assert sandbag_seats(WORLD) == sandbag_seats(SANDBAG_WORLD_SEATS_1_6_ONLY)
    assert aces_sandbag_seats(WORLD) == frozenset({SEAT_HJ})
    assert SEAT_CO not in sandbag_seats(WORLD)

    assert is_sandbag_set(aa, SEAT_HJ, WORLD)
    assert not is_sandbag_set(aa, SEAT_CO, WORLD)
    assert is_voluntary_opener(aa, SEAT_CO, WORLD)
    assert is_voluntary_opener(aa, SEAT_LJ, WORLD)
    for seat in range(1, 7):
        assert is_sandbag_set(tp, seat, WORLD)
        assert not is_voluntary_opener(tp, seat, WORLD)
    assert not is_sandbag_set(tp, SEAT_CO, WORLD)
    for seat in range(1, 8):
        assert is_voluntary_opener(jj, seat, WORLD)
        assert not is_sandbag_set(jj, seat, WORLD)


def test_zero_pct_leaves_from_cutoff_open_fixture():
    """0% sandbag L is the existing CO lab — do not rebuild or use the BN leaf."""
    assert CO_0PCT.exists()
    data = json.loads(CO_0PCT.read_text(encoding="utf-8"))
    by = {r["co_class"]: r for r in data["by_class"]}
    jj = load_co_zero_sandbag_leaf("pair_J")
    qq = load_co_zero_sandbag_leaf("pair_Q")
    kk = load_co_zero_sandbag_leaf("pair_K")
    assert abs(jj - by["pair_J"]["ev_open"]) < 1e-12
    assert abs(qq - by["pair_Q"]["ev_open"]) < 1e-12
    assert abs(kk - by["pair_K"]["ev_open"]) < 1e-12
    # Product pin from the 0% lab: all three are +EV vs pass 0.
    assert jj > 1.0
    assert qq > jj
    assert kk > qq
    assert abs(jj - 1.43502) < 1e-12
    assert abs(qq - 1.55099) < 1e-12
    assert abs(kk - 1.6776) < 1e-12
    # Not the BN steal+6.9% leaf (~+$1.936).
    assert jj < 1.7
    mix0 = mix_co_open(0.0, jj)
    assert abs(mix0["ev_open"] - jj) < 1e-12
    assert mix0["opening_is_positive_ev"] is True


def test_independent_rate_curve_and_p1_matches_1_6_only():
    six = independent_p_raise_unconditional(SANDBAG_WORLD_SEATS_1_6_ONLY)
    co = independent_p_raise_unconditional(WORLD)
    assert abs(six["p_raise"] - co["p_raise"]) < 1e-15
    assert abs(independent_p_raise_at_rate(0.0) - 0.0) < 1e-15
    assert abs(independent_p_raise_at_rate(1.0) - co["p_raise"]) < 1e-12
    assert 0.47 < co["p_raise"] < 0.50
    # Writeup masses ≈ 0.7760 / 0.0821 / 0.1302.
    from fivecarddraw.validation.cutoff_open_sandbag import inventory_masses

    m = inventory_masses()
    assert abs(m["p_j"] - 0.7760) < 5e-4
    assert abs(m["p_s_early"] - 0.0821) < 5e-4
    assert abs(m["p_s_hj"] - 0.1302) < 5e-4
    p_half = independent_p_raise_at_rate(0.5)
    assert 0.0 < p_half < co["p_raise"]
    # Inversion recovers r=1 at the independent p(1).
    inv = invert_independent_rate(co["p_raise"])
    assert abs(float(inv["r"]) - 1.0) < 1e-6


def test_break_even_and_fold_mix():
    leaf = 1.43502
    p_star = break_even_p_raise(leaf)
    assert abs(p_star - leaf / (leaf + 2.0)) < 1e-12
    even = mix_co_open(p_star, leaf)
    assert abs(even["ev_open"] - PASS_EV) < 1e-12
    assert abs(mix_co_open(1.0, leaf)["ev_open"] - FOLD_JJ_TO_RAISE_EV) < 1e-12
    # Independent p(1) ≈ 0.482 sits above JJ's p* ≈ 0.418 ⇒ 100% independent mix is −EV.
    p1 = independent_p_raise_at_rate(1.0)
    assert mix_co_open(p1, leaf)["opening_is_negative_ev"] is True


def test_calibrated_rate_near_one():
    p_ind = independent_p_raise_at_rate(1.0)
    p_mc = p_ind * 1.03
    p_star = 0.42
    out = invert_calibrated_rate(p_star, p_mc_1=p_mc, p_ind_1=p_ind)
    assert 0.7 < float(out["r"]) < 1.0
    assert abs(float(out["kappa"]) - 1.03) < 1e-12
    assert abs(float(out["linear_r"]) - p_star / p_mc) < 1e-12
    # Reconstruct: kappa * p_ind(r) ≈ p_star.
    recon = float(out["kappa"]) * independent_p_raise_at_rate(float(out["r"]))
    assert abs(recon - p_star) < 1e-8


def test_small_deal_mc_co_hero_does_not_filter_bn():
    mc = deal_mc_p_raise_given_passed_co(n=400, seed=20260907, co_class="pair_J")
    assert mc.n_conditioned == 400
    assert mc.co_class == "pair_J"
    assert mc.world == WORLD
    assert 0.30 < mc.p_raise < 0.65
    assert mc.sandbag_seats_hist["0"] == mc.n_conditioned - mc.n_raise
    assert sum(mc.sandbag_seats_hist.values()) == 400
    assert mc.n_co_class >= 400
    # Independent planning is ~0.48; small-n band around that.
    leaf = load_co_zero_sandbag_leaf("pair_J")
    row = class_row(mc, leaf=leaf, p_ind_1=independent_p_raise_at_rate(1.0))
    assert row["ev_open_0pct"] == leaf
    recon = (1.0 - mc.p_raise) * leaf + mc.p_raise * FOLD_JJ_TO_RAISE_EV
    assert abs(row["ev_open_100pct"] - recon) < 1e-12


def test_fixture_pins_jj_qq_kk():
    assert FIXTURE.exists(), (
        "run python -m fivecarddraw.validation.cutoff_open_sandbag --write-fixture"
    )
    from fivecarddraw.validation.cutoff_open_sandbag import load_fixture

    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    live = load_fixture()
    assert data == live
    meta = data["meta"]
    assert meta["frame"] == "cutoff_open_sandbag_v1"
    assert meta["world"] == WORLD
    assert meta["sandbag_set"]["aces_sandbag_seats"] == [6]
    assert meta["sandbag_set"]["seat_7_co"] == "never_sandbags_opens_all_legal"
    assert meta["sandbag_set"]["seat_8_bn"] == "not_in_p_raise"
    assert meta["mc"]["n"] == 40_000
    assert meta["mc"]["seed"] == 20260907
    assert FOCUS_CLASSES == ("pair_J", "pair_Q", "pair_K")

    by = {r["co_class"]: r for r in data["by_class"]}
    assert set(by) == {"pair_J", "pair_Q", "pair_K"}
    # 0% leaves match the CO lab.
    for cls, leaf in (("pair_J", 1.43502), ("pair_Q", 1.55099), ("pair_K", 1.6776)):
        row = by[cls]
        assert abs(row["ev_no_raise_leaf"] - leaf) < 1e-12
        assert abs(row["ev_open_0pct"] - leaf) < 1e-12
        assert row["ev_open_0pct"] > PASS_EV
        assert row["raise_policy"] == "fold"
        mc = row["deal_mc"]
        assert mc["n"] == 40_000
        assert mc["seed"] == 20260907
        assert mc["n_conditioned"] == 40_000
        assert mc["co_class"] == cls
        recon = (1.0 - row["p_raise"]) * leaf + row["p_raise"] * FOLD_JJ_TO_RAISE_EV
        assert abs(row["ev_open_100pct"] - recon) < 1e-12
        assert 0.45 < row["p_raise"] < 0.55
        # Independent p(1) ~0.482; MC should sit a bit higher (joint enrichment).
        assert row["p_raise"] > row["independent_p_raise_1"] - 0.01

    jj = by["pair_J"]
    qq = by["pair_Q"]
    kk = by["pair_K"]
    assert abs(jj["p_raise"] - 0.493775) < 1e-12
    assert abs(qq["p_raise"] - 0.492775) < 1e-12
    assert abs(kk["p_raise"] - 0.5012) < 1e-12
    assert abs(jj["ev_open_100pct"] - (-0.26110700050000013)) < 1e-12
    assert abs(qq["ev_open_100pct"] - (-0.19884909724999988)) < 1e-12
    assert abs(kk["ev_open_100pct"] - (-0.16561311999999995)) < 1e-12
    assert "bn_class" not in jj["independent_blocked"]
    assert jj["independent_blocked"]["co_class"] == "pair_J"
    # Product: 0% +EV (already pinned). 100% is −EV for the face pairs.
    assert jj["opening_is_negative_ev"] is True
    assert qq["opening_is_negative_ev"] is True
    assert kk["opening_is_negative_ev"] is True
    a = data["answers"]
    assert a["q1_jj_plus_ev_at_100pct"] is False
    assert a["q2_jj_plus_ev_at_0pct"] is True
    assert a["binding_class"] == "pair_J"
    assert abs(a["q3_jj_r_calibrated"] - 0.787161321269366) < 1e-12
    assert 0.84 < a["q3_jj_r_linear"] < 0.85
    assert a["binding_r_calibrated"] == jj["r_calibrated"]
    # Binding = lowest r that still keeps the class +EV (JJ flips first).
    assert jj["r_calibrated"] <= qq["r_calibrated"] <= kk["r_calibrated"]
    assert jj["deal_mc"]["n_tried"] == 2_801_845
    assert jj["deal_mc"]["n_raise"] == 19_751


def test_pair_k_plus_joker_is_two_kings_bug_as_ace_kicker():
    """Bug is an ace, not a third king: KK+joker stays pair_K (ace kicker)."""
    from fivecarddraw.validation.cutoff_open_sandbag import (
        PAIR_K_ACE_IDS,
        PAIR_K_BUG_IDS,
        PAIR_K_NO_BUG_IDS,
        n_physical_kings,
    )

    assert classify_opener(parse_hand("Kh Kd 9s 7h 4c")) == "pair_K"
    assert classify_opener(parse_hand("Kh Kd Bu 9s 7h")) == "pair_K"
    assert classify_opener(parse_hand("Kh Bu 9s 7h 4c")) is None  # ace-high
    assert classify_opener(parse_hand("Kh Kd As 7h 4c")) == "pair_K"
    assert n_physical_kings(PAIR_K_BUG_IDS) == 2
    assert n_physical_kings(PAIR_K_NO_BUG_IDS) == 2
    assert n_physical_kings(PAIR_K_ACE_IDS) == 2


def test_sample_forced_blockers_match_class():
    from fivecarddraw.validation.cutoff_open_sandbag import (
        BUG_ID,
        has_physical_ace,
        sample_class_ids_forced,
    )

    rng = __import__("random").Random(20260907)
    bug_ids = sample_class_ids_forced("pair_K", rng, require_bug=True)
    ace_ids = sample_class_ids_forced("pair_K", rng, require_physical_ace=True)
    assert bug_ids is not None and BUG_ID in bug_ids
    assert _ids_to_cls_local(bug_ids) == "pair_K"
    assert ace_ids is not None and has_physical_ace(ace_ids)
    assert _ids_to_cls_local(ace_ids) == "pair_K"


def _ids_to_cls_local(ids):
    from fivecarddraw.cards import card_from_id

    return classify_opener(tuple(card_from_id(i) for i in ids))


def test_small_flavor_mc_bug_lowers_p_raise_vs_class_average():
    from fivecarddraw.validation.cutoff_open_sandbag import deal_mc_p_raise_co_flavor

    mc = deal_mc_p_raise_co_flavor(
        n=400, seed=20260907, co_class="pair_K", require_bug=True
    )
    assert mc.n_conditioned == 400
    assert mc.p_co_has_bug == 1.0
    # Class-average pair_K is ~0.50; the joker should cut sandbag-set mass.
    assert 0.15 < mc.p_raise < 0.55


def test_fixture_blockers_kk_joker():
    from fivecarddraw.validation.cutoff_open_sandbag import load_fixture

    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert data == load_fixture()
    blockers = data["blockers"]
    rem = blockers["remaining_exact"]
    assert rem["pair_k_bug"]["co_class"] == "pair_K"
    assert rem["pair_k_bug"]["has_bug"] is True
    assert rem["pair_k_bug"]["n_physical_kings"] == 2
    assert rem["pair_k_no_bug"]["two_pair_plus"] == 144_753
    assert rem["pair_k_bug"]["two_pair_plus"] == 133_259
    assert rem["pair_k_ace"]["two_pair_plus"] == 141_667
    assert rem["pair_k_bug"]["pair_A"] == 64_548
    assert rem["pair_k_ace"]["pair_A"] == 63_009
    assert rem["pair_k_bug"]["two_pair_aces_up"] == 14_688
    assert rem["pair_k_bug"]["two_pair_plus"] < rem["pair_k_no_bug"]["two_pair_plus"]
    assert rem["pair_k_bug"]["pair_A"] < rem["pair_k_no_bug"]["pair_A"]
    assert rem["pair_k_bug"]["two_pair_aces_up"] < rem["pair_k_no_bug"]["two_pair_aces_up"]
    assert rem["pair_k_ace"]["pair_A"] < rem["pair_k_no_bug"]["pair_A"]
    assert rem["pair_k_ace"]["two_pair_aces_up"] < rem["pair_k_no_bug"]["two_pair_aces_up"]

    bug = blockers["pair_k_bug"]["reweighted_leaf_mix"]
    ace = blockers["pair_k_ace_kicker"]["reweighted_leaf_mix"]
    kk = next(r for r in data["by_class"] if r["co_class"] == "pair_K")
    assert bug["deal_mc"]["n"] == 10_000
    assert bug["deal_mc"]["seed"] == 20260907
    assert bug["p_raise"] < kk["p_raise"]
    assert abs(bug["p_raise"] - 0.4523) < 1e-12
    assert bug["opening_is_positive_ev"] is True
    assert abs(bug["ev_open_100pct"] - 0.046901204362500226) < 1e-12
    ace_avg = blockers["pair_k_ace_kicker"]["avg_leaf_mix"]
    assert ace_avg["opening_is_negative_ev"] is True
    assert abs(ace["p_raise"] - 0.4718) < 1e-12
    ans = blockers["answers"]
    assert ans["pair_k_bug_plus_ev_at_100pct_reweighted"] is True
    assert ans["pair_k_ace_plus_ev_at_100pct_reweighted"] is False
    assert abs(data["answers"]["q3_jj_r_calibrated"] - 0.787161321269366) < 1e-12

