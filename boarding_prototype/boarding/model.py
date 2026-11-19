"""Static description of the problem: passenger states, passengers, aircraft layout."""

from dataclasses import dataclass
from enum import Enum


class State(Enum):
    WAITING = "WAITING"  # outside the aircraft, in the boarding queue
    WALKING = "WALKING"  # in the aisle, moved during the last step
    BLOCKED = "BLOCKED"  # in the aisle, could not move during the last step
    STOWING = "STOWING"  # at own row, occupying the aisle (luggage + sitting down)
    SEATED = "SEATED"    # in own seat, out of the aisle


IN_AISLE = (State.WALKING, State.BLOCKED, State.STOWING)


@dataclass
class Passenger:
    id: int
    target_row: int                 # 1..n_rows
    target_seat: str                # e.g. "A".."F"
    current_position: int = 0       # 0 = outside; k = aisle cell k (= row k)
    state: State = State.WAITING
    remaining_time: int = 0         # seconds left of the stow + sit process
    aisle_depth: int = 0            # number of seats between this seat and the aisle

    @property
    def seat_label(self) -> str:
        return f"{self.target_row}{self.target_seat}"

    @property
    def in_aisle(self) -> bool:
        return self.state in IN_AISLE


@dataclass(frozen=True)
class Aircraft:
    """Single-aisle cabin: `n_rows` rows, seats listed left to right across the aisle.

    The aisle sits in the middle of `seats` ("ABC | DEF"). One aisle cell per row.
    """
    n_rows: int = 10
    seats: str = "ABCDEF"

    @property
    def n_passengers(self) -> int:
        return self.n_rows * len(self.seats)

    def make_passengers(self) -> list[Passenger]:
        """One passenger per seat. id 0 = 1A, 1 = 1B, ..., ids are row-major."""
        return [
            Passenger(id=len(self.seats) * (row - 1) + i, target_row=row, target_seat=seat,
                      aisle_depth=len(self.seats_between_aisle_and(seat)))
            for row in range(1, self.n_rows + 1)
            for i, seat in enumerate(self.seats)
        ]

    def seat_offset(self, seat: str) -> int:
        """Signed distance from the aisle: +1, +2, ... on the first side, -1, -2, ... on the second."""
        i, half = self.seats.index(seat), len(self.seats) // 2
        return half - i if i < half else half - i - 1

    def seats_between_aisle_and(self, seat: str) -> list[str]:
        """Seats a passenger must pass to reach `seat` from the aisle (aisle side first)."""
        i, half = self.seats.index(seat), len(self.seats) // 2
        return list(self.seats[i + 1:half][::-1]) if i < half else list(self.seats[half:i])
