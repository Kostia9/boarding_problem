"""Airplane boarding simulation (the UI is in app.py).

    from boarding import Simulation, STRATEGIES
    Simulation(STRATEGIES["Back-to-front"]).run()   # -> total boarding time T in seconds
"""

from .model import Aircraft, Passenger, State
from .simulation import Simulation
from .strategies import STRATEGIES
