"""Streamlit + Plotly front end for the boarding simulation.

Run with:  streamlit run app.py
All model logic lives in the `boarding` package; this file only draws its state.
The run is simulated once and played back as a Plotly animation in the browser (no page reruns).
"""

import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from boarding import STRATEGIES, Aircraft, Simulation, State, monte_carlo

SEAT_LETTERS = "ABCDEFGH"
DEFAULTS = dict(strategy="Random", seed=0, n_rows=10, n_seats=6, load_factor=1.0,
                stow_time=5, noncompliance=0.0, block_probability=0.0, n_runs=100)
STATE_COLORS = {State.WAITING: "#7d7c74", State.WALKING: "#2a78d6", State.BLOCKED: "#eb6834",
                State.STOWING: "#1baf7a", State.SEATED: "#eda100"}
EMPTY_COLOR = "#e1e0d9"
MAX_FRAMES = 400  # longer runs show every k-th second so the figure stays small
PLAYBACK_SPEEDS = (1, 3, 5, 10, 30)  # simulated seconds per real second, one play button each


def settings(n_rows, n_seats, load_factor, stow_time, noncompliance, block_probability) -> dict:
    """Simulation keyword arguments for the chosen cabin and stow time."""
    return dict(aircraft=Aircraft(n_rows, SEAT_LETTERS[:n_seats]), load_factor=load_factor,
                stow_time=stow_time, noncompliance=noncompliance, block_probability=block_probability)


@st.cache_data
def boarding_times(n_runs: int, **config) -> dict[str, list[float]]:
    """Mean, min and max of T over seeds 0..n_runs-1 for every strategy (deterministic, so cached)."""
    result = {}
    for name, strategy in STRATEGIES.items():
        times = monte_carlo(strategy, n_runs, **settings(**config))
        result[name] = [round(times.mean(), 1), times.min(), times.max()]
    return result


@st.cache_data
def record_run(strategy_name: str, seed: int, *args):
    """Run one simulation to the end. frames[t] = (state, aisle cell) of every passenger at time t."""
    sim = Simulation(STRATEGIES[strategy_name], seed=seed, **settings(*args))
    frames = [[(p.state, p.current_position) for p in sim.passengers]]
    while not sim.finished:
        sim.step()
        frames.append([(p.state, p.current_position) for p in sim.passengers])
    return sim.aircraft, sim.passengers, frames


