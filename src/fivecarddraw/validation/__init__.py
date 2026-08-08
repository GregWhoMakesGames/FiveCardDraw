"""Dealer-seat / opener equity validation (post-draw aware)."""

__all__ = [
    "adjusted_cascade_components",
    "build_cascade_odds_payload",
    "build_face_pair_outs_payload",
    "build_showdown_matrix_payload",
    "combined_draw_call_wins_vs_aa_plus",
    "load_cascade_odds",
    "load_face_pair_outs",
    "load_showdown_matrix",
    "run_draw_call_odds_analysis",
    "write_cascade_odds_fixture",
    "write_face_pair_outs_fixture",
    "write_showdown_matrix_fixture",
]


def __getattr__(name: str):
    if name == "run_draw_call_odds_analysis":
        from fivecarddraw.validation.draw_call_odds import run_draw_call_odds_analysis

        return run_draw_call_odds_analysis
    if name in {
        "adjusted_cascade_components",
        "build_cascade_odds_payload",
        "combined_draw_call_wins_vs_aa_plus",
        "load_cascade_odds",
        "write_cascade_odds_fixture",
    }:
        from fivecarddraw.validation import cascade_odds

        return getattr(cascade_odds, name)
    if name in {
        "build_face_pair_outs_payload",
        "load_face_pair_outs",
        "write_face_pair_outs_fixture",
    }:
        from fivecarddraw.validation import face_pair_outs

        return getattr(face_pair_outs, name)
    if name in {
        "build_showdown_matrix_payload",
        "load_showdown_matrix",
        "write_showdown_matrix_fixture",
    }:
        from fivecarddraw.validation import showdown_matrix

        return getattr(showdown_matrix, name)
    raise AttributeError(name)
