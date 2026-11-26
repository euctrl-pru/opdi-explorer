"""Picking one flight, and the day's questions across flights."""

import pytest

from opdi_explorer import data

from .conftest import DAY


def test_the_categories_are_offered_in_a_fixed_order():
    assert list(data.SHOWCASE) == [
        "Holding pattern", "Go-around", "Point merge", "Gate to gate",
        "Runway crossing", "De-icing", "Stepped descent",
        "Many airspace crossings", "Long haul", "Training circuits"]
    # The flights with the most events are a count, not something to look at.
    assert "Most events" not in data.SHOWCASE
    assert all(data.SHOWCASE.values())


def test_airline_categories_leave_training_flights_out(explorer_release):
    assert list(data.showcase(DAY, "Holding pattern").frame["flight_id"]
                ) == ["H1"]
    assert list(data.showcase(DAY, "Go-around").frame["flight_id"]) == ["G1"]
    assert list(data.showcase(DAY, "Point merge").frame["flight_id"]
                ) == ["P1"]
    # T1 has the most holdings and go-arounds of the day, and no operator.
    assert list(data.showcase(DAY, "Training circuits").frame["flight_id"]
                ) == ["T1"]


def test_long_haul_ranks_the_airline_flights(explorer_release):
    assert data.showcase(DAY, "Long haul").frame.iloc[0]["flight_id"] == "L1"
    assert "T1" not in set(data.showcase(DAY, "Long haul").frame["flight_id"])


def test_the_categories_for_the_other_events(explorer_release):
    def first(category):
        return data.showcase(DAY, category).frame.iloc[0]

    # H1 left a stand and reached one.
    assert first("Gate to gate")["flight_id"] == "H1"
    assert "stand to stand" in first("Gate to gate")["why"]
    assert first("Runway crossing")["flight_id"] == "G1"
    assert first("Runway crossing")["why"] == "1 runway crossing"
    assert first("De-icing")["flight_id"] == "L1"
    # G1 levelled off twice on the way down; H1 only once, so it is not one.
    assert list(data.showcase(DAY, "Stepped descent").frame["flight_id"]
                ) == ["G1"]
    assert first("Stepped descent")["why"] == "2 level-offs in the descent"
    assert first("Many airspace crossings")["flight_id"] == "L1"
    assert first("Many airspace crossings")["why"] == "2 airspace crossings"


def test_why_says_what_makes_the_flight_worth_opening(explorer_release):
    assert data.showcase(DAY, "Holding pattern").frame.iloc[0]["why"] == (
        "1 holding, 2.0 circuits")
    assert data.showcase(DAY, "Go-around").frame.iloc[0]["why"] == (
        "1 go-around")
    assert "h in the air" in data.showcase(DAY, "Long haul").frame.iloc[0]["why"]


def test_a_category_with_no_flights_is_empty(explorer_release_no_point_merge):
    assert data.showcase(DAY, "Point merge").frame.empty


def test_an_unknown_category_is_refused():
    with pytest.raises(ValueError, match="Holding pattern"):
        data.showcase(DAY, "Best flights")


def test_the_showcase_carries_what_the_track_needs(explorer_release):
    f = data.showcase(DAY, "Long haul").frame.iloc[0]
    assert f["icao24"] == "ddd444" and f["flt_id"] == "BAW117"
    assert f["first_seen"].hour == 23 and f["last_seen"].day == 29


def test_search_is_a_prefix_and_case_insensitive(explorer_release):
    assert list(data.search_flights(DAY, callsign="baw").frame["flight_id"]
                ) == ["L1"]
    assert list(data.search_flights(DAY, icao24="AAA").frame["flight_id"]
                ) == ["H1"]
    assert data.search_flights(DAY, callsign="ZZZ").frame.empty
    assert len(data.search_flights(DAY).frame) == 6


def test_a_search_term_with_a_quote_is_just_text(explorer_release):
    assert data.search_flights(DAY, callsign="O'H").frame.empty


def test_one_flights_row_and_events(explorer_release):
    assert data.flight(DAY, "H1").frame.iloc[0]["ades"] == "EGLL"
    ev = data.flight_events(DAY, "H1").frame
    assert len(ev) == 17 and ev["event_time"].is_monotonic_increasing
    held = ev[ev["type"] == "holding-end"].iloc[0]
    assert held["holding_circuits"] == 2.0 and held["holding_duration_s"] == 600
    assert data.flight_events(DAY, "nope").frame.empty


def test_holding_by_destination_and_hour(explorer_release):
    h = data.holdings_by_destination_hour(DAY).frame
    egll = h[h["airport"] == "EGLL"].iloc[0]
    assert (egll["hour"], egll["holdings"], egll["minutes"]) == (9, 1, 10)


def test_level_flight_in_descent_per_arrival(explorer_release):
    r = data.level_share_in_descent(DAY).frame.set_index("airport")
    # Two arrivals at Heathrow: one with a 120 s level-off, one with two of
    # 60 s.
    assert r.loc["EGLL", "arrivals"] == 2
    assert r.loc["EGLL", "with_level_off"] == 2
    assert r.loc["EGLL", "level_min_per_arrival"] == 2.0
    assert r.loc["KJFK", "level_min_per_arrival"] == 0


# -- a sample of each table, to look at -------------------------------------

def test_a_sample_of_the_flight_list_is_whole_rows(explorer_release):
    r = data.sample_flight_list(DAY, n=4)
    assert len(r.frame) == 4 and len(r.frame.columns) == 46
    assert "USING SAMPLE" in r.sql
    # Asking for more than there is gives what there is.
    assert len(data.sample_flight_list(DAY, n=500).frame) == 6


def test_a_sample_of_events_carries_the_measurement_columns(explorer_release):
    r = data.sample_events(DAY, n=10)
    assert len(r.frame) == 10
    assert list(r.frame.columns) == list(data.EVENT_COLUMNS
                                         + data.MEASUREMENT_COLUMNS)


def test_the_event_sample_can_keep_one_type_or_the_measured_rows(
        explorer_release):
    only = data.sample_events(DAY, n=50, type_="go-around").frame
    assert set(only["type"]) == {"go-around"} and len(only) == 3
    measured = data.sample_events(DAY, n=50, measured=True).frame
    # Three holdings and one point-merge leg carry a measurement of their own.
    assert sorted(measured["type"]) == ["holding-end"] * 3 + ["pms-leg-exit"]
    assert measured["holding_duration_s"].notna().sum() == 3
