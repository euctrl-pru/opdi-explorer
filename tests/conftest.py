"""A one-day release and a slice of the state-vector store, on local disk.

Shaped exactly like the published files, with typed columns: an all-NULL
column written by pandas has no type, and DuckDB then cannot bind a function
that needs a timestamp -- which would fail the query for a reason the real
files never give.
"""

import datetime as dt
import json

import pandas as pd
import pytest

from opdi_explorer import config, read, release
from opdi_explorer import data

DAY = dt.date(2026, 4, 28)
T0 = dt.datetime(2026, 4, 28, 8, 0, 0)

_FL_STRINGS = ["flight_id", "icao24", "flt_id", "adep", "ades", "adep_p",
               "ades_p", "adep_source", "ades_source", "registration", "model",
               "typecode", "icao_aircraft_class", "icao_operator", "rwy_dep",
               "rwy_arr", "stnd_dep", "stnd_arr", "version", "release"]
_FL_TIMES = (["first_seen", "last_seen", "atot", "aldt", "aobt", "aibt"]
             + [f"c{r}_{end}" for end in ("arr", "dep")
                for r in (40, 50, 60, 100, 110, 120)])
_FL_DOUBLES = ["rwy_dep_bearing_deg", "rwy_arr_bearing_deg",
               "track_duration_min"]
_FL_BOOLS = ["superseded_dep", "superseded_arr", "movement_dep",
             "movement_arr"]

_EV_STRINGS = ["event_id", "flight_id", "type", "h3_res_5", "source",
               "version", "info", "icao24", "flt_id", "adep", "ades"]
_EV_DOUBLES = ["longitude", "latitude", "altitude_ft", "distance_flown_nm",
               "time_passed_s", "holding_duration_s", "holding_distance_nm",
               "holding_circuits", "pms_leg_time_s", "pms_leg_distance_nm",
               "pms_direct_to_distance_nm"]


def _typed(rows, strings, times, doubles, bools):
    df = pd.DataFrame(rows)
    for c in strings:
        df[c] = df.get(c, pd.Series([None] * len(df))).astype("string")
    for c in times:
        df[c] = pd.to_datetime(df.get(c, pd.Series([None] * len(df)))
                               ).astype("datetime64[us]")
    for c in doubles:
        df[c] = df.get(c, pd.Series([None] * len(df))).astype("float64")
    for c in bools:
        df[c] = df.get(c, pd.Series([None] * len(df))).astype("boolean")
    df["dof"] = DAY
    return df


def _flight(fid, icao24, flt_id, adep, ades, start_h, hours, operator="BAW",
            typecode="A320", took_off=True, landed=True):
    first = T0 + dt.timedelta(hours=start_h)
    last = first + dt.timedelta(hours=hours)
    return dict(
        flight_id=fid, icao24=icao24, flt_id=flt_id, adep=adep, ades=ades,
        adep_source="runway_event" if adep else "undetermined",
        ades_source="aerodrome" if ades else "undetermined",
        registration="G-" + fid, typecode=typecode, icao_operator=operator,
        first_seen=first, last_seen=last,
        atot=first + dt.timedelta(minutes=12) if took_off else None,
        aldt=last - dt.timedelta(minutes=8) if landed else None,
        rwy_dep="25R" if took_off else None, rwy_arr="27L" if landed else None,
        track_duration_min=hours * 60.0, superseded_dep=False,
        superseded_arr=False, movement_dep=bool(adep) and took_off,
        movement_arr=bool(ades) and landed, version="v6.1.0",
        release="v2.0.0")


def _event(flight, n, type_, minutes, info=None, lat=51.0, lon=0.0,
           alt=3000.0, version="events_v0.5.0", **measures):
    return dict(
        event_id=f"{flight['flight_id']}-E{n:04d}",
        flight_id=flight["flight_id"], type=type_,
        event_time=flight["first_seen"] + dt.timedelta(minutes=minutes),
        longitude=lon, latitude=lat, altitude_ft=alt, source="OSN",
        version=version,
        info=("" if info is None
              else info if isinstance(info, str) else json.dumps(info)),
        distance_flown_nm=float(minutes) * 5, time_passed_s=minutes * 60.0,
        icao24=flight["icao24"], flt_id=flight["flt_id"],
        adep=flight["adep"], ades=flight["ades"], **measures)


