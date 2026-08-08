"""Game configuration, positions, and betting structure."""

from __future__ import annotations

from dataclasses import dataclass


SEAT_NAMES = (
    "UTG",  # left of dealer (first to act pre-draw)
    "UTG+1",
    "UTG+2",
    "Lojack",
    "Hijack",
    "Cutoff",
    "Button",
    "Dealer",  # last to act pre-draw; dealer button
)


@dataclass(frozen=True, slots=True)
class GameConfig:
    """Fixed-limit five-card draw configuration for v1."""

    num_players: int = 8
    ante: float = 0.25
    small_bet: float = 2.0
    big_bet: float = 4.0
    # Pre-draw uses small bet; post-draw (later) uses big bet.
    max_raises: int = 3  # bet + 3 raises; set 1 for simplification
    jacks_or_better: bool = True
    include_bug: bool = True

    def __post_init__(self) -> None:
        if self.num_players != 8:
            raise ValueError("v1 supports exactly 8 players")
        if self.max_raises < 1:
            raise ValueError("max_raises must be >= 1")

    @property
    def starting_pot(self) -> float:
        return self.num_players * self.ante

    @property
    def ante_to_small_bet_ratio(self) -> float:
        return self.ante / self.small_bet

    @property
    def max_bets_on_street(self) -> int:
        """Number of bet increments allowed: open/bet + raises."""
        return 1 + self.max_raises

    def seat_name(self, seat_index: int) -> str:
        if not 0 <= seat_index < self.num_players:
            raise IndexError(seat_index)
        return SEAT_NAMES[seat_index]


DEFAULT_CONFIG = GameConfig()


@dataclass(frozen=True, slots=True)
class StreetState:
    """Betting state on the current street (pre-draw for v1)."""

    pot: float
    bet_size: float
    amount_to_call: float
    raises_used: int
    max_raises: int
    opener_seat: int | None = None

    @property
    def can_raise(self) -> bool:
        return self.raises_used < self.max_raises

    def after_fold(self) -> StreetState:
        return self

    def after_call(self, n_callers: int = 1) -> StreetState:
        return StreetState(
            pot=self.pot + self.amount_to_call * n_callers,
            bet_size=self.bet_size,
            amount_to_call=self.amount_to_call,
            raises_used=self.raises_used,
            max_raises=self.max_raises,
            opener_seat=self.opener_seat,
        )

    def after_open(self, seat: int) -> StreetState:
        return StreetState(
            pot=self.pot + self.bet_size,
            bet_size=self.bet_size,
            amount_to_call=self.bet_size,
            raises_used=0,
            max_raises=self.max_raises,
            opener_seat=seat,
        )

    def after_raise(self) -> StreetState:
        if not self.can_raise:
            raise ValueError("raise cap reached")
        # Caller puts in call + one bet; pot increases by amount_to_call + bet_size
        # from the raiser's perspective relative to prior amount_to_call.
        add = self.amount_to_call + self.bet_size
        return StreetState(
            pot=self.pot + add,
            bet_size=self.bet_size,
            amount_to_call=self.bet_size,  # others now face one bet more
            raises_used=self.raises_used + 1,
            max_raises=self.max_raises,
            opener_seat=self.opener_seat,
        )


def initial_predraw_state(config: GameConfig = DEFAULT_CONFIG) -> StreetState:
    return StreetState(
        pot=config.starting_pot,
        bet_size=config.small_bet,
        amount_to_call=0.0,
        raises_used=0,
        max_raises=config.max_raises,
        opener_seat=None,
    )


def pot_odds_to_call(pot: float, to_call: float) -> float:
    """Required equity to break even on a call (ignoring implied/reverse implied)."""
    if to_call <= 0:
        return 0.0
    return to_call / (pot + to_call)
