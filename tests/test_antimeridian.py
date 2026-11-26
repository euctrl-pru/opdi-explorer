"""Lines that cross the 180th meridian are drawn the way they were flown.

A flight from Japan to the United States goes east across the Pacific: its
longitude climbs to +180 and carries on from -180. Drawn as stored, the map
joins +179.9 to -179.9 with a line the long way round -- straight back across
Asia, Europe and the Atlantic.
"""

import datetime as dt

import numpy as np
import pandas as pd

from opdi_explorer import charts

T = dt.datetime(2026, 7, 30, 6, 0)

#: Tokyo towards Los Angeles: east across the date line.
PACIFIC = pd.DataFrame({
    "event_time": [T + dt.timedelta(minutes=30 * i) for i in range(9)],
    "lat": [35.5, 40.0, 44.0, 47.0, 48.0, 47.0, 44.0, 40.0, 34.0],
    "lon": [140.0, 155.0, 170.0, 179.5, -175.0, -160.0, -145.0, -130.0, -118.4],
    "altitude_ft": [0.0, 35000, 35000, 35000, 35000, 35000, 35000, 35000, 0.0],
})


def _steps(lons) -> np.ndarray:
    return np.abs(np.diff(np.asarray(lons, dtype=float)))


def test_unwrapping_keeps_neighbours_together():
    out = charts.unwrap([170.0, 179.5, -175.0, -160.0])
    assert list(out) == [170.0, 179.5, 185.0, 200.0]
    # Westbound, the other way.
    assert list(charts.unwrap([-170.0, -179.0, 178.0])) == [-170.0, -179.0, -182.0]
    # A track that never crosses is left exactly as it is.
    assert list(charts.unwrap([4.5, 8.5, 12.0])) == [4.5, 8.5, 12.0]


def test_a_transpacific_track_is_one_line_across_the_pacific():
    track = charts.flight_map(PACIFIC, pd.DataFrame(columns=[
        "type", "event_time", "lat", "lon", "altitude_ft"])).data[0]
    lons = np.array(track.lon, dtype=float)
    assert _steps(lons).max() < 30          # no jump across the map
    assert lons.min() >= 140 and lons.max() > 180
    # Never over Europe or the Atlantic.
    assert not ((lons > -100) & (lons < 100)).any()


def test_events_follow_the_track_across_the_date_line():
    events = pd.DataFrame({
        "type": ["ATOT", "top-of-climb", "xing-fir", "ALDT"],
        "event_time": [T, T + dt.timedelta(minutes=35),
                       T + dt.timedelta(minutes=125),
                       T + dt.timedelta(minutes=240)],
        "lat": [35.5, 40.5, 48.0, 34.0],
        "lon": [140.0, 156.0, -174.0, -118.4],
        "altitude_ft": [0.0, 35000.0, 35000.0, 0.0],
    })
    fig = charts.flight_map(PACIFIC, events)
    placed = np.concatenate([np.asarray(t.lon, dtype=float)
                             for t in fig.data[1:]])
    # The two events east of the date line sit on the same side as the track
    # there: at 186 and 241.6, not at -174 and -118.4.
    assert sorted(np.round(placed, 1)) == [140.0, 156.0, 186.0, 241.6]


def test_without_a_track_the_event_line_takes_the_short_way_too():
    events = pd.DataFrame({
        "type": ["ATOT", "xing-fir", "ALDT"],
        "event_time": [T, T + dt.timedelta(hours=2), T + dt.timedelta(hours=4)],
        "lat": [35.5, 48.0, 34.0], "lon": [140.0, -174.0, -118.4],
        "altitude_ft": [0.0, 35000.0, 0.0],
    })
    line = charts.flight_map(None, events).data[0]
    assert _steps(line.lon).max() < 90
    assert list(np.round(np.asarray(line.lon, dtype=float), 1)) == [
        140.0, 186.0, 241.6]


def test_the_map_is_centred_on_the_pacific_not_on_europe():
    centre = charts.flight_map(PACIFIC, None).layout.map.center
    assert 170 < centre.lon < 200


def test_a_close_up_at_the_date_line_stays_in_one_piece():
    fig = charts.zoom_map(PACIFIC, None, T + dt.timedelta(minutes=60),
                          T + dt.timedelta(minutes=150))
    lons = np.asarray(fig.data[0].lon, dtype=float)
    assert _steps(lons).max() < 30


def test_a_route_across_the_pacific_is_drawn_as_a_great_circle():
    routes = pd.DataFrame({
        "adep": ["RJAA"], "ades": ["KLAX"], "flights": [12],
        "adep_lat": [35.76], "adep_lon": [140.39],
        "ades_lat": [33.94], "ades_lon": [-118.41]})
    line = charts.route_map(routes).data[0]
    lons = np.asarray(line.lon, dtype=float)
    lats = np.asarray(line.lat, dtype=float)
    assert len(lons) > 10 and _steps(lons).max() < 30
    assert not ((lons > -100) & (lons < 100)).any()
    # A great circle between two points near 35 N bows north of both.
    assert lats.max() > 45


def test_a_short_route_is_still_a_line_between_its_two_airports():
    routes = pd.DataFrame({
        "adep": ["EDDF"], "ades": ["EGLL"], "flights": [20],
        "adep_lat": [50.03], "adep_lon": [8.57],
        "ades_lat": [51.47], "ades_lon": [-0.46]})
    line = charts.route_map(routes).data[0]
    assert round(line.lon[0], 2) == 8.57 and round(line.lon[-1], 2) == -0.46
    assert round(line.lat[0], 2) == 50.03 and round(line.lat[-1], 2) == 51.47
