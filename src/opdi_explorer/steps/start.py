"""Step 1 -- the two tables, how they join, and the day in numbers."""

import pandas as pd
import streamlit as st

from opdi_explorer import config
from opdi_explorer import catalogue, charts, ui


def _when(value) -> str:
    return "–" if pd.isna(value) else f"{pd.Timestamp(value):%H:%M:%S}"


def render() -> None:
    day = ui.header(
        "start",
        "The Open Performance Data Initiative (OPDI) turns the aircraft "
        "position reports received by the OpenSky Network into two tables "
        "anyone can download: a <b>flight list</b> and a table of "
        "<b>flight events</b>. This tour shows what is in each, what every "
        "event means, and what you can work out from them.")

    left, right = st.columns(2)
    left.markdown(
        "<div class='ex-card'><h4>Flight list</h4>"
        "<p><b>One row is one flight.</b> Who flew, from where to where, with "
        "which aircraft, and when it left its stand, took off, landed and "
        "parked.</p></div>", unsafe_allow_html=True)
    right.markdown(
        "<div class='ex-card'><h4>Flight events</h4>"
        "<p><b>One row is one thing that happened to a flight</b>, with its "
        "time and place: a take-off, a level-off, a holding pattern, a "
        "taxiway entered. A flight has dozens.</p></div>",
        unsafe_allow_html=True)
    st.markdown(
        "The two are joined by **`flight_id`**. Every event row also repeats "
        "the columns of its flight, so many questions need the events table "
        "alone.")

    st.subheader(f"{day:%d %B %Y} in numbers")
    n = ui.ask("day_numbers", day)
    row = n.frame.iloc[0]
    ui.numbers({
        "flights": ui.number(row["flights"]),
        "events": ui.number(row["events"]),
        "airports": ui.number(row["airports"]),
        "aircraft": ui.number(row["aircraft"]),
        "kinds of event": ui.number(row["event_types"]),
    })
    ui.query(n)

    st.subheader("One flight, in both tables")
    example = ui.ask("example_flight", day)
    if example.frame.empty:
        st.info("This day has no flight followed from take-off to landing "
                "with a known operator, so there is no example to show.")
    else:
        f = example.frame.iloc[0]
        st.markdown(
            f"In the flight list, **{str(f['flt_id']).strip()}** is one row: "
            f"a {f['typecode']} of {f['icao_operator']} from "
            f"**{f['adep']}** to **{f['ades']}**, off the runway at "
            f"{_when(f['atot'])} and landed at {_when(f['aldt'])} (UTC). "
            f"Its `flight_id` is `{f['flight_id']}`.")
        ev = ui.ask("flight_events", day, f["flight_id"])
        st.markdown(
            f"In the flight events table the same `flight_id` has "
            f"**{len(ev.frame)} rows**. The first few:")
        head = ev.frame.head(6)
        ui.table(
            [(_when(e["event_time"]), e["type"],
              catalogue.event(e["type"]).description,
              "" if pd.isna(e["altitude_ft"]) else f"{e['altitude_ft']:,.0f}")
             for _, e in head.iterrows()],
            ["time (UTC)", "type", "what it means", "altitude (ft)"],
            ["k", "k", "", "k"])
        ui.query(ev, "Show the query for this flight's events")

    st.subheader("The days of this release")
    trend = ui.ask("days_trend")
    st.markdown(
        (f"**{len(trend.frame)} day{'' if len(trend.frame) == 1 else 's'}** shown, from "
         f"{config.FROM_DAY:%d %B %Y} on. " if config.FROM_DAY else
         f"The release holds **{len(trend.frame)} days**. ")
        + "Each has its own pair of files, so a day can be read without the "
          "others. Pick another day at the top right at any time.")
    ui.chart(charts.days_trend(trend.frame, "flights", "flights"), trend,
             "trend_flights")

    st.caption(
        f"Release `{config.RELEASE.rstrip('/').split('/')[-1]}`, read "
        "directly from its published files. Descriptions are the OPDI data "
        "dictionary's.")
    st.subheader("The tour")
    for col, (key, title, what) in zip(st.columns(len(ui.STEPS) - 1),
                                       ui.STEPS[1:]):
        with col.container(border=True):
            number = [k for k, _, _ in ui.STEPS].index(key) + 1
            st.markdown(f"**{number}. {title}**")
            st.caption(what)
            if key in ui.PAGES:
                st.page_link(ui.PAGES[key], label="Open →")
    ui.back_next("start")
