"""Figures, as pure functions of a frame.

Kept apart from the pages so each can be tested without Streamlit, and so that
every builder has the same answer to "what if there is nothing to draw":
`empty()`, a figure that says so, never an exception from an empty frame.
"""

import math
from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from opdi_explorer import catalogue, style

#: A day's runways at one airport beyond this many fold into "Other": six is
#: the number of hues that can be told apart.
MAX_SERIES = 6
_SERIES = list(style.GROUP_COLOUR.values())


def empty(message: str, height: int = 220) -> go.Figure:
    """A figure with no marks that says why."""
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, x=0.5, y=0.5,
                       xref="paper", yref="paper",
                       font=dict(size=14, color="rgba(128,128,128,0.9)"))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return style.apply(fig, height=height, legend=False)


def _none(frame) -> bool:
    return frame is None or len(frame) == 0


# -- bars -------------------------------------------------------------------

def bar_by_hour(frame, value: str, unit: str, colour: str = style.ACCENT,
                height: int = 300):
    """Twenty-four bars, one per UTC hour, missing hours shown as zero."""
    if _none(frame):
        return empty("Nothing happened in any hour of this day.")
    full = (pd.DataFrame({"hour": range(24)})
            .merge(frame[["hour", value]], on="hour", how="left").fillna(0))
    fig = go.Figure(go.Bar(
        x=full["hour"], y=full[value], marker_color=colour,
        hovertemplate="%{x}:00 UTC<br>%{y:,.0f} " + unit + "<extra></extra>"))
    fig.update_xaxes(title_text="Hour of day (UTC)", dtick=3)
    fig.update_yaxes(title_text=unit.capitalize())
    return style.apply(fig, height=height, legend=False)


def ranked_bars(frame, label: str, value: str, unit: str,
                colour: str = style.ACCENT, n: int = 20,
                fmt: str = ",.0f"):
    """Horizontal bars, largest at the top."""
    if _none(frame):
        return empty("Nothing to rank on this day.")
    top = frame.sort_values(value, ascending=False).head(n).iloc[::-1]
    fig = go.Figure(go.Bar(
        x=top[value], y=top[label].astype(str), orientation="h",
        marker_color=colour,
        hovertemplate="%{y}<br>%{x:" + fmt + "} " + unit + "<extra></extra>"))
    fig.update_xaxes(title_text=unit.capitalize())
    return style.apply(fig, height=max(240, 22 * len(top) + 80), legend=False)


def binned_bars(frame, x: str, y: str, x_title: str, y_title: str,
                colour: str = style.ACCENT, horizontal: bool = False):
    """A histogram whose bins were counted in the query."""
    if _none(frame):
        return empty("Nothing to count on this day.")
    bar = (go.Bar(y=frame[x], x=frame[y], orientation="h", marker_color=colour,
                  hovertemplate="%{y:,.0f}<br>%{x:,.0f}<extra></extra>")
           if horizontal else
           go.Bar(x=frame[x], y=frame[y], marker_color=colour,
                  hovertemplate="%{x:,.0f}<br>%{y:,.0f}<extra></extra>"))
    fig = go.Figure(bar)
    fig.update_xaxes(title_text=y_title if horizontal else x_title)
    fig.update_yaxes(title_text=x_title if horizontal else y_title)
    fig.update_layout(bargap=0.05)
    return style.apply(fig, height=420 if horizontal else 320, legend=False)


def grouped_bars(frame, x: str, series: str, value: str, unit: str,
                 order: Optional[list] = None):
    """A few series side by side (at most six, in fixed colour order).

    `order` fixes the order of the categories on the x axis. Without it they
    appear in the order the rows happen to come, which for levels written as
    text ("5k", "30k", "3k") is no order at all.
    """
    if _none(frame):
        return empty("Nothing to compare on this day.")
    fig = go.Figure()
    names = list(dict.fromkeys(frame[series]))[:MAX_SERIES]
    for i, name in enumerate(names):
        part = frame[frame[series] == name]
        fig.add_trace(go.Bar(
            x=part[x].astype(str), y=part[value], name=str(name),
            marker_color=_SERIES[i],
            hovertemplate=f"{name}<br>%{{x}}<br>%{{y:,.0f}} {unit}"
                          "<extra></extra>"))
    fig.update_layout(barmode="group")
    if order is not None:
        fig.update_xaxes(categoryorder="array", categoryarray=list(order))
    fig.update_yaxes(title_text=unit.capitalize())
    return style.apply(fig, height=320)