def draw_cabin(aircraft: Aircraft, passengers: list, frames: list) -> dict:
    """Top-down view (aisle at y = 0, seats at their signed offset), animated over `frames`.

    The browser plays the frames itself, so the page never reloads during playback. All passengers
    are one trace (waiting ones hidden); each frame replaces its positions and colors. No eased
    transitions between frames: Plotly then moves the markers but leaves their labels behind.
    Frames are plain dicts: building hundreds of validated go.Frame objects takes seconds.
    """
    seat_y = aircraft.seat_offset
    rows = range(1, aircraft.n_rows + 1)
    size = min(30, 900 // aircraft.n_rows)
    font = max(6, size // 3)
    n_total = len(passengers)
    T = len(frames) - 1
    step = math.ceil(T / MAX_FRAMES)                  # simulated seconds per animation frame
    times = list(range(0, T, step)) + [T]

    def counts(t):
        return {s: sum(state is s for state, _ in frames[t]) for s in State}

    def door(t):
        n = counts(t)[State.WAITING]
        return dict(x=[0] if n else [None], y=[0] if n else [None], text=[n] if n else [])

    def people(t):
        x, y, color = [], [], []
        for p, (state, cell) in zip(passengers, frames[t]):
            seated = state is State.SEATED
            x.append(None if state is State.WAITING else p.target_row if seated else cell)
            y.append(None if state is State.WAITING else seat_y(p.target_seat) if seated else 0)
            color.append(STATE_COLORS[state])
        return dict(x=x, y=y, marker=dict(color=color))

    def status(t):
        c = counts(t)
        return (f"t = {t} s of T = {T} s  ·  seated {c[State.SEATED]} / {n_total}  ·  "
                f"waiting {c[State.WAITING]}  ·  blocked {c[State.BLOCKED]}")

    fig = go.Figure()
    # Static background: every seat and every aisle cell as an empty square, empty seats crossed.
    fig.add_trace(go.Scatter(
        x=[r for r in rows for _ in aircraft.seats],
        y=[seat_y(s) for _ in rows for s in aircraft.seats],
        mode="markers", hoverinfo="skip", showlegend=False,
        marker=dict(symbol="square", size=size, color=EMPTY_COLOR),
    ))
    fig.add_trace(go.Scatter(
        x=list(rows), y=[0] * aircraft.n_rows, mode="markers", hoverinfo="skip", showlegend=False,
        marker=dict(symbol="square-open", size=size, color="#c3c2b7"),
    ))
    taken = {p.seat_label for p in passengers}
    empty = [(r, s) for r in rows for s in aircraft.seats if f"{r}{s}" not in taken]
    fig.add_trace(go.Scatter(
        x=[r for r, _ in empty] or [None], y=[seat_y(s) for _, s in empty] or [None],
        mode="markers", name="Empty seat", hoverinfo="skip", showlegend=bool(empty),
        marker=dict(symbol="x", size=round(size * 0.6), color="#222222"),
    ))
    # Animated traces (index 3 and 4): waiting count at the door, and every passenger.
    fig.add_trace(go.Scatter(
        **door(0), mode="markers+text", name="Waiting (at door)",
        hovertemplate="%{text} passengers waiting outside<extra></extra>",
        marker=dict(size=size + 4, color=STATE_COLORS[State.WAITING]),
        textfont=dict(size=font, color="#ffffff"),
    ))
    first = people(0)
    fig.add_trace(go.Scatter(
        x=first["x"], y=first["y"], marker=dict(size=size - 2, color=first["marker"]["color"]),
        mode="markers+text", showlegend=False, text=[p.seat_label for p in passengers],
        customdata=[p.stow_time for p in passengers],
        hovertemplate="Passenger %{text}, stow time %{customdata} s<extra></extra>",
        textfont=dict(size=font, color="#0b0b0b"),
    ))
    # Legend-only entries for the passenger states (Plotly hides traces without points).
    for state in (State.WALKING, State.BLOCKED, State.STOWING, State.SEATED):
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name=state.value.capitalize(),
                                 marker=dict(size=10, color=STATE_COLORS[state])))

    def play(speed):  # "immediate" interrupts the running playback, fromcurrent keeps the position
        return dict(mode="immediate", fromcurrent=True, transition=dict(duration=0),
                    frame=dict(duration=1000 * step / speed, redraw=True))
    jump = dict(mode="immediate", frame=dict(duration=0, redraw=True), transition=dict(duration=0))
    half = max(map(abs, map(seat_y, aircraft.seats)))
    fig.update_layout(
        title=dict(text=status(0), x=0, font=dict(size=14)),
        height=max(330, 55 * (2 * half + 1) + 140), margin=dict(l=10, r=10, t=70, b=10),
        legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, itemsizing="constant",
                    itemclick=False, itemdoubleclick=False),
        xaxis=dict(tickvals=[0, *rows], ticktext=["door", *rows],
                   range=[-0.7, aircraft.n_rows + 0.7], showgrid=False, zeroline=False, fixedrange=True),
        yaxis=dict(tickvals=[seat_y(s) for s in aircraft.seats] + [0],
                   ticktext=list(aircraft.seats) + ["aisle"],
                   range=[-half - 0.7, half + 0.7], showgrid=False, zeroline=False, fixedrange=True),
        updatemenus=[dict(type="buttons", direction="left", x=0, y=0, xanchor="left", yanchor="top",
                          pad=dict(t=30), showactive=True, active=-1, buttons=[
                              *[dict(label=f"▶ {s}×", method="animate", args=[None, play(s)])
                                for s in PLAYBACK_SPEEDS],
                              dict(label="❚❚", method="animate", args=[[None], jump]),
                          ])],
        sliders=[dict(x=0.3, len=0.7, y=0, yanchor="top", pad=dict(t=20),
                      currentvalue=dict(prefix="t = ", suffix=" s", font=dict(size=12)),
                      ticklen=0, minorticklen=0, font=dict(color="rgba(0,0,0,0)"),
                      steps=[dict(method="animate", label=str(t), args=[[str(t)], jump]) for t in times])],
    )
    fig = fig.to_dict()
    fig["frames"] = [dict(name=str(t), data=[door(t), people(t)], traces=[3, 4],
                          layout=dict(title=dict(text=status(t)))) for t in times]
    return fig


