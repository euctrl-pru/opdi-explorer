"""The data layer and what the flight list answers by itself."""

import pandas as pd

from opdi_explorer import data

from .conftest import DAY


def test_the_shown_sql_uses_relative_paths_and_runs_the_real_ones(
        explorer_release):
    r = data.flights_by_hour(DAY)
    assert "read_parquet('flight_list/flight_list_20260428.parquet')" in r.sql
    assert str(explorer_release) not in r.sql and "s3://" not in r.sql
    assert r.frame["flights"].sum() == 6


def test_the_shown_sql_is_the_query_that_ran_with_its_parameters(
        explorer_release):
    r = data.aircraft_types(DAY, n=3)
    assert "LIMIT 3" in r.sql and "{" not in r.sql
    assert not r.sql.startswith(" ")


def test_a_quote_in_a_parameter_cannot_break_the_query(explorer_release):
    assert data.run("SELECT {x} AS v", x="O'Hare").frame.iloc[0]["v"] == "O'Hare"


def test_a_json_pattern_in_a_query_survives(explorer_release):
    # `'{%'` is not a placeholder, and must reach DuckDB untouched.
    r = data.run("SELECT count(*) AS n FROM {flight_events} "
                 "WHERE info LIKE '{%'", DAY)
    assert r.frame.iloc[0]["n"] > 0 and "'{%'" in r.sql


def test_the_day_in_numbers(explorer_release):
    n = data.day_numbers(DAY).frame.iloc[0]
    assert (n["flights"], n["aircraft"], n["airports"]) == (6, 6, 7)
    assert n["events"] == 46 and n["event_types"] == 26


def test_the_trend_comes_from_the_catalogue(explorer_release):
    r = data.days_trend()
    assert list(r.frame.columns) == ["day", "flights", "events"]
    assert r.frame.iloc[0]["flights"] == 6 and "catalogue.parquet" in r.sql


def test_the_example_flight_is_a_complete_one(explorer_release):
    f = data.example_flight(DAY).frame.iloc[0]
    assert f["adep"] and f["ades"] and pd.notna(f["atot"]) and pd.notna(f["aldt"])


def test_airports_carry_names_and_positions(explorer_release):
    a = data.airports_by_departures(DAY).frame.set_index("airport")
    assert a.loc["EGLL", "name"] == "London Heathrow Airport"
    assert a.loc["EGLL", "arrivals"] == 2 and a.loc["EGLL", "departures"] == 1
    assert round(a.loc["EGLL", "lat"], 2) == 51.47


def test_without_an_airports_table_the_counts_survive(
        explorer_release_no_airports):
    assert not data.has_airports()
    a = data.airports_by_departures(DAY).frame.set_index("airport")
    assert a.loc["EGLL", "arrivals"] == 2 and pd.isna(a.loc["EGLL", "lat"])
    r = data.busiest_routes(DAY).frame
    assert len(r) == 4 and r["adep_lat"].isna().all()


def test_routes_are_pairs_of_different_airports(explorer_release):
    r = data.busiest_routes(DAY).frame
    # The training flight (EGBB to EGBB) is not a route.
    assert sorted(zip(r["adep"], r["ades"])) == [
        ("EDDF", "EGLL"), ("EGLL", "KJFK"), ("EKCH", "ENGM"), ("LFPG", "EGLL")]
    assert r["adep_lat"].notna().all()


def test_types_operators_and_sources(explorer_release):
    assert set(data.aircraft_types(DAY).frame["typecode"]) == {
        "A320", "A20N", "B77W", "P28A"}
    assert set(data.operators(DAY).frame["operator"]) == {
        "DLH", "AFR", "SAS", "BAW"}
    s = data.airport_sources(DAY).frame
    dep = s[s["end"] == "departure"].set_index("source")["flights"]
    assert dep["runway_event"] == 5 and dep["undetermined"] == 1


def test_airborne_time_is_take_off_to_landing(explorer_release):
    t = data.airborne_time_by_type(DAY).frame.set_index("typecode")
    # L1: 8 h seen, 12 min to take-off, landed 8 min before the end.
    assert t.loc["B77W", "median"] == 8 * 60 - 20
    assert t.loc["A320", "flights"] == 2