def quartile_boxes(frame, label: str, unit: str,
                   colour: str = style.ACCENT):
    """Boxes from quartiles computed in the query (`q1, median, q3`, and
    `p10`/`p90` for the whiskers where the frame has them)."""
    if _none(frame):
        return empty("Nothing to summarise on this day.")
    f = frame.iloc[::-1]
    fig = go.Figure(go.Box(
        y=f[label].astype(str), q1=f["q1"], median=f["median"], q3=f["q3"],
        lowerfence=f["p10"] if "p10" in f.columns else f["q1"],
        upperfence=f["p90"] if "p90" in f.columns else f["q3"],
        orientation="h", marker_color=colour, line=dict(width=1.5),
        hoverinfo="x"))
    fig.update_xaxes(title_text=unit)
    return style.apply(fig, height=max(240, 30 * len(f) + 80), legend=False)


def runway_use(frame):
    """Movements per runway and hour: take-offs above, landings below."""
    if _none(frame):
        return empty("No take-off or landing with a runway at this airport "
                     "on this day.")
    totals = frame.groupby("runway")["movements"].sum().sort_values(
        ascending=False)
    keep = list(totals.index[:MAX_SERIES - 1]) if len(totals) > MAX_SERIES \
        else list(totals.index)
    f = frame.assign(runway=frame["runway"].where(
        frame["runway"].isin(keep), "Other"))
    f = f.groupby(["hour", "runway", "kind"], as_index=False)["movements"].sum()
    names = sorted(keep) + (["Other"] if (f["runway"] == "Other").any() else [])
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        subplot_titles=("Take-offs", "Landings"),
                        vertical_spacing=0.12)
    for i, runway in enumerate(names):
        for row, kind in ((1, "take-off"), (2, "landing")):
            part = f[(f["runway"] == runway) & (f["kind"] == kind)]
            fig.add_trace(go.Bar(
                x=part["hour"], y=part["movements"], name=f"Runway {runway}",
                legendgroup=runway, showlegend=row == 1,
                marker_color=_SERIES[i] if runway != "Other" else style.NEUTRAL,
                hovertemplate=f"Runway {runway} · {kind}<br>%{{x}}:00 UTC"
                              "<br>%{y} movements<extra></extra>"), row, 1)
    fig.update_layout(barmode="stack")
    fig.update_xaxes(range=[-0.5, 23.5], dtick=3)
    fig.update_xaxes(title_text="Hour of day (UTC)", row=2, col=1)
    fig = style.apply(fig, height=500)
    # The legend goes under the chart: above it, it runs into the title of
    # the upper panel.
    fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.16,
                                  x=0, title_text=""),
                      margin=dict(l=8, r=8, t=36, b=8))
    return fig


def bearing_rose(frame, colour: str = style.ACCENT):
    """Arrivals by the direction they come from, around the airport."""
    if _none(frame):
        return empty("No inbound 40 NM crossing at this airport on this day.")
    fig = go.Figure(go.Barpolar(
        r=frame["flights"], theta=frame["bearing"] + 5, width=10,
        marker_color=colour,
        hovertemplate="from %{theta:.0f}°<br>%{r} arrivals<extra></extra>"))
    fig.update_layout(polar=dict(
        angularaxis=dict(direction="clockwise", rotation=90,
                         tickvals=[0, 90, 180, 270],
                         ticktext=["N", "E", "S", "W"]),
        radialaxis=dict(showticklabels=False, ticks="")))
    return style.apply(fig, height=380, legend=False)


def heat(frame, x: str, y: str, value: str, unit: str):
    """A grid of one measure: darker is more."""
    if _none(frame):
        return empty("Nothing to show on this day.")
    grid = frame.pivot_table(index=y, columns=x, values=value, aggfunc="sum")
    grid = grid.reindex(columns=range(24)) if x == "hour" else grid
    order = grid.sum(axis=1).sort_values().index
    grid = grid.loc[order]
    fig = go.Figure(go.Heatmap(
        z=grid.values, x=list(grid.columns), y=[str(v) for v in grid.index],
        colorscale=style.SEQUENTIAL, xgap=2, ygap=2,
        colorbar=dict(title=unit, thickness=12),
        hovertemplate="%{y} · %{x}:00 UTC<br>%{z:,.0f} " + unit
                      + "<extra></extra>"))
    fig.update_xaxes(title_text="Hour of day (UTC)", dtick=3)
    return style.apply(fig, height=max(260, 24 * len(grid) + 90),
                       legend=False)


