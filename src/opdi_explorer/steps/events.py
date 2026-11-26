"""Step 3 -- flight events: pick one, and have it explained."""

import json

import pandas as pd
import streamlit as st

from opdi_explorer import catalogue, charts, style, ui

#: Event columns every row has, whatever its type.
_COMMON = [
    ("event_id", "Identifier of the event."),
    ("flight_id", "The flight it belongs to: the key to the flight list."),
    ("type", "What happened."),
    ("event_time", "When, in UTC."),
    ("longitude, latitude", "Where. Empty on the few types that are a time "
                            "only, such as the block times."),
    ("altitude_ft", "Altitude in feet, where the type has one."),
    ("info", "Extra details of this type, as JSON text."),
    ("distance_flown_nm", "Distance flown since the start of the track, in "
                          "nautical miles."),
    ("time_passed_s", "Seconds since the start of the track."),
    ("version", "Version of the method that found the event."),
]


def _info(row) -> dict:
    try:
        parsed = json.loads(row["info"]) if row["info"] else {}
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _airport_picker(day, type_: str, key: str, label: str):
    """An airport among those with the most events of *type_*."""
    top = ui.ask("top_airports_for", day, type_).frame
    if top.empty:
        return None
    return st.selectbox(
        label, list(top["airport"]), key=key,
        format_func=lambda a: f"{a} ({int(top.set_index('airport').loc[a, 'events']):,})")


