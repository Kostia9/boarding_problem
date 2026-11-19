"""How long a passenger blocks the aisle at their row.

This is the main extension point for behavioural constraints: a subclass can read
the current state of `sim` (e.g. seat interference: more time if row-mates already
sit nearer the aisle). The fixed model below does not.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .model import Passenger

if TYPE_CHECKING:
    from .simulation import Simulation


class TimingModel(ABC):
    @abstractmethod
    def stow_time(self, passenger: Passenger, sim: "Simulation") -> int:
        """Seconds to store luggage. Called once, when the passenger reaches their row."""

    @abstractmethod
    def seat_time(self, passenger: Passenger, sim: "Simulation") -> int:
        """Seconds to sit down. Called once, right after `stow_time`."""


@dataclass(frozen=True)
class FixedTiming(TimingModel):
    """Iteration-1 assumption: the same fixed times for everyone."""
    stow: int = 5
    seat: int = 2

    def stow_time(self, passenger, sim):
        return self.stow

    def seat_time(self, passenger, sim):
        return self.seat
