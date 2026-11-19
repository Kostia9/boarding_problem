"""Passenger states, passengers and the aircraft layout."""

from dataclasses import dataclass
from enum import Enum


class State(Enum):
    WAITING = "WAITING"  # outside the aircraft, in the boarding queue
    WALKING = "WALKING"  # in the aisle, moved during the last step
    BLOCKED = "BLOCKED"  # in the aisle, could not move during the last step
    STOWING = "STOWING"  # at own row, blocking the aisle (luggage + sitting down)
    SEATED = "SEATED"    # in own seat, out of the aisle


@dataclass
class Passenger:
    id: int
    target_row: int                # 1..n_rows
    target_seat: str               # e.g. "A".."F"
    aisle_distance: int            # 1 = aisle seat, 2 = middle, 3 = window
    current_position: int = 0      # 0 = outside, k = aisle cell of row k
    state: State = State.WAITING
    remaining_time: int = 0        # seconds left of stowing + sitting down

    @property
    def seat_label(self) -> str:
        return f"{self.target_row}{self.target_seat}"


@dataclass(frozen=True)
class Aircraft:
    """Single-aisle cabin. The aisle is in the middle of `seats` ("ABC | DEF")."""
    n_rows: int = 10
    seats: str = "ABCDEF"

    @property
    def n_passengers(self) -> int:
        return self.n_rows * len(self.seats)

    def seat_offset(self, seat: str) -> int:
        """Signed distance from the aisle: A, B, C -> 3, 2, 1 and D, E, F -> -1, -2, -3."""
        i, half = self.seats.index(seat), len(self.seats) // 2
        return half - i if i < half else half - i - 1

    def make_passengers(self) -> list[Passenger]:
        """One passenger per seat, row by row (1A, 1B, ..., 2A, ...)."""
        passengers = []
        for row in range(1, self.n_rows + 1):
            for seat in self.seats:
                passengers.append(Passenger(id=len(passengers), target_row=row, target_seat=seat,
                                            aisle_distance=abs(self.seat_offset(seat))))
        return passengers
