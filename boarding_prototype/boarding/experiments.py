"""Monte Carlo: boarding time T over many seeds."""

from dataclasses import dataclass

import numpy as np

from .model import Aircraft
from .simulation import Simulation


@dataclass(frozen=True)
class Summary:
    mean: float
    std: float
    ci95: float      # half-width of the 95 % confidence interval of the mean
    min: int
    max: int
    runs: int

    @classmethod
    def of(cls, times):
        t = np.asarray(times, dtype=float)
        std = float(t.std(ddof=1)) if len(t) > 1 else 0.0
        return cls(mean=float(t.mean()), std=std, ci95=1.96 * std / np.sqrt(len(t)),
                   min=int(t.min()), max=int(t.max()), runs=len(t))


def monte_carlo(strategy, runs=1000, aircraft=Aircraft(), first_seed=0, simulation=Simulation, **params):
    """Boarding times T of `runs` independent runs with seeds first_seed, first_seed + 1, ...

    `simulation` can be a subclass of Simulation (e.g. with seat interference);
    `params` go to its constructor (stow_time=..., seat_time=...).
    """
    if runs < 1:
        raise ValueError("runs must be at least 1")
    return np.array([simulation(strategy, aircraft, seed=first_seed + k, **params).run()
                     for k in range(runs)])
