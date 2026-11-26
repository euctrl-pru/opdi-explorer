"""Step 4 -- one flight: its track from OpenSky, with its events on it."""

import json

import pandas as pd
import streamlit as st

from opdi_explorer import config
from opdi_explorer import (
    catalogue, charts, data, style, tracks, ui,
)

#: Minutes of track shown either side of a holding, go-around or leg.
_MARGIN_MIN = 6

#: At most this many close-ups per flight, so a training flight with a dozen
#: go-arounds does not become a page of maps.
_MAX_CLOSE_UPS = 3


@st.cache_data(ttl=3600, show_spinner=False)
def _fetched(tracks_root, icao24, first_seen, last_seen):
    return tracks.thin(tracks.fetch(icao24, first_seen, last_seen))


def _track(tracks_root, icao24, first_seen, last_seen):
    """The thinned track, or the reason there is none.

    Only a track that was read is remembered. The failure is raised through
    the cache, not returned from it: a store that could not be reached for a
    moment must be tried again on the next look, not reported as gone for an
    hour.
    """
    try:
        return _fetched(tracks_root, icao24, first_seen, last_seen), None
    except tracks.TrackUnavailable as reason:
        return None, str(reason)


def _text(value) -> str:
    """A cell as text; empty for NULL, NaN and blanks."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return ""
    return str(value).strip()


def _name(f) -> str:
    """What to call a flight: its call sign, or its address when it has none
    (not every aircraft broadcasts one)."""
    return _text(f.get("flt_id")) or _text(f.get("icao24")) or "this flight"


def _info(event) -> dict:
    """`info` as a dict; empty when it is anything else.

    `info` is JSON text in principle. Empty text, text that is not JSON, and
    JSON that is not an object (a list, a number, `null`) all mean the same
    to this page: no details.
    """
    try:
        parsed = json.loads(event["info"]) if event["info"] else {}
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _num(value, default: float = 0.0) -> float:
    """A JSON number as a float; a missing or `null` one is the default."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _label(f) -> str:
    route = f"{_text(f['adep']) or '?'} → {_text(f['ades']) or '?'}"
    why = f" · {f['why']}" if "why" in f.index and _text(f["why"]) else ""
    return f"{_name(f)}  {route}{why}"


def _pick(day):
    """The flight the user chose, as a row of the showcase/search frame."""
    with st.container(border=True):
        how = st.radio(
            "Find a flight", ["Showcase", "Search"], horizontal=True,
            key="flight_how",
            help="Showcase offers flights worth looking at, found from the "
                 "day's events. Search finds any flight.")
        left, right = st.columns([2, 3])
        if how == "Showcase":
            category = left.selectbox("Flights with a…", list(data.SHOWCASE),
                                      key="flight_category")
            found = ui.ask("showcase", day, category, n=8)
            note = data.SHOWCASE[category]
        else:
            callsign = left.text_input(
                "Call sign starts with", "", key="flight_cs",
                help="As broadcast, for example DLH4.").strip()
            icao24 = left.text_input(
                "or aircraft address starts with", "", key="flight_addr",
                help="The 24-bit address, for example 4ca2.").strip()
            if not (callsign or icao24):
                right.info("Type the start of a call sign or of an aircraft "
                           "address.")
                return None, None
            found = ui.ask("search_flights", day, callsign or None,
                           icao24 or None)
            note = (f"{len(found.frame)} flights match"
                    + (" (the first 50)." if len(found.frame) >= 50 else "."))
        if found.frame.empty:
            right.info("No such flight on this day. Try another kind, "
                       "another search, or another day.")
            return None, found
        i = right.selectbox(
            "Flight", range(len(found.frame)), key=f"flight_pick_{how}",
            format_func=lambda k: _label(found.frame.iloc[k]))
        st.caption(note)
    return found.frame.iloc[i], found


def _sentence(f) -> str:
    """The flight-list row, in words."""
    parts = [f"**{_name(f)}**"]
    if _text(f.get("typecode")):
        parts.append(f"a {_text(f['typecode'])}")
    if _text(f.get("icao_operator")):
        parts.append(f"of {_text(f['icao_operator'])}")
    parts.append(f"from **{_text(f.get('adep')) or 'an unknown airport'}** to "
                 f"**{_text(f.get('ades')) or 'an unknown airport'}**")
    seen = (f"first seen {pd.Timestamp(f['first_seen']):%d %b %H:%M}, last "
            f"seen {pd.Timestamp(f['last_seen']):%d %b %H:%M} UTC")
    return " ".join(parts) + ", " + seen + "."