def _hold(seq, circuits, duration, context="arrival"):
    return {"holding_seq": seq, "pattern": "racetrack", "direction": "R",
            "circuits": circuits, "duration_s": duration, "distance_nm": 30.0,
            "altitude_start_ft": 9000, "altitude_end_ft": 8000,
            "straight_pct": 40, "context": context}


def _rwy(apt, runway, method="acdm"):
    return {"runway": runway, "rwy_ident": runway, "apt_icao": apt,
            "runway_bearing_deg": 270.0, "method": method}


def build_release(root, with_point_merge=True):
    """Write the release under *root*; returns the flights by id."""
    h1 = _flight("H1", "aaa111", "DLH900", "EDDF", "EGLL", 0, 2,
                 operator="DLH")
    g1 = _flight("G1", "bbb222", "AFR100", "LFPG", "EGLL", 1, 2,
                 operator="AFR")
    p1 = _flight("P1", "ccc333", "SAS400", "EKCH", "ENGM", 2, 1,
                 operator="SAS", typecode="A20N")
    l1 = _flight("L1", "ddd444", "BAW117", "EGLL", "KJFK", 15, 8,
                 typecode="B77W")
    t1 = _flight("T1", "eee555", "GBOOF", "EGBB", "EGBB", 3, 1, operator=None,
                 typecode="P28A")
    x1 = _flight("X1", "fff666", "XTEST", None, None, 4, 1, operator=None,
                 typecode=None, took_off=False, landed=False)
    flights = [h1, g1, p1, l1, t1, x1]

    ev = []
    # H1: stand to stand, with one holding before landing.
    ev += [
        _event(h1, 1, "first_seen", 0, lat=50.03, lon=8.57, alt=350.0),
        _event(h1, 2, "AOBT", 2, {"stand": "A12", "apt_icao": "EDDF",
                                  "take_off": str(h1["atot"]),
                                  "take_off_method": "acdm"},
               lat=None, lon=None, alt=None),
        _event(h1, 3, "exit-parking_position", 2,
               {"osm_aeroway": "parking_position", "osm_ref": "A12",
                "osm_airport": "EDDF", "opdi_time_in_use_s": 1800},
               lat=50.03, lon=8.57, alt=None),
        _event(h1, 4, "exit-taxiway", 9,
               {"osm_aeroway": "taxiway", "osm_ref": "N", "osm_airport": "EDDF",
                "opdi_time_in_use_s": 240}, lat=50.03, lon=8.55, alt=None),
        _event(h1, 5, "line-up", 10, _rwy("EDDF", "25R"), lat=50.04, lon=8.58,
               alt=None),
        _event(h1, 6, "take-off-roll", 11, _rwy("EDDF", "25R"), lat=50.04,
               lon=8.58, alt=None),
        _event(h1, 7, "ATOT", 12, _rwy("EDDF", "25R"), lat=50.04, lon=8.55,
               alt=380.0),
        _event(h1, 8, "top-of-climb", 30, {"method": "pru", "observed": True},
               lat=50.6, lon=5.0, alt=36000.0),
        _event(h1, 9, "xing-fir", 40,
               {"fir_from": "EDGGFIR", "fir_to": "EBBUFIR", "fl": 360.0,
                "vertical": False}, lat=50.7, lon=4.0, alt=36000.0,
               version="fir_v0.2.0"),
        _event(h1, 10, "level-off-descent-start", 80,
               {"kpi": "KPI19", "duration_s": 120, "distance_nm": 8.0,
                "level_ft": 9000}, lat=51.2, lon=0.6, alt=9000.0),
        _event(h1, 11, "level-off-descent-end", 82,
               {"kpi": "KPI19", "duration_s": 120, "distance_nm": 8.0,
                "level_ft": 9000}, lat=51.2, lon=0.5, alt=9000.0),
        _event(h1, 12, "holding-start", 85, _hold(1, 2.0, 600), lat=51.3,
               lon=0.3, alt=9000.0, version="holding_v0.2.0"),
        _event(h1, 13, "holding-end", 95, _hold(1, 2.0, 600), lat=51.3,
               lon=0.3, alt=8000.0, version="holding_v0.2.0",
               holding_duration_s=600.0, holding_distance_nm=30.0,
               holding_circuits=2.0),
        _event(h1, 14, "xing-40nm", 100,
               {"apt_icao": "EGLL", "direction": "inbound", "bearing": 95.0,
                "flight_level": 70}, lat=51.4, lon=0.6, alt=7000.0),
        _event(h1, 15, "ALDT", 112, _rwy("EGLL", "27L"), lat=51.46, lon=-0.43,
               alt=90.0),
        _event(h1, 16, "last_seen", 120, lat=51.47, lon=-0.45, alt=80.0),
        _event(h1, 17, "AIBT", 119, {"stand": "512", "apt_icao": "EGLL",
                                     "landing": str(h1["aldt"]),
                                     "landing_method": "acdm"},
               lat=None, lon=None, alt=None),
    ]
    # G1: a go-around at Heathrow, then a landing found the legacy way.
    ev += [
        _event(g1, 1, "first_seen", 0, lat=49.0, lon=2.55, alt=400.0),
        _event(g1, 2, "ATOT", 12, _rwy("LFPG", "26R"), lat=49.0, lon=2.5,
               alt=420.0),
        _event(g1, 3, "go-around", 95,
               {"apt_icao": "EGLL", "low_height_ft": 250,
                "recovery_roc_ft_min": 2800, "excursion_seconds": 480},
               lat=51.46, lon=-0.40, alt=330.0),
        _event(g1, 4, "ALDT", 112, _rwy("EGLL", "27R", "legacy"), lat=51.47,
               lon=-0.43, alt=90.0),
        _event(g1, 5, "last_seen", 120, lat=51.47, lon=-0.45, alt=80.0),
        # Two level-offs on the way down, and a runway crossed while taxiing in.
        _event(g1, 6, "level-off-descent-end", 70,
               {"kpi": "KPI19", "duration_s": 60, "distance_nm": 4.0,
                "level_ft": 5000}, lat=51.3, lon=0.4, alt=5000.0),
        _event(g1, 7, "level-off-descent-end", 80,
               {"kpi": "KPI19", "duration_s": 60, "distance_nm": 4.0,
                "level_ft": 4000}, lat=51.35, lon=0.2, alt=4000.0),
        _event(g1, 8, "runway-crossing-entry", 115, _rwy("EGLL", "27L"),
               lat=51.465, lon=-0.44, alt=None),
        _event(g1, 9, "runway-crossing-vacated", 116, _rwy("EGLL", "27L"),
               lat=51.464, lon=-0.44, alt=None),
    ]
    # P1: a point-merge arrival at Oslo.
    if with_point_merge:
        leg = {"apt_icao": "ENGM", "pms_id": "ENGM-1", "merge_point": "OSPAD",
               "leg_seq": 1, "direction": "cw", "leg_distance_nm": 20.0,
               "leg_level_ft": 11000, "duration_s": 180, "distance_nm": 12.0,
               "direct_to_distance_nm": 9.0, "direct_aligned": True}
        ev += [
            _event(p1, 1, "first_seen", 0, lat=55.6, lon=12.6, alt=20.0),
            _event(p1, 2, "pms-leg-entry", 40, leg, lat=60.0, lon=11.5,
                   alt=11000.0, version="pms_v0.2.0"),
            _event(p1, 3, "pms-leg-exit", 43, leg, lat=60.1, lon=11.2,
                   alt=11000.0, version="pms_v0.2.0", pms_leg_time_s=180.0,
                   pms_leg_distance_nm=12.0, pms_direct_to_distance_nm=9.0),
            _event(p1, 4, "pms-merge-point", 46,
                   {"apt_icao": "ENGM", "pms_id": "ENGM-1",
                    "merge_point": "OSPAD", "closest_nm": 0.4, "via_leg": True},
                   lat=60.15, lon=11.1, alt=7000.0, version="pms_v0.2.0"),
            _event(p1, 5, "last_seen", 60, lat=60.2, lon=11.08, alt=680.0),
        ]
    else:
        ev += [_event(p1, 1, "first_seen", 0, lat=55.6, lon=12.6, alt=20.0),
               _event(p1, 5, "last_seen", 60, lat=60.2, lon=11.08, alt=680.0)]
    # L1: long haul across midnight, two airspace crossings.
    ev += [
        _event(l1, 1, "first_seen", 0, lat=51.47, lon=-0.45, alt=80.0),
        _event(l1, 2, "ATOT", 12, _rwy("EGLL", "27L"), lat=51.47, lon=-0.48,
               alt=95.0),
        _event(l1, 3, "xing-fir", 60,
               {"fir_from": "EGTTFIR", "fir_to": "EISNFIR", "fl": 340.0,
                "vertical": False}, lat=52.0, lon=-5.5, alt=34000.0,
               version="fir_v0.2.0"),
        _event(l1, 4, "xing-fir", 120,
               {"fir_from": "EGTTFIR", "fir_to": "EISNFIR", "fl": 360.0,
                "vertical": False}, lat=52.1, lon=-5.6, alt=36000.0,
               version="fir_v0.2.0"),
        _event(l1, 5, "last_seen", 480, lat=40.64, lon=-73.78, alt=20.0),
        _event(l1, 6, "entry-deicing_pad", 3,
               {"osm_aeroway": "deicing_pad", "osm_airport": "EGLL",
                "opdi_time_in_use_s": 300}, lat=51.47, lon=-0.46, alt=None),
        _event(l1, 7, "exit-deicing_pad", 8,
               {"osm_aeroway": "deicing_pad", "osm_airport": "EGLL",
                "opdi_time_in_use_s": 300}, lat=51.47, lon=-0.46, alt=None),
    ]
    # T1: a training flight flying circuits and orbits at one aerodrome.
    ev += [
        _event(t1, 1, "first_seen", 0, lat=52.45, lon=-1.75, alt=330.0),
        _event(t1, 2, "holding-end", 15, _hold(1, 1.0, 180, "other"),
               lat=52.5, lon=-1.7, alt=2000.0, version="holding_v0.2.0",
               holding_duration_s=180.0, holding_circuits=1.0),
        _event(t1, 3, "go-around", 25, {"apt_icao": "EGBB"}, lat=52.45,
               lon=-1.75, alt=500.0),
        _event(t1, 4, "holding-end", 35, _hold(2, 1.5, 240, "other"),
               lat=52.5, lon=-1.7, alt=2000.0, version="holding_v0.2.0",
               holding_duration_s=240.0, holding_circuits=1.5),
        _event(t1, 5, "go-around", 45, {"apt_icao": "EGBB"}, lat=52.45,
               lon=-1.75, alt=500.0),
        _event(t1, 6, "last_seen", 60, lat=52.45, lon=-1.75, alt=330.0),
    ]
    # X1: a type the dictionary does not know, and an `info` that is not JSON.
    ev += [
        _event(x1, 1, "xing-tma", 5, {"tma": "LONDON"}, lat=51.5, lon=-0.2),
        _event(x1, 2, "ATOT", 6, "not json", lat=51.5, lon=-0.2),
    ]

    pub = root / "published"
    for sub in ("flight_list", "flight_events"):
        (pub / sub).mkdir(parents=True)
    _typed(flights, _FL_STRINGS, _FL_TIMES, _FL_DOUBLES, _FL_BOOLS).to_parquet(
        pub / "flight_list" / "flight_list_20260428.parquet")
    events = _typed(ev, _EV_STRINGS, [], _EV_DOUBLES, [])
    events["event_time"] = events["event_time"].astype("datetime64[us]")
    events.to_parquet(pub / "flight_events" / "flight_events_20260428.parquet")
    pd.DataFrame([
        {"day": DAY, "flights": len(flights), "events": len(ev),
         "release": "v2.0.0",
         "event_versions": ["events_v0.5.0", "fir_v0.2.0", "holding_v0.2.0",
                            "pms_v0.2.0"],
         "commit": "abf88db47a1484d4",
         "published_at": dt.datetime(2026, 11, 22, 6)},
    ]).to_parquet(pub / "catalogue.parquet")

    (root / "oa_airports").mkdir()
    pd.DataFrame([
        ("EGLL", "London Heathrow Airport", 51.4706, -0.4619, "GB", "London"),
        ("EDDF", "Frankfurt am Main Airport", 50.0333, 8.5706, "DE",
         "Frankfurt"),
        ("LFPG", "Charles de Gaulle Airport", 49.0128, 2.55, "FR", "Paris"),
        ("EKCH", "Copenhagen Kastrup Airport", 55.6179, 12.656, "DK",
         "Copenhagen"),
        ("ENGM", "Oslo Airport, Gardermoen", 60.1939, 11.1004, "NO", "Oslo"),
        ("KJFK", "John F Kennedy International Airport", 40.6398, -73.7789,
         "US", "New York"),
        ("EGBB", "Birmingham Airport", 52.4539, -1.748, "GB", "Birmingham"),
    ], columns=["ident", "name", "latitude_deg", "longitude_deg",
                "iso_country", "municipality"]).to_parquet(
        root / "oa_airports" / "part.parquet")
    return {f["flight_id"]: f for f in flights}