def _series_of(frame, by: Optional[str]):
    """`(name, rows, colour)` for a chart split by column *by*.

    Every row is drawn. With more groups than hues, the largest five keep a
    hue each and the rest are drawn together as "Other" in a neutral -- never
    dropped: a chart that silently leaves out the groups past the sixth shows
    whichever came first in the frame, and looks complete.
    """
    if by is None:
        return [(None, frame, _SERIES[0])]
    labels = frame[by].fillna("unknown").astype(str)
    sizes = labels.value_counts()
    ranked = sorted(sizes.index, key=lambda k: (-sizes[k], k))
    if len(ranked) > MAX_SERIES:
        keep = ranked[:MAX_SERIES - 1]
        out = [(k, frame[labels == k], _SERIES[i]) for i, k in enumerate(keep)]
        out.append(("Other", frame[~labels.isin(keep)], style.NEUTRAL))
        return out
    return [(k, frame[labels == k], _SERIES[i]) for i, k in enumerate(ranked)]


def scatter_xy(frame, x: str, y: str, x_title: str, y_title: str,
               by: Optional[str] = None, diagonal: bool = False,
               hover: Optional[str] = None):
    """Points, optionally split into a few named series."""
    if _none(frame):
        return empty("Nothing to plot on this day.")
    fig = go.Figure()
    for name, part, colour in _series_of(frame, by):
        fig.add_trace(go.Scatter(
            x=part[x], y=part[y], mode="markers", name=str(name or ""),
            marker=dict(size=8, color=colour, opacity=0.7,
                        line=dict(width=1, color="white")),
            text=part[hover].astype(str) if hover else None,
            hovertemplate=("%{text}<br>" if hover else "")
            + f"{x_title}: %{{x:,.1f}}<br>{y_title}: %{{y:,.1f}}"
              "<extra></extra>"))
    if diagonal:
        top = float(max(frame[x].max(), frame[y].max()))
        fig.add_trace(go.Scatter(
            x=[0, top], y=[0, top], mode="lines", name="equal",
            line=dict(width=1, dash="dot", color="rgba(128,128,128,0.7)"),
            hoverinfo="skip"))
    fig.update_xaxes(title_text=x_title)
    fig.update_yaxes(title_text=y_title)
    return style.apply(fig, height=360, legend=by is not None or diagonal)


def days_trend(frame, value: str, unit: str):
    """One measure per published day."""
    if _none(frame) or value not in frame.columns:
        return empty("The catalogue lists no days.")
    fig = go.Figure(go.Bar(
        x=frame["day"], y=frame[value], marker_color=style.ACCENT,
        hovertemplate="%{x|%d %b %Y}<br>%{y:,.0f} " + unit + "<extra></extra>"))
    fig.update_yaxes(title_text=unit.capitalize())
    return style.apply(fig, height=240, legend=False)


# -- maps -------------------------------------------------------------------

def _map_layout(fig, lat, lon, zoom: float, height: int, legend=True):
    fig.update_layout(
        map=dict(style=style.MAP_STYLE, zoom=zoom,
                 center=dict(lat=float(lat), lon=float(lon))),
        height=height, margin=dict(l=0, r=0, t=0, b=0), showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0,
                    title_text=""))
    return fig


def _fit_zoom(lats, lons, height: int = 480, width: int = 900) -> float:
    """The zoom at which the whole spread of the points is in view.

    Worked out, not looked up. The map draws 512-pixel tiles, so at zoom z a
    degree of longitude is `512 * 2**z / 360` pixels and a degree of latitude
    that divided by cos(latitude). The zoom is the largest at which both
    spans fit with a margin; a table of thresholds tuned by eye put a
    1,000 km flight half off the map.
    """
    import math

    lat_span = max(float(lats.max() - lats.min()), 0.01)
    lon_span = max(float(lons.max() - lons.min()), 0.01)
    mid = math.radians(float(lats.max() + lats.min()) / 2)
    margin = 1.35
    by_lon = math.log2(360 * width / (512 * lon_span * margin))
    by_lat = math.log2(360 * max(math.cos(mid), 0.2) * height
                       / (512 * lat_span * margin))
    return max(0.5, min(by_lon, by_lat, 14.0))


