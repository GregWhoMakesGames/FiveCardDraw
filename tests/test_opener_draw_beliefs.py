"""Tests for Step 0 opener draw belief tables."""

from __future__ import annotations

import json
from pathlib import Path

from fivecarddraw.validation.opener_draw_beliefs import (
    PAIR_D3,
    exact_beliefs_given_d,
)
from fivecarddraw.validation.showdown_matrix import OPENER_CLASSES


FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "validation"
    / "opener_draw_beliefs.json"
)


def test_exact_beliefs_d3_is_pure_pair_under_pairs_d3():
    # Minimal fake inventory: 10 of each class
    inv = {c: [tuple(range(5))] * 10 for c in OPENER_CLASSES}
    b = exact_beliefs_given_d(inv, PAIR_D3)
    assert b["d3_pair_family_mass"] == 1.0
    assert set(b["p_family_given_d"]["3"]) == {"pair"}
    assert b["p_family_given_d"]["2"]["trips"] == 1.0
    assert "four_of_a_kind" in b["p_family_given_d"]["1"]


def test_fixture_d3_nakedness_and_structure():
    assert FIXTURE.exists(), "run analyze-opener-draw-beliefs --write-fixture"
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert data["meta"]["step"] == 0
    assert data["meta"]["seed"] == 20260809

    h = data["highlights"]
    # Under pairs always d=3, every d=3 deal is a pair start
    assert h["d3_under_pairs_d3"]["d3_pair_family_mass"] == 1.0
    assert h["d3_under_pairs_d3"]["p_d3"] > 0.5  # pairs dominate opener mass
    # Diverting all pairs off d=3 empties that line
    assert h["d3_under_pairs_d2"]["p_d3"] == 0.0
    assert h["d3_under_pairs_d1"]["p_d3"] == 0.0
    assert h["d3_under_pairs_stand"]["p_d3"] == 0.0

    # JJ d=3 mostly stays one pair; AA improves more often (bug / ace paths)
    jj3 = next(
        x
        for x in data["finals_by_class_d"]
        if x["opener_class"] == "pair_J" and x["n_draw"] == 3
    )
    assert jj3["p_final"]["one_pair"] > 0.7
    aa3 = next(
        x
        for x in data["finals_by_class_d"]
        if x["opener_class"] == "pair_A" and x["n_draw"] == 3
    )
    assert aa3["p_final"]["one_pair"] > 0.6
    assert aa3["p_final"]["one_pair"] < jj3["p_final"]["one_pair"]
