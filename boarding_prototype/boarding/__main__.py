"""python -m boarding [--runs N] [--rows R ...] [--seats ABCDEF] [--strategy NAME]
                   [--noncompliance F ...] [--delay NAME [--phases K] [--sigma S]] [--csv FILE]

Without options: one run (seed 0) of every strategy, as before.
With --runs N: mean, standard deviation, 95 % CI of the mean, min and max of T over N seeds.
Several values for --rows and/or --noncompliance run a sweep over all their combinations:

    python -m boarding --runs 300 --rows 10 20 30 40 --strategy Random
    python -m boarding --runs 300 --noncompliance 0 0.25 0.5 0.75 1 --strategy Back-to-front
"""

import argparse
import csv
import itertools

from . import DELAYS, STRATEGIES, Aircraft
from .experiments import Summary, monte_carlo

parser = argparse.ArgumentParser(prog="python -m boarding", description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="\n".join(__doc__.splitlines()[5:]))
parser.add_argument("--runs", type=int, default=1, help="number of seeds per strategy (default 1)")
parser.add_argument("--seed", type=int, default=0, help="first seed (default 0)")
parser.add_argument("--rows", type=int, nargs="+", default=[Aircraft.n_rows], metavar="R",
                    help=f"number of rows, one or more values (default {Aircraft.n_rows})")
parser.add_argument("--seats", default=Aircraft.seats, help='seat letters of a row, e.g. "ABCDEF"')
parser.add_argument("--strategy", action="append", choices=STRATEGIES, metavar="NAME",
                    help="only this strategy (repeatable); default: all")
parser.add_argument("--noncompliance", type=float, nargs="+", default=[0.0], metavar="F",
                    help="share of passengers who ignore the strategy and join the queue "
                         "at a random place (0..1), one or more values (default 0)")
parser.add_argument("--delay", choices=DELAYS, default="geometric",
                    help="distribution of the time at the row, mean = stow + sit time (default geometric)")
parser.add_argument("--phases", type=int, default=3, help="phases of the erlang delay (default 3)")
parser.add_argument("--sigma", type=float, default=0.5, help="sigma of the lognormal delay (default 0.5)")
parser.add_argument("--stow-time", type=int, default=5, help="mean seconds for luggage (default 5)")
parser.add_argument("--seat-time", type=int, default=2, help="mean seconds to sit down (default 2)")
parser.add_argument("--csv", metavar="FILE",
                    help="also write every run (strategy, rows, passengers, noncompliance, seed, T) to FILE")
args = parser.parse_args()

delay = DELAYS[args.delay](phases=args.phases, sigma=args.sigma)
names = args.strategy or list(STRATEGIES)
width = max(map(len, names))
records = []

print(f"{len(args.seats)} seats per row, {delay} delay with mean {args.stow_time + args.seat_time} s, "
      f"{args.runs} run(s) per strategy, seeds {args.seed}..{args.seed + args.runs - 1}")
for n_rows, fraction in itertools.product(args.rows, args.noncompliance):
    aircraft = Aircraft(n_rows, args.seats)
    print(f"\n{n_rows} rows ({aircraft.n_passengers} passengers), {fraction:.0%} ignore the strategy")
    if args.runs > 1:
        print(f"{'Strategy':<{width}}  {'mean':>7}  {'± 95%':>6}  {'std':>6}  {'min':>5}  {'max':>5}")
    for name in names:
        times = monte_carlo(STRATEGIES[name], args.runs, aircraft, first_seed=args.seed,
                            noncompliance=fraction, delay=delay,
                            stow_time=args.stow_time, seat_time=args.seat_time)
        records += [(name, n_rows, aircraft.n_passengers, fraction, args.seed + k, int(t))
                    for k, t in enumerate(times)]
        if args.runs == 1:
            print(f"{name:<{width}}  T = {times[0]} s")
        else:
            s = Summary.of(times)
            print(f"{name:<{width}}  {s.mean:7.1f}  {s.ci95:6.1f}  {s.std:6.1f}  {s.min:5d}  {s.max:5d}")

if args.csv:
    with open(args.csv, "w", newline="") as f:
        csv.writer(f).writerows([("strategy", "rows", "passengers", "noncompliance", "seed", "T")]
                                + records)
    print(f"\nwrote {len(records)} runs to {args.csv}")
