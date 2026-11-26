"""Step 2 -- the flight list: what a row holds, and what it answers alone."""

import pandas as pd
import streamlit as st

from opdi_explorer import catalogue, charts, data, style, ui


def _shown(value) -> str:
    """A cell of the example row, as text."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return "(empty)"
    if isinstance(value, pd.Timestamp):
        # A date is stored as a timestamp at midnight; show it as the date.
        if value == value.normalize():
            return f"{value:%Y-%m-%d}"
        return f"{value:%Y-%m-%d %H:%M:%S}"
    return str(value)


def render() -> None:
    day = ui.header(
        "flight_list",
        "One row of the flight list is one flight. A flight is usually one "
        "<i>track</i>: the position reports of one aircraft under one call "
        "sign, from the first to the last one received. The 46 columns fall "
        "into seven groups.")

    example = ui.ask("example_flight", day).frame
    row = example.iloc[0] if not example.empty else None
    if row is not None:
        st.caption(
            f"The example values are those of {str(row['flt_id']).strip()} "
            f"({row['adep']} to {row['ades']}) on {day:%d %B %Y}.")
    for tab, (group, columns) in zip(
            st.tabs(list(catalogue.COLUMN_GROUPS)),
            catalogue.COLUMN_GROUPS.items()):
        with tab:
            st.markdown(f"**{catalogue.COLUMN_GROUP_NOTES[group]}**")
            ui.table(
                [(c, m, _shown(row[c]) if row is not None and c in row.index
                  else "") for c, m in columns],
                ["column", "what it holds", "example"], ["k", "", "v"])
            with st.expander("The full description of each column"):
                for c, _ in columns:
                    st.markdown(f"**`{c}`** — {catalogue.column(c)[3]}")

    st.subheader("Look at the table")
    sample = ui.ask("sample_flight_list", day)
    st.markdown(
        f"A random sample of **{len(sample.frame):,} rows** of the day's "
        "flight list, every column. Scroll sideways; click a column name to "
        "sort.")
    st.dataframe(sample.frame, hide_index=True, width="stretch", height=330,
                 column_config={"dof": st.column_config.DateColumn(
                     "dof", format="YYYY-MM-DD")})
    ui.query(sample, "Show the query for this sample")

    st.header("What the flight list answers by itself")

    ui.question("Where do aircraft fly from and to?")
    airports = ui.ask("airports_by_departures", day)
    busiest = airports.frame.head(1)
    if not busiest.empty:
        b = busiest.iloc[0]
        st.markdown(
            f"**{len(airports.frame):,} airports** had at least one departure "
            f"or arrival. The busiest was **{b['airport']}**"
            + (f" ({b['name']})" if isinstance(b["name"], str) else "")
            + f" with {int(b['departures']):,} departures and "
              f"{int(b['arrivals']):,} arrivals.")
    if not data.has_airports():
        st.info("This release has no table of airport positions "
                "(`oa_airports`), so airports and routes cannot be put on a "
                "map. The counts below are unaffected.")
        ui.chart(charts.ranked_bars(
            airports.frame.assign(
                movements=airports.frame["departures"]
                + airports.frame["arrivals"]),
            "airport", "movements", "movements"), airports, "airports_rank")
    else:
        ui.chart(charts.airport_map(airports.frame), airports, "airports_map",
                 "Each circle is an airport; its size is the number of "
                 "departures and arrivals. Counted with `movement_dep` and "
                 "`movement_arr`, the columns made for counting.")

    ui.question("Which routes are flown most?")
    routes = ui.ask("busiest_routes", day)
    a, b = st.columns([3, 2])
    with a:
        ui.chart(charts.route_map(routes.frame), routes, "routes_map")
    with b:
        st.dataframe(routes.frame[["adep", "ades", "flights"]],
                     hide_index=True, width="stretch", height=440)

    ui.question("When are flights first seen?")
    hours = ui.ask("flights_by_hour", day)
    ui.chart(charts.bar_by_hour(hours.frame, "flights", "flights"), hours,
             "by_hour",
             "The hour is UTC, so the world's daytime moves across the chart.")

    ui.question("Which aircraft, and whose?")
    a, b = st.columns(2)
    with a:
        types = ui.ask("aircraft_types", day)
        ui.chart(charts.ranked_bars(types.frame, "typecode", "flights",
                                    "flights"), types, "types")
    with b:
        ops = ui.ask("operators", day)
        ui.chart(charts.ranked_bars(ops.frame, "operator", "flights",
                                    "flights",
                                    colour=style.GROUP_COLOUR[
                                        "Vertical profile"]),
                 ops, "operators")

    ui.question(
        "How often is each end of a flight found, and how?",
        "`adep_source` and `ades_source` say how the airport was decided: "
        "from a take-off or landing on one of its runways (`runway_event`), "
        "from where the track began or ended (`aerodrome`), or not at all "
        "(`undetermined`, as for a flight passing overhead).")
    sources = ui.ask("airport_sources", day)
    ui.chart(charts.grouped_bars(sources.frame, "source", "end", "flights",
                                 "flights"), sources, "sources")

    ui.question("How long are flights in the air, by aircraft type?")
    airborne = ui.ask("airborne_time_by_type", day)
    ui.chart(charts.quartile_boxes(airborne.frame, "typecode",
                                   "minutes from take-off to landing"),
             airborne, "airborne",
             "The box is the middle half of the flights of that type, the "
             "line in it the median, the whiskers the 10th and 90th "
             "percentile. Only flights with both a take-off and a landing.")

    ui.back_next("flight_list")