def unwrap(lons) -> np.ndarray:
    """Longitudes as one continuous run, without the jump at the date line.

    Longitude is stored between -180 and +180, so a flight heading east over
    the Pacific goes ..., +179, -179, ... and a line drawn through those
    numbers joins them the long way round: back across Asia, Europe and the
    Atlantic. Here each longitude is moved by a whole number of turns to sit
    next to the one before it (+179, +181, ...). The map draws longitudes
    beyond 180 where they belong, on the next copy of the world.
    """
    values = np.asarray(lons, dtype=float)
    if values.size < 2:
        return values
    return np.unwrap(values, period=360.0)


def _beside(lons, reference) -> np.ndarray:
    """Each longitude moved by whole turns to sit nearest its reference."""
    lons = np.asarray(lons, dtype=float)
    reference = np.asarray(reference, dtype=float)
    return lons + 360.0 * np.round((reference - lons) / 360.0)


def great_circle(lat1, lon1, lat2, lon2):
    """`(lats, lons)` along the shortest path between two points.

    The shortest way from Tokyo to Los Angeles is across the Pacific and bows
    north; a straight line between the two on the map is neither. Points
    every three degrees or so, the longitudes unwrapped.
    """
    p1, l1, p2, l2 = map(math.radians, (lat1, lon1, lat2, lon2))
    d = 2 * math.asin(math.sqrt(
        math.sin((p2 - p1) / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin((l2 - l1) / 2) ** 2))
    n = max(2, int(math.degrees(d) / 3) + 2)
    if d < 1e-9 or n == 2:
        return (np.array([lat1, lat2], dtype=float),
                unwrap([lon1, lon2]))
    f = np.linspace(0.0, 1.0, n)
    a, b = np.sin((1 - f) * d) / math.sin(d), np.sin(f * d) / math.sin(d)
    x = a * math.cos(p1) * math.cos(l1) + b * math.cos(p2) * math.cos(l2)
    y = a * math.cos(p1) * math.sin(l1) + b * math.cos(p2) * math.sin(l2)
    z = a * math.sin(p1) + b * math.sin(p2)
    lats = np.degrees(np.arctan2(z, np.hypot(x, y)))
    lons = unwrap(np.degrees(np.arctan2(y, x)))
    # The ends exactly where the airports are, not a rounding error away.
    lats[0], lats[-1] = lat1, lat2
    lons[0] = lon1
    lons[-1] = float(_beside([lon2], [lons[-1]])[0])
    return lats, lons


def airport_map(frame):
    """Airports sized by their movements."""
    if _none(frame):
        return empty("No airport with a departure or an arrival on this day.")
    f = frame.dropna(subset=["lat", "lon"])
    if f.empty:
        return empty("This release has no table of airport positions, so the "
                     "airports cannot be put on a map.")
    total = f["departures"] + f["arrivals"]
    fig = go.Figure(go.Scattermap(
        lat=f["lat"], lon=f["lon"], mode="markers",
        # Area, not radius, follows the count, and the largest airport is
        # about 22 px across: any bigger and the circles of the eastern US
        # and of western Europe merge into one blob.
        marker=dict(size=(total.clip(lower=1) ** 0.5).clip(upper=45) * 0.42
                    + 2.5, color=style.ACCENT, opacity=0.6),
        customdata=pd.DataFrame({
            "a": f["airport"], "n": f["name"].fillna(""),
            "d": f["departures"], "r": f["arrivals"]}).values,
        hovertemplate="<b>%{customdata[0]}</b> %{customdata[1]}<br>"
                      "%{customdata[2]:,} departures · "
                      "%{customdata[3]:,} arrivals<extra></extra>"))
    return _map_layout(fig, 25, 10, 1.1, 520, legend=False)


def route_map(frame):
    """The busiest routes, thicker where more flights flew them."""
    if _none(frame):
        return empty("No route between two different airports on this day.")
    f = frame.dropna(subset=["adep_lat", "adep_lon", "ades_lat", "ades_lon"])
    if f.empty:
        return empty("This release has no table of airport positions, so the "
                     "routes cannot be drawn.")
    fig = go.Figure()
    top = float(f["flights"].max())
    all_lats, all_lons, ends = [], [], []
    for r in f.itertuples():
        # A great circle, so a long route is drawn where it is flown and one
        # across the Pacific does not cut back across the rest of the map.
        lats, lons = great_circle(r.adep_lat, r.adep_lon,
                                  r.ades_lat, r.ades_lon)
        fig.add_trace(go.Scattermap(
            lat=lats, lon=lons, mode="lines", showlegend=False,
            line=dict(width=1.5 + 5 * r.flights / top, color=style.ACCENT),
            opacity=0.7,
            hovertemplate=f"<b>{r.adep} → {r.ades}</b><br>{r.flights} flights"
                          "<extra></extra>"))
        all_lats.append(lats); all_lons.append(lons)
        ends += [(lats[0], lons[0], r.adep), (lats[-1], lons[-1], r.ades)]
    fig.add_trace(go.Scattermap(
        lat=[e[0] for e in ends], lon=[e[1] for e in ends], mode="markers",
        marker=dict(size=6, color=style.ACCENT), showlegend=False,
        text=[e[2] for e in ends], hovertemplate="%{text}<extra></extra>"))
    lats = pd.Series(np.concatenate(all_lats))
    lons = pd.Series(np.concatenate(all_lons))
    return _map_layout(fig, (lats.min() + lats.max()) / 2,
                       (lons.min() + lons.max()) / 2,
                       _fit_zoom(lats, lons, 480, 600), 480, legend=False)


def point_map(frame, colour: str = style.ACCENT, by: Optional[str] = None,
              name: str = "events"):
    """A cloud of positions: where something happens."""
    if _none(frame):
        return empty("No event of this type carries a position on this day.")
    fig = go.Figure()
    groups = [(name, frame, colour)] if by is None else [
        (k, frame[frame[by] == k], _SERIES[i])
        for i, k in enumerate(list(dict.fromkeys(frame[by]))[:MAX_SERIES])]
    for label, part, hue in groups:
        fig.add_trace(go.Scattermap(
            lat=part["lat"], lon=part["lon"], mode="markers", name=str(label),
            marker=dict(size=4, color=hue, opacity=0.45),
            hovertemplate=f"{label}<br>%{{lat:.3f}}, %{{lon:.3f}}"
                          "<extra></extra>"))
    # Framed on the middle 98% of the points, so a handful of far-away ones
    # do not shrink everything else to a dot.
    lat = frame["lat"].clip(frame["lat"].quantile(0.01),
                            frame["lat"].quantile(0.99))
    lon = frame["lon"].clip(frame["lon"].quantile(0.01),
                            frame["lon"].quantile(0.99))
    return _map_layout(fig, (lat.min() + lat.max()) / 2,
                       (lon.min() + lon.max()) / 2,
                       _fit_zoom(lat, lon, 460, 600), 460,
                       legend=by is not None)


# -- one flight -------------------------------------------------------------

def _event_hover(events: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "type": events["type"],
        "time": pd.to_datetime(events["event_time"]).dt.strftime(
            "%H:%M:%S UTC"),
        "what": [catalogue.event(t).description for t in events["type"]],
    })


