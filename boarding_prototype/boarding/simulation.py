"""The simulation engine: a discrete-time system X(t+1) = F(X(t)), 1 step = 1 second."""

from collections import deque

import numpy as np

from .model import Aircraft, Passenger, State
from .strategies import BoardingStrategy
from .timing import FixedTiming, TimingModel


class Simulation:
    """One boarding run.

    Everything stochastic must draw from `self.rng` (seeded by `seed`), so a run is
    always reproducible: same inputs + same seed -> same trajectory and same T.
    The RNG is used first by the strategy (entry order), then by the timing model
    in the fixed update order of `step`.
    """

    def __init__(self, strategy: BoardingStrategy, aircraft: Aircraft = Aircraft(),
                 timing: TimingModel = FixedTiming(), seed: int = 0):
        self.strategy = strategy
        self.aircraft = aircraft
        self.timing = timing
        self.rng = np.random.default_rng(seed)
        self.passengers = aircraft.make_passengers()          # indexed by id
        order = strategy.order(self.passengers, self.rng)
        if sorted(passenger.id for passenger in order) != [passenger.id for passenger in self.passengers]:
            raise ValueError(f"{strategy!r} must return every passenger exactly once")
        self.entry_order: tuple[Passenger, ...] = tuple(order)
        self.queue: deque[Passenger] = deque(order)            # still outside
        # aisle[k] = passenger in cell k (1..n_rows). Index 0 (outside) stays None; the extra
        # cell n_rows+1 is never occupied, so "is the next cell free" needs no bounds check.
        self.aisle: list[Passenger | None] = [None] * (aircraft.n_rows + 2)
        self.t = 0                                             # equals T once finished
        self.n_seated = 0

    # ---- queries -------------------------------------------------------------
    @property
    def finished(self) -> bool:
        return self.n_seated == len(self.passengers)

    def count(self, state: State) -> int:
        return sum(passenger.state is state for passenger in self.passengers)

    # ---- dynamics ------------------------------------------------------------
    def step(self) -> "Simulation":
        """Advance one second. Fixed update order (this is what makes F well defined):

        1. Aisle cells from the back (row n) to the front (row 1). A cell vacated
           earlier in this step can be entered by the passenger directly behind it,
           so an unobstructed line moves forward together.
        2. Then, if aisle cell 1 is free, the next waiting passenger enters.
        """
        if self.finished:
            return self
        self.t += 1
        for cell in range(self.aircraft.n_rows, 0, -1):
            passenger = self.aisle[cell]
            if passenger is not None:
                self._update_in_aisle(passenger, cell)
        if self.queue and self.can_move(self.queue[0], 1):
            self._move(self.queue.popleft(), 0, 1)
        return self

    def run(self, max_steps: int = 100_000) -> int:
        """Run to completion and return the total boarding time T."""
        while not self.finished:
            if self.t >= max_steps:
                raise RuntimeError(f"Simulation did not finish within {max_steps} steps")
            self.step()
        return self.t

    def can_move(self, passenger: Passenger, to_cell: int) -> bool:
        """Movement constraint. Override to add rules (e.g. a cap on passengers in the aisle)."""
        return self.aisle[to_cell] is None

    # ---- internals -----------------------------------------------------------
    def _update_in_aisle(self, passenger: Passenger, cell: int) -> None:
        if passenger.state is State.STOWING:
            self._continue_stowing(passenger, cell)
        elif self.can_move(passenger, cell + 1):
            self._move(passenger, cell, cell + 1)
        else:
            passenger.state = State.BLOCKED

    def _continue_stowing(self, passenger: Passenger, cell: int) -> None:
        passenger.remaining_time -= 1
        if passenger.remaining_time == 0:
            passenger.state = State.SEATED
            self.n_seated += 1
            self.aisle[cell] = None

    def _move(self, passenger: Passenger, from_cell: int, to_cell: int) -> None:
        self.aisle[from_cell] = None           # cell 0 (outside) is always None
        self.aisle[to_cell] = passenger
        passenger.current_position = to_cell
        passenger.state = State.WALKING
        if to_cell == passenger.target_row:
            self._start_stowing(passenger)

    def _start_stowing(self, passenger: Passenger) -> None:
        stow = self.timing.stow_time(passenger, self)
        seat = self.timing.seat_time(passenger, self)
        if stow < 0 or seat < 0 or stow + seat < 1:
            raise ValueError(f"{self.timing!r} gave stow={stow}, seat={seat}; "
                             "need non-negative times with a total of at least 1 s")
        passenger.state = State.STOWING
        passenger.remaining_time = stow + seat
