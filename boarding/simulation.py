"""Discrete-time boarding simulation, 1 step = 1 second."""

from collections import deque
from numbers import Integral

import numpy as np

from .model import Aircraft, State
from .strategies import with_noncompliance


def _seconds(value, minimum):
    if isinstance(value, bool) or not isinstance(value, Integral) or value < minimum:
        raise ValueError(f"Expected an integer duration of at least {minimum} seconds, got {value!r}")
    return int(value)


class Simulation:
    """One boarding run. All randomness comes from `self.rng`, so a seed gives a reproducible run.

    Each passenger gets a geometric stow time with mean
    `stow_time` seconds, followed by the fixed sitting time.
    load_factor < 1 leaves a random share of the seats empty.
    Empty seats and stow times are drawn before the strategy runs, so for a given seed
    every strategy boards the same passengers with the same luggage.
    """

    def __init__(self, strategy, aircraft=Aircraft(), seed=0, stow_time=5, seat_time=2,
                 *, load_factor=1, noncompliance=0, block_probability=0):
        self.aircraft = aircraft
        self.stow_time = _seconds(stow_time, 1)
        self.seat_time = _seconds(seat_time, 0)
        self.rng = np.random.default_rng(seed)
        self.passengers = self._fill_seats(load_factor)
        self._draw_stow_times()
        if not 0 <= block_probability <= 1:
            raise ValueError("block_probability must be between 0 and 1")
        if block_probability:
            # Sample blockers independently of the strategy and queue order.
            block_rng = np.random.Generator(self.rng.bit_generator.jumped())
            for passenger in self.passengers:
                passenger.blocks_behind = block_rng.random() < block_probability
        order = list(strategy(self.passengers.copy(), self.rng))
        if sorted(map(id, order)) != sorted(map(id, self.passengers)):
            raise ValueError("Strategy must return each original passenger exactly once")
        self.entry_order = with_noncompliance(order, noncompliance, self.rng)
        self.queue = deque(self.entry_order)             # passengers still outside
        self.aisle = [None] * (aircraft.n_rows + 1)      # aisle[k] = passenger in cell k (0 unused)
        self.t = 0
        self.n_seated = 0

    @property
    def finished(self):
        return self.n_seated == len(self.passengers)

    def count(self, state):
        return sum(p.state is state for p in self.passengers)

    def time_at_row(self, passenger):
        """Seconds a passenger blocks the aisle at their row. Override for e.g. seat interference."""
        return passenger.stow_time + self.seat_time

    def step(self):
        """Advance one second.

        Aisle cells are updated from the back to the front, so a line of passengers
        can move forward together. Then the next passenger enters if cell 1 is free.
        """
        if self.finished:
            return
        self.t += 1
        for cell in range(self.aircraft.n_rows, 0, -1):
            p = self.aisle[cell]
            if p is None:
                continue
            if p.state is State.STOWING:
                p.remaining_time -= 1
                if p.remaining_time == 0:
                    p.state = State.SEATED
                    self.aisle[cell] = None
                    self.n_seated += 1
            elif self._can_enter(cell + 1):
                self._move(p, cell + 1)
            else:
                p.state = State.BLOCKED
        if self.queue and self._can_enter(1):
            self._move(self.queue.popleft(), 1)

    def run(self):
        """Run to the end and return the total boarding time T in seconds."""
        while not self.finished:
            self.step()
        return self.t

    def _fill_seats(self, load_factor):
        passengers = self.aircraft.make_passengers()
        if not 0 < load_factor <= 1:
            raise ValueError(f"load_factor must be in (0, 1], got {load_factor!r}")
        if load_factor == 1:
            return passengers
        n = round(load_factor * len(passengers))
        if n == 0:
            raise ValueError(f"load_factor {load_factor!r} leaves the cabin empty")
        keep = np.sort(self.rng.choice(len(passengers), size=n, replace=False))
        return [passengers[i] for i in keep]

    def _draw_stow_times(self):
        times = self.rng.geometric(1 / self.stow_time, size=len(self.passengers))
        for p, t in zip(self.passengers, times):
            p.stow_time = int(t)

    def _can_enter(self, cell):
        if self.aisle[cell] is not None:
            return False
        ahead = self.aisle[cell + 1] if cell < self.aircraft.n_rows else None
        return not (ahead and ahead.blocks_behind and ahead.state is State.STOWING
                    and ahead.remaining_time > self.seat_time)

    def _move(self, p, cell):
        self.aisle[p.current_position] = None
        self.aisle[cell] = p
        p.current_position = cell
        p.state = State.WALKING
        if cell == p.target_row:
            p.state = State.STOWING
            p.remaining_time = _seconds(self.time_at_row(p), 1)


def monte_carlo(strategy, n_runs, **kwargs):
    """Boarding times T of `n_runs` runs with seeds 0..n_runs-1 (kwargs go to Simulation)."""
    return np.array([Simulation(strategy, seed=k, **kwargs).run() for k in range(n_runs)])
