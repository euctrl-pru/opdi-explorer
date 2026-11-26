"""One flight's track, read from the state-vector store."""

import datetime as dt

import pandas as pd
import pytest

from opdi_explorer import config
from opdi_explorer import tracks


def at(day, hour, minute=0):
    return dt.datetime(2026, 4, day, hour, minute)


def test_the_hours_of_a_window_are_inclusive_and_cross_midnight():
    hrs = tracks.hours(at(28, 23, 10), at(29, 0, 50))
    assert len(hrs) == 2 and hrs[1] - hrs[0] == 3600
    assert dt.datetime.fromtimestamp(hrs[0], dt.timezone.utc).hour == 23
    assert tracks.hours(at(28, 9, 0), at(28, 9, 59)) == [hrs[0] - 14 * 3600]


def test_a_flight_across_midnight_reads_the_hours_of_both_days(state_vectors):
    t = tracks.fetch("AAA111", at(28, 23, 10), at(29, 0, 50))
    assert t["event_time"].min() == pd.Timestamp("2026-04-28 23:10")
    assert t["event_time"].max() == pd.Timestamp("2026-04-29 00:50")
    # One sample a minute, both ends kept, the other aircraft left out.
    assert len(t) == 101
    assert t["event_time"].is_monotonic_increasing
    assert list(t.columns) == ["event_time", "lat", "lon", "altitude_ft",
                               "speed_kt", "roc_ft_min", "on_ground"]


def test_units_are_aviation(state_vectors):
    r = tracks.fetch("aaa111", at(28, 9, 0), at(28, 9, 5)).iloc[0]
    # Stored: 3048 m, 100 m/s, 5.08 m/s.
    assert r["altitude_ft"] == pytest.approx(10000, abs=1)
    assert r["speed_kt"] == pytest.approx(194.384)
    assert r["roc_ft_min"] == pytest.approx(1000, abs=1)


def test_fractions_of_a_second_do_not_cut_the_ends_off(state_vectors):
    t = tracks.fetch("aaa111",
                     pd.Timestamp("2026-04-28 09:00:00.500"),
                     pd.Timestamp("2026-04-28 09:05:00.250"))
    assert len(t) == 6


def test_a_missing_hour_is_skipped_not_fatal(state_vectors):
    # The folder of 03:00 on the 29th does not exist.
    t = tracks.fetch("aaa111", at(29, 2, 30), at(29, 3, 30))
    assert len(t) == 30 and t["event_time"].max() == pd.Timestamp(
        "2026-04-29 02:59")


def test_no_readable_hour_is_unavailable_with_a_reason(state_vectors):
    with pytest.raises(tracks.TrackUnavailable, match="no state vectors"):
        tracks.fetch("aaa111", at(29, 3, 10), at(29, 3, 50))


def test_an_aircraft_that_is_not_there_is_unavailable(state_vectors):
    with pytest.raises(tracks.TrackUnavailable, match="no state vectors"):
        tracks.fetch("000000", at(28, 9, 0), at(28, 9, 30))


def test_a_flight_over_the_cap_is_refused(state_vectors):
    with pytest.raises(tracks.TrackUnavailable, match="20 hours"):
        tracks.fetch("aaa111", at(28, 0, 0), at(29, 6, 0))


def test_no_track_store_configured(monkeypatch):
    monkeypatch.setattr(config, "TRACKS", None)
    with pytest.raises(tracks.TrackUnavailable, match="not configured"):
        tracks.fetch("aaa111", at(28, 9, 0), at(28, 9, 30))


def test_progress_ends_at_the_total(state_vectors):
    seen = []
    tracks.fetch("aaa111", at(28, 9, 0), at(28, 11, 30),
                 progress=lambda done, total: seen.append((done, total)))
    assert seen == [(3, 3)]                 # every hour in one read


def test_with_a_missing_hour_progress_goes_hour_by_hour(state_vectors):
    seen = []
    tracks.fetch("aaa111", at(29, 1, 30), at(29, 3, 30),
                 progress=lambda done, total: seen.append((done, total)))
    assert seen == [(1, 3), (2, 3), (3, 3)]


def test_thinning_keeps_both_ends():
    f = pd.DataFrame({"x": range(10001)})
    t = tracks.thin(f, 4000)
    assert len(t) <= 4001
    assert t["x"].iloc[0] == 0 and t["x"].iloc[-1] == 10000


def test_a_short_track_is_not_thinned():
    f = pd.DataFrame({"x": range(50)})
    assert len(tracks.thin(f, 4000)) == 50
