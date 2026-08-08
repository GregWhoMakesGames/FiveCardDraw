from fivecarddraw.rules import DEFAULT_CONFIG, GameConfig, initial_predraw_state, pot_odds_to_call


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
