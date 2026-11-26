"""What one event type looks like across a day."""

from opdi_explorer import data

from .conftest import DAY


def test_counts_are_events_and_flights_per_type(explorer_release):
    c = data.type_counts(DAY).frame.set_index("type")
    assert c.loc["ATOT", "events"] == 4 and c.loc["ATOT", "flights"] == 4
    assert c.loc["holding-end", "events"] == 3
    assert c.loc["holding-end", "flights"] == 2


def test_the_sample_row_is_one_with_details(explorer_release):
    # X1 carries an ATOT whose info is the text "not json"; the sample must be
    # a row that shows the fields.
    row = data.sample_row(DAY, "ATOT").frame.iloc[0]
    assert row["info"].startswith("{") and row["type"] == "ATOT"
    # A type with no details still has a sample.
    assert data.sample_row(DAY, "first_seen").frame.iloc[0]["info"] == ""


def test_info_that_is_not_json_is_no_details_not_an_error(explorer_release):
    r = data.runway_use(DAY, "EGLL").frame
    got = {(x.runway, x.kind): x.movements for x in r.itertuples()}
    assert got == {("27L", "landing"): 1, ("27R", "landing"): 1,
                   ("27L", "take-off"): 1}
    top = data.top_airports_for(DAY, "ATOT").frame
    assert set(top["airport"]) == {"EDDF", "LFPG", "EGLL"}   # X1 has none


def test_where_and_when(explorer_release):
    w = data.where(DAY, "go-around").frame
    assert len(w) == 3 and list(w.columns) == ["lat", "lon"]
    h = data.by_hour(DAY, "go-around").frame
    assert h["events"].sum() == 3


def test_the_sample_is_taken_from_the_events_of_that_type(explorer_release):
    # Three go-arounds among 46 events: a sample of two must be two of them,
    # not whatever two of the 46 happened to be go-arounds.
    assert len(data.where(DAY, "go-around", n=2).frame) == 2
    assert len(data.track_limits(DAY, n=4).frame) == 4


def test_an_event_type_with_no_events_gives_an_empty_frame(explorer_release):
    assert data.where(DAY, "entry-hangar").frame.empty
    assert data.by_hour(DAY, "entry-hangar").frame.empty
    assert data.top_airports_for(DAY, "entry-hangar").frame.empty
    assert data.sample_row(DAY, "entry-hangar").frame.empty


def test_events_without_a_position_are_not_put_on_the_map(explorer_release):
    assert data.where(DAY, "AOBT").frame.empty


def test_go_arounds_by_airport(explorer_release):
    g = data.go_arounds_by_airport(DAY).frame.set_index("airport")
    assert g.loc["EGBB", "go_arounds"] == 2 and g.loc["EGBB", "flights"] == 1
    assert g.loc["EGLL", "go_arounds"] == 1


def test_line_up_to_take_off_roll(explorer_release):
    r = data.lineup_to_roll(DAY).frame
    # H1 lined up at +10 min and rolled at +11 min.
    assert list(r["seconds"]) == [60] and list(r["flights"]) == [1]


def test_taxi_out_is_off_block_to_take_off(explorer_release):
    t = data.taxi_out_by_airport(DAY, min_flights=1).frame.iloc[0]
    assert (t["airport"], t["flights"], t["median_min"]) == ("EDDF", 1, 10.0)
    # The default leaves out an airport with a single flight.
    assert data.taxi_out_by_airport(DAY).frame.empty


def test_time_on_the_surface_by_kind(explorer_release):
    s = data.surface_time_by_kind(DAY).frame.set_index("kind")
    assert s.loc["parking_position", "median"] == 1800
    assert s.loc["taxiway", "median"] == 240


def test_top_of_climb_altitude_is_binned(explorer_release):
    t = data.toc_altitude(DAY).frame
    assert list(t["altitude_ft"]) == [36000] and list(t["flights"]) == [1]


def test_level_offs_by_phase_and_level(explorer_release):
    f = data.level_off_by_level(DAY).frame
    assert set(f["phase"]) == {"descent"}
    r = f[f["level_ft"] == 9000].iloc[0]
    assert (r["level_offs"], r["median_s"]) == (1, 120)
    assert list(f["level_ft"]) == [4000, 5000, 9000]


def test_arrival_bearings_are_binned_to_ten_degrees(explorer_release):
    b = data.arrival_bearings(DAY, "EGLL").frame
    assert list(b["bearing"]) == [90] and list(b["flights"]) == [1]
    assert data.arrival_bearings(DAY, "KJFK").frame.empty


def test_holding_measurements(explorer_release):
    h = data.holding_stats(DAY).frame
    assert sorted(h["circuits"]) == [1.0, 1.5, 2.0]
    assert 600.0 in set(h["duration_s"])
    assert set(h["context"]) == {"arrival", "other"}
    d = data.holdings_by_destination(DAY).frame.set_index("airport")
    assert d.loc["EGLL", "holdings"] == 1 and d.loc["EGLL", "minutes"] == 10
    # The training flight's holds at EGBB are not holds before a landing.
    assert "EGBB" not in d.index


def test_point_merge_leg_against_what_was_left(explorer_release):
    r = data.pms_leg_vs_direct(DAY).frame.iloc[0]
    assert (r["airport"], r["leg_nm"], r["direct_nm"], r["leg_s"]) == (
        "ENGM", 12.0, 9.0, 180.0)


def test_a_day_without_point_merge_is_empty_not_an_error(
        explorer_release_no_point_merge):
    assert data.pms_leg_vs_direct(DAY).frame.empty


def test_airspace_boundaries(explorer_release):
    f = data.fir_boundaries(DAY).frame.iloc[0]
    assert (f["fir_from"], f["fir_to"], f["crossings"]) == (
        "EGTTFIR", "EISNFIR", 2)


def test_track_limits_say_which_end(explorer_release):
    t = data.track_limits(DAY).frame
    assert set(t["which"]) == {"first seen", "last seen"}
    assert len(t) == 10
