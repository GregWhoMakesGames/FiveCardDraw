"""Face-pair outs among drawing callers — unit + fixture pins."""

from fivecarddraw.cards import parse_hand
from fivecarddraw.hand_rank import HandCategory, evaluate_hand, can_open_jacks_or_better
from fivecarddraw.validation.draw_call_odds import DrawHandResult, classify_draw
from fivecarddraw.validation.face_pair_outs import (
    TARGET_ORDER,
    face_pair_outs_for_hand,
    load_face_pair_outs,
)


def test_bug_straight_draw_can_hit_aa_with_four_aces():
    cards = parse_hand("Bu 9h 8d 7c 2s")
    assert not can_open_jacks_or_better(cards)
    keep = tuple(c for c in cards if str(c) != "2s")
    hand = DrawHandResult(
        cards=cards,
        discard=next(c for c in cards if str(c) == "2s"),
        keep=keep,
        outs=16,
        undealt=48,
        has_bug=True,
        draw_class=classify_draw(keep),
    )
    fp = {x.target: x for x in face_pair_outs_for_hand(hand)}
    assert "AA" in fp
    assert fp["AA"].n_outs == 4
    assert fp["AA"].n_pure == 4
    ace = next(c for c in parse_hand("As Kh Qd Jc 9s") if str(c) == "As")
    v = evaluate_hand((*keep, ace))
    assert v.category == HandCategory.ONE_PAIR
    assert v.tiebreak[0] == 14


def test_fixture_call_2to1_buckets_pinned():
    data = load_face_pair_outs()
    s = data["sets"]["call_2to1"]
    assert s["n_hands"] == 18_396
    assert s["n_with_face_pair_draw"] == 15_444
    assert s["by_target"]["AA"]["hands_that_can_make"] == 13_248
    assert s["by_target"]["AA"]["outs_dist"] == {"3": 4680, "4": 8568}
    assert s["by_target"]["KK"]["hands_that_can_make"] == 660
    assert s["by_target"]["KK"]["outs_dist"] == {"3": 660}
    assert s["by_target"]["QQ"]["hands_that_can_make"] == 2556
    assert s["by_target"]["JJ"]["hands_that_can_make"] == 4320
    for t in TARGET_ORDER:
        n = s["by_target"][t]["hands_that_can_make"]
        if n:
            assert s["by_target"][t]["also_straight_plus_outs_dist"] == {"0": n}


def test_ffs16_cannot_make_aa():
    data = load_face_pair_outs()
    assert data["sets"]["ffs16"]["by_target"]["AA"]["hands_that_can_make"] == 0
    assert data["sets"]["ffs16"]["n_with_face_pair_draw"] == 324
