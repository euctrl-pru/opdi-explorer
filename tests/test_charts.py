"""Chart builders: colour identity, and what happens with nothing to draw."""

import datetime as dt

import pandas as pd

from opdi_explorer import catalogue, charts, style

NONE = pd.DataFrame()
T = dt.datetime(2026, 4, 28, 9, 0)

TRACK = pd.DataFrame({
    "event_time": [T + dt.timedelta(minutes=m) for m in range(0, 60, 5)],
    "lat": [51.0 + m / 100 for m in range(12)],
    "lon": [0.0 + m / 100 for m in range(12)],
    "altitude_ft": [1000.0 * m for m in range(12)],
})
EVENTS = pd.DataFrame({
    "type": ["ATOT", "go-around", "holding-end", "AOBT", "xing-tma"],
    "event_time": [T + dt.timedelta(minutes=m) for m in (1, 20, 30, 0, 40)],
    "lat": [51.0, 51.04, 51.06, None, 51.08],
    "lon": [0.0, 0.04, 0.06, None, 0.08],
    "altitude_ft": [300.0, 500.0, 9000.0, None, 7000.0],
})

EMPTY_CASES = [
    (charts.bar_by_hour, (NONE, "flights", "flights")),
    (charts.ranked_bars, (NONE, "airport", "flights", "flights")),
    (charts.binned_bars, (NONE, "seconds", "flights", "s", "flights")),
    (charts.grouped_bars, (NONE, "source", "end", "flights", "flights")),
    (charts.quartile_boxes, (NONE, "typecode", "minutes")),
    (charts.runway_use, (NONE,)),
    (charts.bearing_rose, (NONE,)),
    (charts.heat, (NONE, "hour", "airport", "minutes", "minutes")),
    (charts.scatter_xy, (NONE, "a", "b", "A", "B")),
    (charts.days_trend, (NONE, "flights", "flights")),
    (charts.airport_map, (NONE,)),
    (charts.route_map, (NONE,)),
    (charts.point_map, (NONE,)),
    (charts.flight_map, (NONE, NONE)),
    (charts.flight_profile, (NONE, NONE)),
    (charts.event_timeline, (NONE,)),
]


def test_every_builder_survives_an_empty_frame():
    for build, args in EMPTY_CASES:
        fig = build(*args)
        assert len(fig.data) == 0, build.__name__
        assert fig.layout.annotations, build.__name__


def test_airports_without_positions_say_so_instead_of_an_empty_map():
    f = pd.DataFrame({"airport": ["EGLL"], "name": [None], "lat": [None],
                      "lon": [None], "departures": [1], "arrivals": [2]})
    fig = charts.airport_map(f)
    assert not fig.data and "positions" in fig.layout.annotations[0].text


def test_a_family_keeps_its_colour_and_groups_share_one():
    assert style.colour_of("ATOT") == style.colour_of("go-around")   # runway
    assert style.symbol_of("ATOT") != style.symbol_of("go-around")
    assert style.colour_of("holding-start") != style.colour_of("ATOT")
    assert len(set(style.GROUP_COLOUR.values())) == 6
    assert set(style.GROUP_COLOUR) == set(catalogue.GROUPS)


def test_two_families_of_one_group_never_share_a_shape():
    for families in catalogue.GROUPS.values():
        shapes = [style.FAMILY_SYMBOL[f] for f in families]
        assert len(shapes) == len(set(shapes)), families


def test_an_undescribed_type_gets_a_neutral_not_a_groups_colour():
    assert style.colour_of("xing-tma") == style.NEUTRAL
    assert style.NEUTRAL not in style.GROUP_COLOUR.values()
    assert style.symbol_of("xing-tma")


def test_the_flight_map_draws_the_track_and_one_trace_per_family():
    fig = charts.flight_map(TRACK, EVENTS)
    names = [t.name for t in fig.data]
    assert names[0] == "OpenSky track"
    # AOBT has no position, so its family is not on the map.
    # In the dictionary's order, with the undescribed type last.
    assert names[1:] == ["Take-off and landing", "Other runway events",
                         "Holding", catalogue.UNDESCRIBED]


def test_without_a_track_the_events_are_joined_and_labelled_as_not_the_path():
    fig = charts.flight_map(TRACK.iloc[0:0], EVENTS)
    assert fig.data[0].mode == "lines"
    assert "not the path flown" in fig.data[0].name
    prof = charts.flight_profile(None, EVENTS)
    assert "not the path flown" in prof.data[0].name


def test_the_profile_uses_shapes_to_tell_families_apart():
    fig = charts.flight_profile(TRACK, EVENTS)
    by_name = {t.name: t for t in fig.data}
    assert (by_name["Take-off and landing"].marker.symbol
            != by_name["Other runway events"].marker.symbol)
    assert (by_name["Take-off and landing"].marker.color
            == by_name["Other runway events"].marker.color)


def test_a_zoom_keeps_only_its_window():
    fig = charts.zoom_map(TRACK, EVENTS, T + dt.timedelta(minutes=15),
                          T + dt.timedelta(minutes=35))
    assert len(fig.data[0].lat) == 5          # samples at 15..35 minutes
    assert {t.name for t in fig.data[1:]} == {"Other runway events", "Holding"}


def test_more_runways_than_hues_fold_into_other():
    f = pd.DataFrame({"hour": [8] * 8, "runway": list("ABCDEFGH"),
                      "kind": ["landing"] * 8,
                      "movements": [9, 8, 7, 6, 5, 4, 3, 2]})
    names = {t.name for t in charts.runway_use(f).data}
    assert "Runway Other" in names and len(names) == 6


def test_hours_with_nothing_are_drawn_as_zero_not_left_out():
    f = pd.DataFrame({"hour": [3, 7], "flights": [5, 9]})
    fig = charts.bar_by_hour(f, "flights", "flights")
    assert len(fig.data[0].x) == 24 and sum(fig.data[0].y) == 14
