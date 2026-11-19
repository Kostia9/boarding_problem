"""Discrete-time boarding simulation, 1 step = 1 second."""

from collections import deque
from numbers import Integral

import numpy as np

from .model import Aircraft, State


def _seconds(value, minimum):
    if isinstance(value, bool) or not isinstance(value, Integral) or value < minimum:
        raise ValueError(f"Expected an integer duration of at least {minimum} seconds, got {value!r}")
    return int(value)


class Simulation:
    """One boarding run. All randomness comes from `self.rng`, so a seed gives a reproducible run."""

    def __init__(self, strategy, aircraft=Aircraft(), seed=0, stow_time=5, seat_time=2):
        self.aircraft = aircraft
        self.stow_time = _seconds(stow_time, 0)
        self.seat_time = _seconds(seat_time, 0)
        self.rng = np.random.default_rng(seed)
        self.passengers = aircraft.make_passengers()
        self.entry_order = list(strategy(self.passengers.copy(), self.rng))
        if sorted(map(id, self.entry_order)) != sorted(map(id, self.passengers)):
            raise ValueError("Strategy must return each original passenger exactly once")
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
        return self.stow_time + self.seat_time

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
            elif self.aisle[cell + 1] is None:
                self._move(p, cell + 1)
            else:
                p.state = State.BLOCKED
        if self.queue and self.aisle[1] is None:
            self._move(self.queue.popleft(), 1)

    def run(self):
        """Run to the end and return the total boarding time T in seconds."""
        while not self.finished:
            self.step()
        return self.t

    def _move(self, p, cell):
        self.aisle[p.current_position] = None
        self.aisle[cell] = p
        p.current_position = cell
        p.state = State.WALKING
        if cell == p.target_row:
            p.state = State.STOWING
            p.remaining_time = _seconds(self.time_at_row(p), 1)
