"""python -m boarding [--runs N] [--rows R] [--seats ABCDEF] [--strategy NAME] [--csv FILE]

Without options: one run (seed 0) of every strategy, as before.
With --runs N: mean, standard deviation, 95 % CI of the mean, min and max of T over N seeds.
"""

import argparse
import csv

from . import STRATEGIES, Aircraft
from .experiments import Summary, monte_carlo

parser = argparse.ArgumentParser(prog="python -m boarding", description=__doc__.splitlines()[0])
parser.add_argument("--runs", type=int, default=1, help="number of seeds per strategy (default 1)")
parser.add_argument("--seed", type=int, default=0, help="first seed (default 0)")
parser.add_argument("--rows", type=int, default=Aircraft.n_rows)
parser.add_argument("--seats", default=Aircraft.seats, help='seat letters of a row, e.g. "ABCDEF"')
parser.add_argument("--strategy", action="append", choices=STRATEGIES, metavar="NAME",
                    help="only this strategy (repeatable); default: all")
parser.add_argument("--csv", metavar="FILE", help="also write every run (strategy, seed, T) to FILE")
args = parser.parse_args()

aircraft = Aircraft(args.rows, args.seats)
names = args.strategy or list(STRATEGIES)
width = max(map(len, names))
rows = []

print(f"{aircraft.n_rows} rows x {len(aircraft.seats)} seats, "
      f"{args.runs} run(s) per strategy, seeds {args.seed}..{args.seed + args.runs - 1}")
if args.runs > 1:
    print(f"{'Strategy':<{width}}  {'mean':>7}  {'± 95%':>6}  {'std':>6}  {'min':>5}  {'max':>5}")
for name in names:
    times = monte_carlo(STRATEGIES[name], args.runs, aircraft, first_seed=args.seed)
    rows += [(name, args.seed + k, int(t)) for k, t in enumerate(times)]
    if args.runs == 1:
        print(f"{name:<{width}}  T = {times[0]} s")
    else:
        s = Summary.of(times)
        print(f"{name:<{width}}  {s.mean:7.1f}  {s.ci95:6.1f}  {s.std:6.1f}  {s.min:5d}  {s.max:5d}")

if args.csv:
    with open(args.csv, "w", newline="") as f:
        csv.writer(f).writerows([("strategy", "seed", "T")] + rows)
    print(f"wrote {len(rows)} runs to {args.csv}")