def _family_chart(day, family: str, type_: str) -> None:
    """The one chart that belongs to the family of the chosen type."""
    if family == "Take-off and landing":
        st.markdown("**How a runway is used through the day.** Take-offs and "
                    "landings carry the runway in `info.runway`.")
        offered = ui.ask("runway_airports", day).frame
        airport = st.selectbox(
            "Airport", list(offered["airport"]), key="rwy_airport",
            format_func=lambda a: (
                f"{a} ({int(offered.set_index('airport').loc[a, 'movements']):,})")
        ) if not offered.empty else None
        if airport:
            r = ui.ask("runway_use", day, airport)
            ui.chart(charts.runway_use(r.frame), r, "family_runway",
                     "A change of colour from one hour to the next is a "
                     "change of runway direction.")
    elif family == "Other runway events":
        a, b = st.columns(2)
        with a:
            st.markdown("**Where aircraft go around most.**")
            g = ui.ask("go_arounds_by_airport", day)
            ui.chart(charts.ranked_bars(g.frame, "airport", "go_arounds",
                                        "go-arounds", n=15), g, "family_ga")
        with b:
            st.markdown("**How long aircraft wait on the runway** between "
                        "lining up and starting to roll.")
            w = ui.ask("lineup_to_roll", day)
            ui.chart(charts.binned_bars(
                w.frame[w.frame["seconds"] <= 300], "seconds", "flights",
                "Seconds from line-up to take-off roll", "Flights"), w,
                "family_lineup")
    elif family == "Block times":
        st.markdown("**Taxi-out time by airport**: from off-block to "
                    "take-off, which `AOBT` carries in `info.take_off`.")
        t = ui.ask("taxi_out_by_airport", day)
        ui.chart(charts.ranked_bars(t.frame, "airport", "median_min",
                                    "minutes (median)", n=25, fmt=".1f"),
                 t, "family_taxi",
                 "Airports with at least five flights whose off-block was "
                 "found. Off-block needs reception at the stand, so the "
                 "airports here are the well-covered ones.")
    elif family == "Airport surface":
        st.markdown("**Time spent on each kind of area**, from "
                    "`info.opdi_time_in_use_s` on the exit events.")
        s = ui.ask("surface_time_by_kind", day)
        ui.chart(charts.quartile_boxes(s.frame, "kind", "seconds"), s,
                 "family_surface")
    elif family == "Vertical profile":
        a, b = st.columns(2)
        with a:
            st.markdown("**How high flights climb**: altitude of the top of "
                        "climb.")
            t = ui.ask("toc_altitude", day)
            ui.chart(charts.binned_bars(t.frame, "altitude_ft", "flights",
                                        "Altitude (ft)", "Flights",
                                        horizontal=True), t, "family_toc")
        with b:
            st.markdown("**Where level-offs happen**, in the climb and in the "
                        "descent.")
            lo = ui.ask("level_off_by_level", day)
            levels = sorted(lo.frame["level_ft"].dropna().unique())
            ui.chart(charts.grouped_bars(
                lo.frame.assign(level=lo.frame["level_ft"].map(
                    lambda v: f"{v / 1000:.0f}k")),
                "level", "phase", "level_offs", "level-offs",
                order=[f"{v / 1000:.0f}k" for v in levels]), lo,
                "family_leveloff", "Level in thousands of feet, low to high.")
    elif family == "Distance rings":
        st.markdown("**From which direction arrivals come**: the bearing of "
                    "the inbound crossing of the 40 NM circle.")
        airport = _airport_picker(day, "xing-40nm", "ring_airport", "Airport")
        if airport:
            b = ui.ask("arrival_bearings", day, airport)
            ui.chart(charts.bearing_rose(b.frame), b, "family_rose",
                     "The longer the bar, the more arrivals crossed the "
                     "circle in that direction from the airport.")
    elif family == "Holding":
        a, b = st.columns(2)
        h = ui.ask("holding_stats", day)
        with a:
            st.markdown("**How long, and how many loops.** Each dot is one "
                        "holding.")
            ui.chart(charts.scatter_xy(
                h.frame.assign(minutes=h.frame["duration_s"] / 60),
                "circuits", "minutes", "Circuits", "Minutes", by="context",
                hover="airport"), h, "family_hold",
                "`context` says whether the hold was before landing "
                "(arrival), far from it (en-route), or neither (other, for "
                "example a local flight).")
        with b:
            st.markdown("**Where flights hold before landing.**")
            d = ui.ask("holdings_by_destination", day)
            ui.chart(charts.ranked_bars(d.frame, "airport", "holdings",
                                        "holdings", n=15,
                                        colour=style.GROUP_COLOUR[
                                            "Holding and point merge"]),
                     d, "family_hold_airports")
    elif family == "Point merge":
        st.markdown("**How far aircraft fly along the leg** before being sent "
                    "to the merge point, and how far the merge point then is.")
        p = ui.ask("pms_leg_vs_direct", day)
        ui.chart(charts.scatter_xy(
            p.frame, "leg_nm", "direct_nm", "Distance flown along the leg (NM)",
            "Distance left to the merge point (NM)", by="airport",
            hover="merge_point"), p, "family_pms",
            "A long way along the leg means the aircraft was kept waiting "
            "there; a short one, that it was turned in almost at once. "
            "Coloured by the airport the system serves; beyond the five with "
            "the most legs, the rest are drawn together as Other.")
    elif family == "Airspace":
        st.markdown("**The airspace boundaries crossed most.**")
        f = ui.ask("fir_boundaries", day)
        ui.chart(charts.ranked_bars(
            f.frame.assign(boundary=f.frame["fir_from"] + " → "
                           + f.frame["fir_to"]),
            "boundary", "crossings", "crossings", n=20,
            colour=style.GROUP_COLOUR["Rings and airspace"]), f, "family_fir")
    elif family == "Track limits":
        st.markdown("**Where tracks begin and end.** Away from airports, "
                    "this is the edge of what the receivers can hear.")
        t = ui.ask("track_limits", day)
        ui.chart(charts.point_map(t.frame, by="which"), t, "family_limits",
                 f"A sample of {len(t.frame):,} positions.")


def _viewer(day, type_: str) -> None:
    """A sample of the events table, with the measurement columns."""
    st.header("Look at the table")
    st.markdown(
        "Every event row carries **measurements** beside its time and place: "
        "`distance_flown_nm` and `time_passed_s` say how far and how long the "
        "flight had flown when the event happened. Holdings and point-merge "
        "legs carry their own (`holding_*`, `pms_*`), on the event that ends "
        "them.")
    which = st.radio(
        "Rows to sample",
        ["Any event", f"Only `{type_}`",
         "Only rows with a holding or point-merge measurement"],
        horizontal=True, key="viewer_rows")
    if which.startswith("Only `"):
        sample = ui.ask("sample_events", day, type_=type_)
    elif which.startswith("Only rows"):
        sample = ui.ask("sample_events", day, measured=True)
    else:
        sample = ui.ask("sample_events", day)
    st.caption(f"A random sample of {len(sample.frame):,} rows: the event's "
               "own columns and its measurements. The columns of the flight, "
               "repeated on every row in the file, are left out here.")
    st.dataframe(sample.frame, hide_index=True, width="stretch", height=330)
    ui.query(sample, "Show the query for this sample")