def _measures(event) -> str:
    """The measurements an event carries, in words."""
    info = _info(event)
    t = event["type"]
    if t == "holding-end":
        return (f"{info.get('pattern', 'holding')}, "
                f"{info.get('circuits', '?')} circuits, "
                f"{_num(info.get('duration_s')) / 60:.0f} minutes, "
                f"{info.get('distance_nm', '?')} NM")
    if t == "go-around":
        return (f"lowest {info.get('low_height_ft', '?')} ft above the "
                f"airport, then up to {info.get('recovery_roc_ft_min', '?')} "
                "ft/min")
    if t == "pms-leg-exit":
        return (f"{info.get('distance_nm', '?')} NM along the leg in "
                f"{_num(info.get('duration_s')):.0f} s, merge point "
                f"{info.get('merge_point', '?')}")
    if t == "runway-crossing-entry":
        return f"crossing runway {info.get('runway', '?')}"
    if t in ("entry-deicing_pad", "exit-deicing_pad"):
        return f"{_num(info.get('opdi_time_in_use_s')) / 60:.0f} minutes on the pad"
    if t == "xing-fir":
        return f"{info.get('fir_from', '?')} to {info.get('fir_to', '?')}"
    labels = {"runway": "runway", "stand": "stand", "osm_ref": "area",
              "level_ft": "level (ft)"}
    for key, label in labels.items():
        if key in info:
            return f"{label} {info[key]}"
    return ""


#: Event types that get a close-up, with its title and the minutes of track
#: shown either side.
_CLOSE_UP = {
    "holding-end": ("Holding", _MARGIN_MIN),
    "go-around": ("Go-around", _MARGIN_MIN),
    "pms-leg-exit": ("Point-merge leg", _MARGIN_MIN),
    "runway-crossing-entry": ("Runway crossing", 2),
    "entry-deicing_pad": ("De-icing", 2),
}

#: Families whose events happen on the ground at an airport.
_GROUND = ("Block times", "Airport surface", "Take-off and landing",
           "Other runway events")


def _close_ups(track, events) -> None:
    """A map of each holding, go-around, leg, crossing or de-icing stop."""
    special = events[events["type"].isin(list(_CLOSE_UP))].head(
        _MAX_CLOSE_UPS)
    if special.empty:
        return
    st.subheader("Close-ups")
    for n, (_, e) in enumerate(special.iterrows()):
        info = _info(e)
        title, margin = _CLOSE_UP[e["type"]]
        seconds = _num(info.get("duration_s") or info.get("excursion_seconds")
                       or info.get("opdi_time_in_use_s"))
        at = pd.Timestamp(e["event_time"])
        start = at - pd.Timedelta(minutes=margin)
        end = at + pd.Timedelta(minutes=margin)
        if e["type"] in ("go-around", "entry-deicing_pad",
                         "runway-crossing-entry"):
            end += pd.Timedelta(seconds=seconds)     # these mark the start
        else:
            start -= pd.Timedelta(seconds=seconds)   # these mark the end
        a, b = st.columns([3, 2])
        with a:
            st.plotly_chart(charts.zoom_map(track, events, start, end),
                            width="stretch", key=f"closeup_{n}")
        with b:
            st.markdown(f"**{title}** at {at:%H:%M:%S} UTC")
            st.markdown(_measures(e))
            st.caption(catalogue.event(e["type"]).description)


def _ground_views(track, events, f) -> None:
    """The flight on the ground at each end, when its ground events are there.

    Shown only where the flight has at least three ground events with a
    position at that end: fewer is a runway time alone, and a map of one dot.
    """
    family = events["type"].map(catalogue.family_of)
    ground = events[family.isin(_GROUND) & events["lat"].notna()]
    took_off = events[events["type"] == "ATOT"]["event_time"]
    landed = events[events["type"] == "ALDT"]["event_time"]
    views = []
    if len(took_off):
        t = pd.Timestamp(took_off.iloc[0])
        before = ground[pd.to_datetime(ground["event_time"]) <= t]
        if len(before) >= 3:
            views.append((f"Leaving {_text(f.get('adep')) or 'the airport'}",
                          pd.Timestamp(before["event_time"].min())
                          - pd.Timedelta(minutes=1),
                          t + pd.Timedelta(seconds=45), len(before)))
    if len(landed):
        t = pd.Timestamp(landed.iloc[-1])
        after = ground[pd.to_datetime(ground["event_time"]) >= t]
        if len(after) >= 3:
            views.append((f"Arriving at {_text(f.get('ades')) or 'the airport'}",
                          t - pd.Timedelta(seconds=45),
                          pd.Timestamp(after["event_time"].max())
                          + pd.Timedelta(minutes=1), len(after)))
    if not views:
        return
    st.subheader("On the ground")
    st.caption("Stand, apron, taxiway and runway events are placed where the "
               "aircraft entered or left each area. Zoom in to follow the "
               "taxi route.")
    for col, (title, start, end, n) in zip(st.columns(len(views)), views):
        with col:
            st.markdown(f"**{title}** · {n} events")
            st.plotly_chart(
                charts.zoom_map(track, events, start, end, height=420,
                                width=500),
                width="stretch", key=f"ground_{title}")


