"""Boarding as a discrete-time Markov chain, 1 step = 1 second.

The state is: who is still outside (and in which order), who stands in which aisle
cell and whether they are walking or stowing, and who is seated. Walking is
deterministic (one cell per second when the next cell is free). The time a passenger
blocks the aisle at their row is random, with the distribution given by `delay`
(see delays.py). By default it is geometric: the passenger sits down in each second
with probability p = 1 / (mean time at the row), independently of how long they have
stood there. This time is memoryless, so the next state depends only on the current
one: boarding is a Markov chain whose only absorbing state is "everyone seated", and
the total boarding time T is its absorption time. The other distributions keep the
Markov property by storing their phase or remaining time in the state.
"""

from collections import deque
from numbers import Integral, Real

import numpy as np

from .delays import Delay, Geometric
from .model import Aircraft, State
from .strategies import with_noncompliance


def _mean_seconds(value):
    if isinstance(value, bool) or not isinstance(value, Real) or not value >= 1:
        raise ValueError(f"Expected a mean time at the row of at least 1 second, got {value!r}")
    return float(value)


def _seconds(value, minimum):
    if isinstance(value, bool) or not isinstance(value, Integral) or value < minimum:
        raise ValueError(f"Expected an integer duration of at least {minimum} seconds, got {value!r}")
    return int(value)


class Simulation:
    """One boarding run. All randomness comes from `self.rng`, so a seed gives a reproducible run."""

    def __init__(self, strategy, aircraft=Aircraft(), seed=0, stow_time=5, seat_time=2,
                 noncompliance=0.0, delay=Geometric()):
        if not isinstance(delay, Delay):
            raise ValueError(f"delay must be a Delay (see boarding.delays), got {delay!r}")
        self.delay = delay
        self.aircraft = aircraft
        self.stow_time = _seconds(stow_time, 0)
        self.seat_time = _seconds(seat_time, 0)
        self.rng = np.random.default_rng(seed)
        self.passengers = aircraft.make_passengers()
        self.noncompliance = noncompliance
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
        """Mean seconds a passenger blocks the aisle at their row. Override for e.g. seat interference."""
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
                if self.delay.tick(p, self.rng):
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
            self.delay.start(p, _mean_seconds(self.time_at_row(p)), self.rng)
