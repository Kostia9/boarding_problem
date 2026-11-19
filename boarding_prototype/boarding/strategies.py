"""Boarding strategies: each one turns the passenger list into an entry order.

To add a strategy, subclass `BoardingStrategy`, implement `order`, and (optionally)
register it in `STRATEGIES` so the app lists it.
"""

from abc import ABC, abstractmethod

import numpy as np

from .model import Passenger


class BoardingStrategy(ABC):
    name: str = "Abstract"
    uses_randomness: bool = False   # True if `order` draws from the RNG

    @abstractmethod
    def order(self, passengers: list[Passenger], rng: np.random.Generator) -> list[Passenger]:
        """Return all passengers, each exactly once, in the order they enter the aircraft."""

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"


class FrontToBack(BoardingStrategy):
    """Row 1 first, then 2, ..., n. Seats A..F within a row."""
    name = "Front-to-back"

    def order(self, passengers, rng):
        return sorted(passengers, key=lambda p: (p.target_row, p.target_seat))


class BackToFront(BoardingStrategy):
    """Row n first, then n-1, ..., 1. Seats A..F within a row."""
    name = "Back-to-front"

    def order(self, passengers, rng):
        return sorted(passengers, key=lambda p: (-p.target_row, p.target_seat))


class RandomOrder(BoardingStrategy):
    """A uniformly random permutation, drawn from the simulation's seeded RNG."""
    name = "Random"
    uses_randomness = True

    def order(self, passengers, rng):
        shuffled = list(passengers)
        rng.shuffle(shuffled)
        return shuffled


class RowCycling(BoardingStrategy):
    """Waves of one passenger per row, back to front: rows n, n-1, ..., 1, n, n-1, ...

    Wave k takes seat k of every row (A first). Each wave reaches all rows at the
    same moment and stows in parallel.
    """
    name = "Row-cycling"

    def order(self, passengers, rng):
        return sorted(passengers, key=lambda p: (p.target_seat, -p.target_row))


class OutsideIn(BoardingStrategy):
    """Board seats farthest from the aisle first, back to front within each group."""
    name = "Outside-in"

    def order(self, passengers, rng):
        return sorted(passengers, key=lambda p: (-p.aisle_depth, -p.target_row))


STRATEGIES: dict[str, type[BoardingStrategy]] = {
    cls.name: cls for cls in (FrontToBack, BackToFront, RandomOrder, RowCycling, OutsideIn)
}
