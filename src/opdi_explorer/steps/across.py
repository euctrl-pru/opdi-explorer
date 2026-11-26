"""Step 5 -- across flights: questions one day of events can answer."""

import streamlit as st

from opdi_explorer import charts, style, ui

_HOLD = style.GROUP_COLOUR["Holding and point merge"]
_RUNWAY = style.GROUP_COLOUR["Runway"]
_GROUND = style.GROUP_COLOUR["Ground"]
_VERTICAL = style.GROUP_COLOUR["Vertical profile"]
_AIRSPACE = style.GROUP_COLOUR["Rings and airspace"]


def render() -> None:
    day = ui.header(
        "across",
        "One flight is a story; a day of them is a measurement. Each question "
        "below is answered from the events of this one day, and the query "
        "under each chart is all it takes.")

    ui.question("Where do aircraft hold before landing, and when?")
    by_airport = ui.ask("holdings_by_destination", day)
    if by_airport.frame.empty:
        st.info("No holding pattern was found on this day.")
    else:
        top = by_airport.frame.iloc[0]
        total = int(by_airport.frame["holdings"].sum())
        places = len(by_airport.frame)
        st.markdown(
            f"**{total:,} holding{'' if total == 1 else 's'} before landing** "
            f"at the {places} destination{'' if places == 1 else 's'} with "
            f"the most. **{top['airport']}** leads with "
            f"{int(top['holdings'])}, {top['minutes']:.0f} minutes in all. "
            "Counted where `info.context` is `arrival`: the hold ended within "
            "60 minutes and 150 NM of the landing.")
        grid = ui.ask("holdings_by_destination_hour", day)
        ui.chart(charts.heat(grid.frame, "hour", "airport", "minutes",
                             "minutes"), grid, "hold_heat",
                 "Each row is a destination, each column an hour (UTC); a "
                 "darker cell is more minutes spent holding by flights bound "
                 "for it.")

    ui.question("Which airports see the most go-arounds?")
    ga = ui.ask("go_arounds_by_airport", day)
    ui.chart(charts.ranked_bars(ga.frame, "airport", "go_arounds",
                                "go-arounds", colour=_RUNWAY), ga, "ga_rank",
             "Training aerodromes rank high: a practised missed approach is a "
             "go-around too.")

    ui.question("How long is the taxi-out, by airport?")
    taxi = ui.ask("taxi_out_by_airport", day)
    ui.chart(charts.ranked_bars(taxi.frame, "airport", "median_min",
                                "minutes (median)", colour=_GROUND, n=25,
                                fmt=".1f"), taxi, "taxi_rank",
             "From off-block to take-off. Only airports with at least five "
             "flights whose off-block was found, which needs reception on the "
             "apron.")

    ui.question(
        "How long do aircraft fly along a point-merge leg?",
        "In a point merge, aircraft fly along an arc until they are sent to "
        "the merge point. The longer the distance along the arc, the longer "
        "the aircraft was held there.")
    pms = ui.ask("pms_leg_vs_direct", day)
    if pms.frame.empty:
        st.info("No point-merge leg was flown on this day.")
    else:
        ui.chart(charts.scatter_xy(
            pms.frame, "leg_nm", "leg_s", "Distance flown along the leg (NM)",
            "Time on the leg (s)", by="airport", hover="merge_point"), pms,
            "pms_scatter",
            f"{len(pms.frame):,} legs flown. Each dot is one, coloured by the "
            "airport the system serves; beyond the five with the most legs, "
            "the rest are drawn together as Other.")

    ui.question("How is a runway used through the day?")
    airports = ui.ask("runway_airports", day).frame
    if airports.empty:
        st.info("No landing with a runway was found on this day.")
    else:
        airport = st.selectbox("Airport", list(airports["airport"]),
                               key="across_runway_airport")
        use = ui.ask("runway_use", day, airport)
        ui.chart(charts.runway_use(use.frame), use, "across_runway",
                 "Stacked by runway. A change of colour from one hour to the "
                 "next is a change of runway direction.")

    ui.question(
        "How much of the descent is flown level?",
        "A level-off in the descent is level flight below the cruise: the "
        "aircraft burns more than in a continuous descent. This is minutes "
        "of it per arrival, at the airports with the most arrivals.")
    level = ui.ask("level_share_in_descent", day)
    ui.chart(charts.ranked_bars(level.frame, "airport",
                                "level_min_per_arrival",
                                "minutes level per arrival", colour=_VERTICAL,
                                n=25, fmt=".1f"), level, "level_rank")

    ui.question("Which airspace boundaries are the busiest?")
    fir = ui.ask("fir_boundaries", day)
    ui.chart(charts.ranked_bars(
        fir.frame.assign(boundary=fir.frame["fir_from"] + " → "
                         + fir.frame["fir_to"]) if not fir.frame.empty
        else fir.frame, "boundary", "crossings", "crossings",
        colour=_AIRSPACE), fir, "fir_rank",
        "Crossings from one flight information region into the next, side "
        "by side (not a climb from a lower region into an upper one).")

    st.divider()
    st.markdown(
        "**That is the tour.** Everything above came from two files per "
        "day. The queries run as they are in DuckDB on the downloaded files; "
        "swap the date in the file name for another day.")
    ui.back_next("across")