def _families(events: pd.DataFrame):
    """`(family, rows)` for the families present, in the dictionary's order,
    with types the dictionary does not know last."""
    fam = events["type"].map(catalogue.family_of)
    order = [f for f in list(catalogue.FAMILIES) + [catalogue.UNDESCRIBED]
             if (fam == f).any()]
    return [(f, events[fam == f]) for f in order]


def flight_map(track, events, height: int = 520, width: int = 1000):
    """The track, with the flight's events on it.

    With no track -- it could not be read -- the events are joined by a thin
    line in time order, which is not the path flown and is labelled so.
    """
    placed = events.dropna(subset=["lat", "lon"]) if not _none(events) \
        else pd.DataFrame(columns=["lat", "lon", "type", "event_time"])
    if _none(track) and placed.empty:
        return empty("This flight has no track and no event with a position.")
    fig = go.Figure()
    placed = placed.copy()
    if not _none(track):
        # Longitudes run on across the date line (see `unwrap`), and every
        # event is put on the same side of it as the track at that moment.
        track_lon = unwrap(track["lon"])
        fig.add_trace(go.Scattermap(
            lat=track["lat"], lon=track_lon, mode="lines",
            line=dict(width=3, color=style.TRACK), opacity=0.8,
            name="OpenSky track", hoverinfo="skip"))
        if not placed.empty:
            times = pd.to_datetime(track["event_time"]).values
            at = np.searchsorted(times,
                                 pd.to_datetime(placed["event_time"]).values)
            placed["lon"] = _beside(
                placed["lon"], track_lon[np.clip(at, 0, len(times) - 1)])
        spread_lat, spread_lon = track["lat"], pd.Series(track_lon)
    else:
        placed = placed.sort_values("event_time")
        placed["lon"] = unwrap(placed["lon"])
        fig.add_trace(go.Scattermap(
            lat=placed["lat"], lon=placed["lon"], mode="lines",
            line=dict(width=1.5, color=style.TRACK), opacity=0.6,
            name="event to event (not the path flown)", hoverinfo="skip"))
        spread_lat, spread_lon = placed["lat"], placed["lon"]
    for family, part in _families(placed):
        fig.add_trace(go.Scattermap(
            lat=part["lat"], lon=part["lon"], mode="markers", name=family,
            marker=dict(size=13, color=style.colour_of_family(family),
                        opacity=0.95),
            customdata=_event_hover(part).values,
            hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]}<br>"
                          "%{customdata[2]}<extra></extra>"))
    return _map_layout(
        fig, (spread_lat.min() + spread_lat.max()) / 2,
        (spread_lon.min() + spread_lon.max()) / 2,
        _fit_zoom(spread_lat, spread_lon, height, width), height)


