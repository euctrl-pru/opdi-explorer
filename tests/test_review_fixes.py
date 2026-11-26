"""Defects found by the whole-branch review, each pinned by a test."""

import datetime as dt

import pandas as pd
import pytest

from opdi_explorer import config, read
from opdi_explorer import charts, data, style, tracks
from opdi_explorer.steps import flight

from .conftest import DAY


# 1 -- points beyond six groups were silently not drawn ---------------------

def test_a_scatter_with_many_groups_draws_every_point():
    f = pd.DataFrame({"g": [f"A{i}" for i in range(10) for _ in range(i + 1)],
                      "x": 1.0, "y": 2.0})
    fig = charts.scatter_xy(f, "x", "y", "X", "Y", by="g")
    assert sum(len(t.x) for t in fig.data) == len(f)
    names = [t.name for t in fig.data]
    # The five largest groups by name, the rest together and in a neutral.
    assert names == ["A9", "A8", "A7", "A6", "A5", "Other"]
    assert fig.data[-1].marker.color == style.NEUTRAL


def test_rows_with_no_group_are_drawn_and_named():
    f = pd.DataFrame({"g": ["a", None, None], "x": [1.0, 2.0, 3.0],
                      "y": [1.0, 2.0, 3.0]})
    fig = charts.scatter_xy(f, "x", "y", "X", "Y", by="g")
    assert sum(len(t.x) for t in fig.data) == 3
    assert "unknown" in [t.name for t in fig.data]


# 2 -- an `info` that is JSON but not an object crashed the flight page -----

@pytest.mark.parametrize("info", ["[1, 2]", "null", '"x"', "not json", "",
                                  '{"duration_s": null}', None])
@pytest.mark.parametrize("type_", ["holding-end", "go-around", "pms-leg-exit",
                                   "ATOT"])
def test_any_info_can_be_put_into_words(info, type_):
    assert isinstance(
        flight._measures(pd.Series({"type": type_, "info": info})), str)


def test_holding_measures_still_read(explorer_release):
    e = pd.Series({"type": "holding-end",
                   "info": '{"pattern": "racetrack", "circuits": 2.0, '
                           '"duration_s": 600, "distance_nm": 30.0}'})
    assert flight._measures(e) == "racetrack, 2.0 circuits, 10 minutes, 30.0 NM"


# 3 -- a failed track read was remembered for an hour -----------------------

def test_a_failed_track_read_is_tried_again(monkeypatch):
    calls = []

    def fetch(icao24, first, last, progress=None):
        calls.append(1)
        if len(calls) == 1:
            raise tracks.TrackUnavailable("the store could not be reached")
        return pd.DataFrame({"event_time": [first], "lat": [1.0], "lon": [2.0],
                             "altitude_ft": [3.0]})

    monkeypatch.setattr(tracks, "fetch", fetch)
    args = ("retry-test-store", "abc123", dt.datetime(2026, 4, 28, 9),
            dt.datetime(2026, 4, 28, 10))
    first, reason = flight._track(*args)
    assert first is None and "could not be reached" in reason
    second, reason = flight._track(*args)
    assert reason is None and len(second) == 1
    flight._track(*args)
    assert len(calls) == 2                  # the success is remembered


# 4 -- one failed look for the airports table stuck until restart -----------

def test_an_airports_table_that_appears_is_found(explorer_release_no_airports):
    assert not data.has_airports()
    folder = explorer_release_no_airports / "oa_airports"
    folder.mkdir()
    pd.DataFrame({"ident": ["EGLL"], "name": ["Heathrow"],
                  "latitude_deg": [51.47], "longitude_deg": [-0.46]}
                 ).to_parquet(folder / "part.parquet")
    assert data.has_airports()


# 6 -- a flight with no call sign was shown as "None" -----------------------

@pytest.mark.parametrize("flt_id", [None, "", "   ", float("nan")])
def test_a_flight_without_a_call_sign_is_named_by_its_address(flt_id):
    f = pd.Series({"flt_id": flt_id, "icao24": "4ca2b1"})
    assert flight._name(f) == "4ca2b1"
    assert flight._name(pd.Series({"flt_id": " DLH4 ", "icao24": "x"})) == "DLH4"


def test_the_sentence_of_a_flight_with_no_call_sign(explorer_release):
    f = pd.Series({"flt_id": None, "icao24": "4ca2b1", "typecode": None,
                   "icao_operator": None, "adep": None, "ades": "EGLL",
                   "first_seen": dt.datetime(2026, 4, 28, 9),
                   "last_seen": dt.datetime(2026, 4, 28, 10)})
    text = flight._sentence(f)
    assert "None" not in text and "**4ca2b1**" in text


# 7 -- "hold before landing" counted training flights -----------------------

def test_holdings_before_landing_are_the_arrival_ones(explorer_release):
    d = data.holdings_by_destination(DAY).frame
    # T1's two holds at EGBB have context `other`: not before a landing.
    assert list(d["airport"]) == ["EGLL"] and list(d["holdings"]) == [1]
    h = data.holdings_by_destination_hour(DAY).frame
    assert set(h["airport"]) == {"EGLL"}
    assert "context" in data.holdings_by_destination(DAY).sql


# 8 -- the level-off chart's levels were out of order -----------------------

def test_grouped_bars_keep_the_order_they_are_given():
    f = pd.DataFrame({"level": ["5k", "30k", "3k", "30k"],
                      "phase": ["climb", "climb", "descent", "descent"],
                      "n": [1, 2, 3, 4]})
    fig = charts.grouped_bars(f, "level", "phase", "n", "level-offs",
                              order=["3k", "5k", "30k"])
    assert list(fig.layout.xaxis.categoryarray) == ["3k", "5k", "30k"]


# 9 -- typed text naming a placeholder broke the query ----------------------

def test_text_that_looks_like_a_placeholder_is_just_text(explorer_release):
    assert data.run("SELECT {x} AS v", DAY,
                    x="{flight_list}").frame.iloc[0]["v"] == "{flight_list}"
    assert data.search_flights(DAY, callsign="{airports}").frame.empty
    assert data.run("SELECT {a} AS a, {b} AS b", a="{b}", b="z"
                    ).frame.iloc[0]["a"] == "{b}"


# 10 -- the track secret's scope and a quote in a key -----------------------

class _Recorder:
    def __init__(self):
        self.sql = []

    def execute(self, sql):
        self.sql.append(sql)


def test_the_track_secret_is_scoped_to_its_bucket_only(tmp_path, monkeypatch):
    keys = tmp_path / "env"
    keys.write_text("AWS_ACCESS_KEY_ID = ab'c\nAWS_SECRET_ACCESS_KEY = s'ecret\n")
    monkeypatch.setattr(config, "TRACKS", "s3://bucket/tables/state_vectors")
    monkeypatch.setattr(config, "TRACKS_ENV_FILE", str(keys))
    con = _Recorder()
    read._configure_tracks(con)
    sql = con.sql[0]
    # With the slash: `s3://bucket` would also match `s3://bucket-other/...`.
    assert "SCOPE 's3://bucket/'" in sql
    assert "KEY_ID 'ab''c'" in sql and "SECRET 's''ecret'" in sql


# the runway picker offered airports its chart then had nothing for ---------

def test_the_runway_picker_offers_airports_that_have_runway_events(
        explorer_release):
    r = data.runway_airports(DAY).frame
    assert set(r["airport"]) == {"EGLL", "EDDF", "LFPG"}
    assert r.set_index("airport").loc["EGLL", "movements"] == 3
    for airport in r["airport"]:
        assert not data.runway_use(DAY, airport).frame.empty
