"""python -m boarding  ->  boarding time of every strategy."""

from . import STRATEGIES, Simulation

for name, strategy in STRATEGIES.items():
    print(f"{name:<14} T = {Simulation(strategy).run()} s")
