"""Generate the strategy comparison and parameter sweeps in plots/."""
from functools import cache
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

from boarding import Aircraft, STRATEGIES, monte_carlo

OUTPUT = Path(__file__).resolve().parent / "plots"
BASE = dict(rows=10, seats=6, occupancy=1.0, noncompliance=0.0, stow_time=5, block_probability=0)
SWEEPS = {
    "rows": ("Cabin rows", [5, 10, 20, 30, 40]),
    "seats": ("Seats per row", [2, 4, 6, 8]),
    "occupancy": ("Occupied seats", [0.1, 0.25, 0.5, 0.75, 1]),
    "noncompliance": ("Passengers ignoring the strategy", [0, 0.25, 0.5, 0.75, 1]),
    "block_probability": ("Chance of blocking the row behind", [0, 0.25, 0.5, 0.75, 1]),
    "stow_time": ("Mean luggage-stowing time (seconds)", [1, 3, 5, 10, 15]),
}


@cache
def simulate(rows, seats, occupancy, noncompliance, stow_time, block_probability):
    aircraft = Aircraft(rows, "ABCDEFGH"[:seats])
    return {name: monte_carlo(strategy, 100, aircraft=aircraft, load_factor=occupancy,
                              noncompliance=noncompliance, stow_time=stow_time, block_probability=block_probability)
            for name, strategy in STRATEGIES.items()}


def save(fig, filename, caption):
    fig.text(0.02, 0.025, caption, fontsize=9, color="#414955")
    fig.tight_layout(rect=(0, 0.10, 1, 1))
    fig.savefig(OUTPUT / filename, dpi=160)
    plt.close(fig)


def main():
    OUTPUT.mkdir(exist_ok=True)
    caption = ("100 runs per strategy (seeds 0–99). Baseline: 10 rows × 6 seats, full occupancy, "
               "full compliance,\n5-second mean geometric luggage time and 2 seconds to sit.")
    times = simulate(**BASE)
    names = sorted(times, key=lambda name: times[name].mean())
    means = [times[name].mean() for name in names]
    errors = [[m - times[n].min() for n, m in zip(names, means)],
              [times[n].max() - m for n, m in zip(names, means)]]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(names, means, xerr=errors, capsize=3, color="#377da0")
    ax.invert_yaxis()
    ax.set(title="Boarding strategies in the baseline cabin",
           xlabel="Mean boarding time (seconds), with observed minimum and maximum")
    save(fig, "strategies.png", caption)

    for key, (label, values) in SWEEPS.items():
        results = [simulate(**(BASE | {key: value})) for value in values]
        fig, ax = plt.subplots(figsize=(9, 5))
        for name, marker in zip(STRATEGIES, ("o", "s", "^", "D", "v", "P")):
            ax.plot(values, [result[name].mean() for result in results], marker=marker, label=name)
        ax.set(title=f"Boarding time by {label.lower()}", xlabel=label,
               ylabel="Mean boarding time (seconds)", xticks=values, ylim=(0, None))
        if key in ("occupancy", "noncompliance", "block_probability"):
            ax.xaxis.set_major_formatter(PercentFormatter(1))
        ax.grid(axis="y", alpha=0.25)
        ax.legend(loc="center left", bbox_to_anchor=(1, 0.5), frameon=False)
        save(fig, f"{key}.png", caption)

        if key == "block_probability":
            differences = [r["Row-cycling"] - r["Steffen"] for r in results]
            fig, ax = plt.subplots(figsize=(9, 5))
            ax.errorbar(values, [d.mean() for d in differences],
                        yerr=[1.96 * d.std(ddof=1) / len(d)**0.5 for d in differences],
                        marker="o", capsize=4)
            ax.axhline(0, color="gray", linestyle="--")
            ax.set(title="Row-cycling versus Steffen under aisle blocking",
                   xlabel=label, ylabel="Row-cycling minus Steffen (seconds)", xticks=values)
            ax.xaxis.set_major_formatter(PercentFormatter(1))
            save(fig, "row_cycling_vs_steffen.png",
                 caption + "\nNegative values favor Row-cycling. Whiskers show approximate 95% CIs for paired mean differences.")


if __name__ == "__main__":
    main()