st.set_page_config(page_title="Airplane boarding", layout="wide")
st.title("Airplane boarding")

for key, value in DEFAULTS.items():
    st.session_state.setdefault(key, value)

with st.sidebar:
    st.header("Cabin")
    st.slider("Rows", 5, 40, key="n_rows")
    st.select_slider("Seats per row", [2, 4, 6, 8], key="n_seats")
    st.slider("Load factor (share of seats taken)", 0.1, 1.0, step=0.05, key="load_factor")
    st.header("Stow time")
    st.slider("Mean geometric stow time (s)", 1, 15, key="stow_time",
              help="Each second, a passenger finishes stowing with probability 1 / mean.")
    st.slider("Chance of blocking the row behind while stowing", 0.0, 1.0, step=0.05,
              key="block_probability", help="0 = never, 1 = every passenger.")
    st.header("Strategy comparison")
    st.slider("Passengers ignoring the strategy", 0.0, 1.0, step=0.05, key="noncompliance",
              help="Each passenger independently joins a random queue position with this probability.")
    st.slider("Monte Carlo runs", 10, 500, step=10, key="n_runs")

ss = st.session_state
st.caption(f"{ss.n_rows} rows x {ss.n_seats} seats, one aisle, 1 step = 1 second. "
           "Labels show each passenger's assigned seat; seat time 2 s. "
           "Play with the ▶ buttons under the cabin (N× = N simulated seconds per real second), "
           "or drag the time slider.")

STRATEGY_NAMES = ["Random"] + [name for name in STRATEGIES if name != "Random"]
s1, s2 = st.columns([4, 1])
s1.selectbox("Boarding strategy", STRATEGY_NAMES, key="strategy")
s2.number_input("Seed", min_value=0, step=1, key="seed",
                help="Empty seats, stow times and the random order are drawn from a generator "
                     "with this fixed seed, so every run is reproducible.")

run = record_run(ss.strategy, int(ss.seed), ss.n_rows, ss.n_seats, ss.load_factor, ss.stow_time,
                 ss.noncompliance, ss.block_probability)
st.plotly_chart(draw_cabin(*run), width="stretch", key="cabin",
                config={"displayModeBar": False})

st.subheader("Strategy comparison")
config = {key: ss[key] for key in ("n_rows", "n_seats", "load_factor", "stow_time", "noncompliance", "block_probability")}
times = boarding_times(ss.n_runs, **config)
table = pd.DataFrame([[name, *t] for name, t in times.items()],
                     columns=["Strategy", "Mean T (s)", "Min T (s)", "Max T (s)"])
table = table.sort_values("Mean T (s)").reset_index(drop=True)  # st.table hides only a plain 0..n index
highlight = "font-weight: bold; background-color: rgba(42, 120, 214, 0.15)"
st.table(table.style.hide(axis="index")
         .format({"Mean T (s)": "{:.1f}", "Min T (s)": "{:.0f}", "Max T (s)": "{:.0f}"})
         .apply(lambda row: [highlight if row["Strategy"] == ss.strategy else ""] * len(row), axis=1))
st.caption(f"Sorted by mean, selected strategy highlighted. Over {ss.n_runs} runs with seeds "
           f"0..{ss.n_runs - 1}. For a given seed every strategy boards the same passengers "
           "(same empty seats and stow times).")
