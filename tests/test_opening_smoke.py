"""Smoke test for opening/response/raise solvers on a tiny synthetic feature set."""

import numpy as np

from fivecarddraw.predraw.model import BucketFeatures
from fivecarddraw.predraw.opening import solve_opening
from fivecarddraw.predraw.raise_tree import solve_raise_tree
from fivecarddraw.predraw.response import solve_responses
from fivecarddraw.rules import GameConfig


def _tiny_features() -> BucketFeatures:
    labels = [
        "one_pair|pair14:xxx|faces0|A2|noBu|no_draw|open",
        "one_pair|pair11:xxx|faces0|A0|noBu|no_draw|open",
        "high_card|hc14:Axxxx|faces0|A1|Bu|bug_sf_draw_high|pass",
        "high_card|hc9:xxxxx|faces0|A0|noBu|no_draw|pass",
    ]
    n = len(labels)
    return BucketFeatures(
        strength=np.array([0.55, 0.40, 0.20, 0.05]),
        draw_power=np.array([0.0, 0.0, 0.95, 0.05]),
        open_legal=np.array([True, True, False, False]),
        weight=np.array([1000.0, 2000.0, 500.0, 50000.0]),
        faces=np.array([0.0, 0.0, 0.0, 0.0]),
        has_bug=np.array([0.0, 0.0, 1.0, 0.0]),
        labels=labels,
    )


def test_solve_pipeline_smoke():
    feat = _tiny_features()
    cfg = GameConfig(max_raises=3)
    opening = solve_opening(feat, cfg, show_progress=False)
    assert opening.open_freq.shape == (8, 4)
    # Aces should open somewhere
    assert opening.open_freq[:, 0].max() > 0.5
    # Junk cannot open
    assert opening.open_freq[:, 3].sum() == 0

    responses = solve_responses(feat, opening, cfg, show_progress=False)
    # Big bug SF draw should continue somewhere
    assert (responses.call_freq[:, 2] + responses.raise_freq[:, 2]).max() > 0.5

    raises = solve_raise_tree(feat, opening, responses, cfg, show_progress=False)
    assert isinstance(raises.records, list)
