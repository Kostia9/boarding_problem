"""Distributions of the time a passenger blocks the aisle at their row.

Every distribution keeps the mean given by `Simulation.time_at_row` (stow + sit time)
and only changes the spread. Each one stores what it needs in the passenger, so the
next second depends only on the current state and boarding stays a Markov chain:

- Geometric: sit down with probability 1/mean every second. Memoryless, so the
  state needs nothing else. Large spread (std ~ mean).
- Erlang(k): k geometric phases in a row (discrete Erlang / negative binomial); the
  state also holds the current phase. Less spread for larger k; k = 1 is Geometric.
- LogNormal(sigma): skewed, long right tail (a few very slow passengers); the time is
  drawn on arrival and the state holds the remaining seconds.
- Fixed: always the mean, rounded (the deterministic first prototype); the state
  holds the remaining seconds.

To add a distribution, subclass `Delay` and implement `start` and `tick`.
"""

import math


class Delay:
    """Interface: `start` when a passenger reaches their row, `tick` once per second after that."""

    name = "delay"

    def start(self, passenger, mean, rng):
        raise NotImplementedError

    def tick(self, passenger, rng):
        """Advance one second; return True when the passenger sits down."""
        raise NotImplementedError

    def __repr__(self):
        return self.name


class Geometric(Delay):
    name = "geometric"

    def start(self, passenger, mean, rng):
        passenger.finish_probability = 1 / mean

    def tick(self, passenger, rng):
        return rng.random() < passenger.finish_probability


class Erlang(Delay):
    """Sum of `phases` geometric phases with mean mean/phases each (needs phases <= mean)."""

    def __init__(self, phases=3):
        if isinstance(phases, bool) or not isinstance(phases, int) or phases < 1:
            raise ValueError(f"Expected a whole number of phases >= 1, got {phases!r}")
        self.phases = phases
        self.name = f"erlang(k={phases})"

    def start(self, passenger, mean, rng):
        if self.phases > mean:
            raise ValueError(f"Erlang with {self.phases} phases needs a mean of at least "
                             f"{self.phases} s, got {mean}")
        passenger.phases_left = self.phases
        passenger.finish_probability = self.phases / mean

    def tick(self, passenger, rng):
        if rng.random() < passenger.finish_probability:
            passenger.phases_left -= 1
        return passenger.phases_left == 0


class _Countdown(Delay):
    """Draws the whole time on arrival and counts it down."""

    def draw(self, mean, rng):
        raise NotImplementedError

    def start(self, passenger, mean, rng):
        passenger.remaining_time = max(1, round(self.draw(mean, rng)))

    def tick(self, passenger, rng):
        passenger.remaining_time -= 1
        return passenger.remaining_time == 0


class LogNormal(_Countdown):
    """Lognormal with the given mean; sigma is the std of log(time) (0.5: std ~ 0.53 x mean)."""

    def __init__(self, sigma=0.5):
        if isinstance(sigma, bool) or not sigma > 0:
            raise ValueError(f"Expected sigma > 0, got {sigma!r}")
        self.sigma = sigma
        self.name = f"lognormal(sigma={sigma:g})"

    def draw(self, mean, rng):
        return rng.lognormal(math.log(mean) - self.sigma ** 2 / 2, self.sigma)


class Fixed(_Countdown):
    name = "fixed"

    def draw(self, mean, rng):
        return mean


DELAYS = {
    "geometric": lambda **_: Geometric(),
    "erlang": lambda phases=3, **_: Erlang(phases),
    "lognormal": lambda sigma=0.5, **_: LogNormal(sigma),
    "fixed": lambda **_: Fixed(),
}