def render() -> None:
    day = ui.header(
        "events",
        "An event is one thing that happened to a flight, with its time and, "
        "nearly always, its place. There are ten families of them. Pick a "
        "family, then an event type, and this page explains it and shows "
        "where and when it happens.")

    with st.expander("The columns every event row has"):
        ui.table(_COMMON, ["column", "what it holds"], ["k", ""])
        st.markdown("Each row then repeats the columns of its flight "
                    "(call sign, airports, aircraft and so on), so events can "
                    "be filtered by flight properties without a join.")

    counts = ui.ask("type_counts", day)
    c = counts.frame.set_index("type")
    present = list(c.index)
    undescribed = [t for t in present if not catalogue.event(t).described]
    families = list(catalogue.FAMILIES) + (
        [catalogue.UNDESCRIBED] if undescribed else [])

    a, b = st.columns(2)
    family = a.selectbox("Family", families, key="event_family")
    if family == catalogue.UNDESCRIBED:
        options = undescribed
    else:
        options = [t for t in catalogue.types_in(family) if t in present]
    if family in catalogue.FAMILY_NOTES:
        st.markdown(ui.tag(family, style.colour_of_family(family))
                    + catalogue.FAMILY_NOTES[family], unsafe_allow_html=True)
    if not options:
        st.info(f"No event of this family was found on {day:%d %B %Y}.")
        ui.back_next("events")
        return
    type_ = b.selectbox(
        "Event type", options, key=f"event_type_{family}",
        format_func=lambda t: f"{t} ({int(c.loc[t, 'events']):,})")
    spec = catalogue.event(type_)

    st.header(f"`{type_}`")
    st.markdown(f"<p class='ex-lead'>{spec.description}</p>",
                unsafe_allow_html=True)
    flights_total = int(ui.ask("day_numbers", day).frame.iloc[0]["flights"])
    ui.numbers({
        "events on this day": ui.number(c.loc[type_, "events"]),
        "flights that have it": ui.number(c.loc[type_, "flights"]),
        "of all flights": f"{100 * c.loc[type_, 'flights'] / max(flights_total, 1):.1f}%",
    })
    ui.query(counts, "Show the query for the counts")

    sample = ui.ask("sample_row", day, type_)
    row = sample.frame.iloc[0] if not sample.frame.empty else None
    details = _info(row) if row is not None else {}

    st.subheader("What its `info` holds")
    fields = dict(spec.fields)
    extra = [k for k in details if k not in fields]
    if not fields and not details:
        st.markdown("Nothing: this event type has no extra details, and its "
                    "`info` is an empty text.")
    else:
        names = [k for k in fields if k in details] + [
            k for k in fields if k not in details] + extra
        ui.table(
            [(k, fields.get(k, "(not in the data dictionary yet)"),
              json.dumps(details[k]) if k in details else "(absent)")
             for k in names],
            ["field", "meaning", "in the example row"], ["k", "", "v"])
        st.caption("A field without a value is left out of `info`, so not "
                   "every row has every field.")

    if row is not None:
        with st.expander("A real row, whole"):
            st.dataframe(
                pd.DataFrame({"column": row.index,
                              "value": [str(v) for v in row.values]}),
                hide_index=True, width="stretch", height=420)
            ui.query(sample)

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Where it happens")
        where = ui.ask("where", day, type_)
        ui.chart(charts.point_map(where.frame, colour=style.colour_of(type_),
                                  name=type_), where, "where",
                 f"{len(where.frame):,} positions"
                 + (" (a sample)" if len(where.frame) >= 20000 else "") + ".")
    with right:
        st.subheader("When it happens")
        when = ui.ask("by_hour", day, type_)
        ui.chart(charts.bar_by_hour(when.frame, "events", "events",
                                    colour=style.colour_of(type_),
                                    height=460), when, "when")

    if family != catalogue.UNDESCRIBED:
        st.subheader(f"What the {family.lower()} family can show")
        _family_chart(day, family, type_)

    _viewer(day, type_)
    ui.back_next("events")