def render() -> None:
    day = ui.header(
        "flight",
        "A flight's events make sense when you see them on the flight. Pick "
        "one below. Its track is read from OpenSky's raw position reports — "
        "the data OPDI starts from — and its events are placed on it.")

    f, found = _pick(day)
    if found is not None:
        ui.query(found, "Show the query that found these flights")
    if f is None:
        ui.back_next("flight")
        return

    route = (f"{_name(f)} &nbsp;·&nbsp; {_text(f.get('adep')) or '?'} → "
             f"{_text(f.get('ades')) or '?'}")
    why = _text(f.get("why")) if "why" in f.index else ""
    facts = [" of ".join(x for x in (_text(f.get("typecode")),
                                     _text(f.get("icao_operator"))) if x),
             f"first seen {pd.Timestamp(f['first_seen']):%d %b %H:%M}, last "
             f"seen {pd.Timestamp(f['last_seen']):%d %b %H:%M} UTC"]
    st.markdown(
        f"<div class='ex-flight'><div class='route'>{route}</div>"
        f"<div class='sub'>{' &nbsp;·&nbsp; '.join(x for x in facts if x)}"
        + (f" &nbsp;·&nbsp; <b>{why}</b>" if why else "") + "</div></div>",
        unsafe_allow_html=True)

    events = ui.ask("flight_events", day, f["flight_id"])
    ev = events.frame
    n_hours = len(tracks.hours(f["first_seen"], f["last_seen"]))
    with st.spinner(f"Reading the OpenSky track of "
                    f"{_name(f)} ({n_hours} hours of "
                    "position reports)…"):
        track, reason = _track(config.TRACKS, f["icao24"], f["first_seen"],
                               f["last_seen"])
    if reason:
        st.info(f"{reason} The charts below show the events alone, at the "
                "positions the pipeline published; the thin line joins one "
                "event to the next and is not the path flown.")

    ui.numbers({
        "events": ui.number(len(ev)),
        "kinds of event": ui.number(ev["type"].nunique()),
        "track points drawn": ui.number(0 if track is None else len(track)),
        "hours seen": f"{(pd.Timestamp(f['last_seen']) - pd.Timestamp(f['first_seen'])).total_seconds() / 3600:.1f}",
    })

    st.subheader("On the map")
    st.plotly_chart(charts.flight_map(track, ev), width="stretch",
                    key="flight_map")
    unplaced = sorted(ev[ev["lat"].isna()]["type"].unique())
    st.caption(
        "Grey line: the OpenSky track. Dots: the flight's events, coloured by "
        "family — click a family in the legend to hide it, hover a dot for "
        "what it is."
        + (f" Not on the map, because they are a time without a position: "
           f"{', '.join(unplaced)}." if unplaced else ""))

    st.subheader("Height over time")
    st.plotly_chart(charts.flight_profile(track, ev), width="stretch",
                    key="flight_profile")

    st.subheader("Everything that happened, in order")
    st.plotly_chart(charts.event_timeline(ev), width="stretch",
                    key="flight_timeline")
    st.dataframe(pd.DataFrame({
        "time (UTC)": pd.to_datetime(ev["event_time"]).dt.strftime(
            "%H:%M:%S"),
        "type": ev["type"],
        "detail": [_measures(e) for _, e in ev.iterrows()],
        "what it means": [catalogue.event(t).description for t in ev["type"]],
        "family": ev["type"].map(catalogue.family_of),
        "altitude (ft)": ev["altitude_ft"].round(0),
        "NM flown": ev["distance_flown_nm"].round(1),
    }), hide_index=True, width="stretch", height=360, column_config={
        "time (UTC)": st.column_config.TextColumn(width="small"),
        "type": st.column_config.TextColumn(width="medium"),
        "detail": st.column_config.TextColumn(width="medium"),
        "what it means": st.column_config.TextColumn(width="large"),
        "altitude (ft)": st.column_config.NumberColumn(width="small",
                                                       format="%d"),
        "NM flown": st.column_config.NumberColumn(width="small"),
    })
    ui.query(events, "Show the query for this flight's events")

    _close_ups(track, ev)
    _ground_views(track, ev, f)

    if track is not None:
        st.caption(
            "The track is OpenSky's raw state vectors for this aircraft "
            f"between first seen and last seen, thinned to {len(track):,} "
            "points for drawing. It is not cleaned, so a stray point is the "
            "receiver's, not the flight's.")
    st.markdown(ui.tag("Next", style.ACCENT)
                + "the same events, across every flight of the day.",
                unsafe_allow_html=True)
    ui.back_next("flight")
