"""Dealer-seat / opener equity validation (post-draw aware)."""

__all__ = [
    "adjusted_cascade_components",
    "build_cascade_odds_payload",
    "combined_draw_call_wins_vs_aa_plus",
    "load_cascade_odds",
    "run_draw_call_odds_analysis",
    "write_cascade_odds_fixture",
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
    raise AttributeError(name)
