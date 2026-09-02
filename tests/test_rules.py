import pytest

from fivecarddraw.rules import (
    DEFAULT_CONFIG,
    GameConfig,
    SEAT_NAMES,
    initial_predraw_state,
    pot_odds_to_call,
)


def test_default_stakes():
    assert DEFAULT_CONFIG.ante == 0.25
    assert DEFAULT_CONFIG.small_bet == 2.0
    assert DEFAULT_CONFIG.big_bet == 4.0
    assert DEFAULT_CONFIG.starting_pot == 2.0
    assert DEFAULT_CONFIG.max_raises == 3


def test_open_updates_pot():
    st = initial_predraw_state()
    st2 = st.after_open(seat=0)
    assert st2.pot == 4.0
    assert st2.amount_to_call == 2.0
    assert st2.opener_seat == 0


def test_raise_cap():
    cfg = GameConfig(max_raises=1)
    st = initial_predraw_state(cfg).after_open(0)
    st = st.after_raise()
    assert st.raises_used == 1
    assert not st.can_raise


def test_pot_odds():
    assert abs(pot_odds_to_call(8.0, 2.0) - 0.2) < 1e-9
    assert pot_odds_to_call(6.0, 0.0) == 0.0


def test_call_adds_to_pot():
    st = initial_predraw_state().after_open(seat=0)
    st2 = st.after_call()
    assert st2.pot == 6.0
    assert st2.amount_to_call == 2.0


def test_raise_cap_raises_when_exceeded():
    cfg = GameConfig(max_raises=1)
    st = initial_predraw_state(cfg).after_open(0).after_raise()
    with pytest.raises(ValueError, match="raise cap"):
        st.after_raise()


def test_v1_is_eight_handed():
    with pytest.raises(ValueError):
        GameConfig(num_players=6)


# INDEX.md seats 1–8: UTG, UTG+1, UTG+2, UTG+3, LJ, HJ, CO, BN.
# Code currently labels 0–7 as UTG, UTG+1, UTG+2, Lojack, Hijack, Cutoff, Button, Dealer.
@pytest.mark.xfail(
    strict=True,
    reason=(
        "SEAT_NAMES uses 6-max labels (Lojack…Button+Dealer) instead of the "
        "research index UTG…UTG+3, LJ, HJ, CO, BN. Last-to-act index 7 is "
        "BN in the paper; code calls it Dealer and also has a separate Button."
    ),
)
def test_seat_names_match_research_index():
    assert SEAT_NAMES == (
        "UTG",
        "UTG+1",
        "UTG+2",
        "UTG+3",
        "LJ",
        "HJ",
        "CO",
        "BN",
    )