def _point_at(monkeypatch, root):
    monkeypatch.setattr(config, "RELEASE", str(root))
    monkeypatch.setattr(read, "_CON", None)
    monkeypatch.setitem(release._catalogue, "key", None)
    data.forget()


@pytest.fixture
def explorer_release(tmp_path, monkeypatch):
    build_release(tmp_path)
    _point_at(monkeypatch, tmp_path)
    return tmp_path


@pytest.fixture
def explorer_release_no_airports(tmp_path, monkeypatch):
    import shutil

    build_release(tmp_path)
    shutil.rmtree(tmp_path / "oa_airports")
    _point_at(monkeypatch, tmp_path)
    return tmp_path


@pytest.fixture
def explorer_release_no_point_merge(tmp_path, monkeypatch):
    build_release(tmp_path, with_point_merge=False)
    _point_at(monkeypatch, tmp_path)
    return tmp_path


# -- a slice of the state-vector store --------------------------------------

def _unix(when: dt.datetime) -> int:
    return int(when.replace(tzinfo=dt.timezone.utc).timestamp())


@pytest.fixture
def state_vectors(tmp_path, monkeypatch):
    """Hour folders in the store's layout, for the flights of the release.

    One sample a minute for every aircraft, from two hours before the release
    day's first flight to past midnight; the hour of 2026-04-29 03:00 has no
    folder, as a real gap would look.
    """
    root = tmp_path / "state_vectors"
    aircraft = ["aaa111", "bbb222", "ccc333", "ddd444", "eee555"]
    start = dt.datetime(2026, 4, 28, 6, 0)
    for h in range(0, 24):
        hour = start + dt.timedelta(hours=h)
        if hour == dt.datetime(2026, 4, 29, 3, 0):
            continue
        rows = []
        for m in range(60):
            t = _unix(hour + dt.timedelta(minutes=m))
            for i, a in enumerate(aircraft):
                rows.append(dict(
                    time=t, icao24=a, lat=50.0 + i + m / 600.0,
                    lon=1.0 + h / 10.0 + m / 600.0, velocity=100.0,
                    heading=90.0, vertRate=5.08, callsign="TEST    ",
                    onGround=False, baroAltitude=3048.0, geoAltitude=3100.0))
        folder = root / f"hour={_unix(hour)}"
        folder.mkdir(parents=True)
        pd.DataFrame(rows).to_parquet(folder / "part.parquet")
    monkeypatch.setattr(config, "TRACKS", str(root))
    monkeypatch.setattr(read, "_CON", None)
    return root