def zoom_map(track, events, start, end, height: int = 380,
             width: int = 600):
    """The part of the flight between two times."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    t = track if _none(track) else track[
        (track["event_time"] >= start) & (track["event_time"] <= end)]
    e = events if _none(events) else events[
        (pd.to_datetime(events["event_time"]) >= start)
        & (pd.to_datetime(events["event_time"]) <= end)]
    return flight_map(t, e, height=height, width=width)


def flight_profile(track, events):
    """Altitude over time, with the events at their own altitude."""
    with_alt = events.dropna(subset=["altitude_ft"]) if not _none(events) \
        else pd.DataFrame(columns=["altitude_ft", "type", "event_time"])
    if _none(track) and with_alt.empty:
        return empty("This flight has no track and no event with an altitude.")
    fig = go.Figure()
    if not _none(track):
        fig.add_trace(go.Scatter(
            x=track["event_time"], y=track["altitude_ft"], mode="lines",
            line=dict(width=2, color=style.TRACK), name="OpenSky track",
            hovertemplate="%{x|%H:%M:%S}<br>%{y:,.0f} ft<extra></extra>"))
    else:
        path = with_alt.sort_values("event_time")
        fig.add_trace(go.Scatter(
            x=path["event_time"], y=path["altitude_ft"], mode="lines",
            line=dict(width=1.5, dash="dot", color=style.TRACK),
            name="event to event (not the path flown)", hoverinfo="skip"))
    for family, part in _families(with_alt):
        fig.add_trace(go.Scatter(
            x=part["event_time"], y=part["altitude_ft"], mode="markers",
            name=family,
            marker=dict(size=11, color=style.colour_of_family(family),
                        symbol=style.FAMILY_SYMBOL.get(family, "x"),
                        line=dict(width=1.5, color="white")),
            customdata=_event_hover(part).values,
            hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]}<br>"
                          "%{y:,.0f} ft<br>%{customdata[2]}<extra></extra>"))
    fig.update_yaxes(title_text="Altitude (ft)", rangemode="tozero")
    fig.update_xaxes(title_text="Time (UTC)")
    return style.apply(fig, height=400)


def event_timeline(events):
    """Every event on one time line, one row per family."""
    if _none(events):
        return empty("This flight has no events.")
    fig = go.Figure()
    rows = _families(events)
    for family, part in rows:
        fig.add_trace(go.Scatter(
            x=part["event_time"], y=[family] * len(part), mode="markers",
            name=family, showlegend=False,
            marker=dict(size=11, color=style.colour_of_family(family),
                        symbol=style.FAMILY_SYMBOL.get(family, "x"),
                        opacity=0.85, line=dict(width=1, color="white")),
            customdata=_event_hover(part).values,
            hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]}<br>"
                          "%{customdata[2]}<extra></extra>"))
    fig.update_yaxes(categoryorder="array",
                     categoryarray=[f for f, _ in rows][::-1])
    fig.update_xaxes(title_text="Time (UTC)")
    return style.apply(fig, height=70 + 34 * len(rows), legend=False)
