"""Airplane boarding simulation engine (no UI code; see app.py for the front end).

    from boarding import Simulation, BackToFront
    Simulation(BackToFront()).run()          # -> total boarding time T in seconds
"""

from .model import Aircraft, Passenger, State
from .simulation import Simulation
from .strategies import (STRATEGIES, BackToFront, BoardingStrategy, FrontToBack,
                         OutsideIn, RandomOrder, RowCycling)
from .timing import FixedTiming, TimingModel

__all__ = [
    "Aircraft", "Passenger", "State", "Simulation",
    "BoardingStrategy", "FrontToBack", "BackToFront", "RandomOrder", "RowCycling", "OutsideIn",
    "STRATEGIES",
    "TimingModel", "FixedTiming",
]
