"""Every question explorer asks of the published files.

Each function returns a `Result`: the frame, and the SQL that produced it. The
SQL is part of what explorer teaches -- a chart with the query under it shows a
newcomer how to get the same answer from the files themselves -- so the text
shown is the query that ran, with only the file locations shortened to the
paths a downloaded copy would have.

One day at a time. The published files are a few hundred megabytes a day and
every question here reads only the columns it needs, so nothing is loaded
whole and nothing is cached on disk.
"""

import datetime as dt
import re
from dataclasses import dataclass
from typing import Dict, Optional

import pandas as pd

from opdi_explorer import config, read, release


@dataclass
class Result:
    """A frame and the query that produced it."""
    frame: pd.DataFrame
    sql: str


#: Whether the release has an airports table, per release. Asked once: the
#: answer does not change while the app runs.
_airports: Dict[str, bool] = {}

#: The name the release's airports table is kept under on the connection,
#: once it has been read (see `has_airports`).
_AIRPORTS_TABLE = "explorer_airports"


def forget() -> None:
    """Drop what was learned about the release (for tests that swap it)."""
    _airports.clear()


def _release_root() -> str:
    return config.RELEASE.rstrip("/").replace("s3a://", "s3://")


def _sources(day: Optional[dt.date]):
    """`(real, shown)` text for each `{placeholder}` a query may name."""
    # The airports table is read once and kept (see `has_airports`); the
    # query as shown still names the file it came from.
    real = {"airports": _AIRPORTS_TABLE}
    shown = {"airports": "read_parquet('oa_airports/*.parquet')"}
    if day is not None:
        for kind in ("flight_list", "flight_events"):
            real[kind] = f"read_parquet('{release.day_file(kind, day)}')"
            shown[kind] = f"read_parquet('{kind}/{kind}_{day:%Y%m%d}.parquet')"
    return real, shown


def _literal(value) -> str:
    """*value* as a SQL literal."""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (list, tuple)):
        return ", ".join(_literal(v) for v in value)
    return "'" + str(value).replace("'", "''") + "'"


def run(template: str, day: Optional[dt.date] = None, **params) -> Result:
    """Run *template* and return its frame with the query as shown.

    `{flight_list}`, `{flight_events}` and `{airports}` name the files;
    `{name}` names a parameter, written into the query as a literal. Plain
    replacement, not `str.format`: the queries contain JSON patterns such as
    `'{%'`, which a format string would choke on.
    """
    real, shown = _sources(day)
    literals = {name: _literal(value) for name, value in params.items()}

    def fill(sources: Dict[str, str]) -> str:
        # One pass over the template. Filling the placeholders one after
        # another would re-read text already written in: a call sign typed
        # as `{flight_list}` became a file name inside a string literal.
        known = {**sources, **literals}
        return _PLACEHOLDER.sub(
            lambda m: known.get(m.group(1), m.group(0)), _tidy(template))

    return Result(read.query(fill(real)), fill(shown))


_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def _tidy(sql: str) -> str:
    """Strip the indentation a triple-quoted query carries."""
    lines = [ln for ln in sql.strip("\n").splitlines()]
    pad = min((len(ln) - len(ln.lstrip()) for ln in lines if ln.strip()),
              default=0)
    return "\n".join(ln[pad:] for ln in lines).strip()


def has_airports() -> bool:
    """Whether the release carries `oa_airports` (names and positions).

    Reads the table once and keeps it on the connection. It is small -- one
    row per airport in the world -- and reading it from the store cost four
    to five seconds every time a query joined it, three times on one step.
    Kept per release and per connection, so another release, or a fresh
    connection, reads its own.
    """
    key = _release_root()
    if _airports.get(key) and not read.query(
            "SELECT 1 FROM duckdb_tables() "
            f"WHERE table_name = '{_AIRPORTS_TABLE}'").empty:
        return True     # read for this release, and still on this connection
    try:
        read.query(f"""
            CREATE OR REPLACE TEMP TABLE {_AIRPORTS_TABLE} AS
            SELECT *
            FROM read_parquet('{key}/oa_airports/*.parquet')""")
    except Exception:  # noqa: BLE001
        # Not remembered. "No" from one failed read may be a network blip,
        # and remembering it would take the maps away until a restart.
        return False
    _airports.clear()
    _airports[key] = True
    return True


def J(name: str) -> str:
    """SQL reading field *name* out of `info`.

    `info` is JSON text, an empty text on events with no details, and -- in
    principle -- anything at all. Only valid JSON is parsed: an unreadable
    `info` means "no details", never a failed query.

    Queries that group on such a field read it in a CTE first and group on
    the plain column. Filtering a `GROUP BY ALL` on the field in `HAVING`
    pulled `info` itself into the grouping, and two crossings of the same
    boundary came back as two rows of one.
    """
    return (f"CASE WHEN json_valid(info) "
            f"THEN json_extract_string(info, '$.{name}') END")


def json_field(name: str) -> str:
    return J(name)


# ===========================================================================
# 1 -- the day, and the flight list
# ===========================================================================

def day_numbers(day) -> Result:
    return run("""
        SELECT (SELECT count(*) FROM {flight_list}) AS flights,
               (SELECT count(*) FROM {flight_events}) AS events,
               (SELECT count(DISTINCT a) FROM (
                    SELECT adep AS a FROM {flight_list}
                    UNION ALL SELECT ades FROM {flight_list})
                 WHERE a IS NOT NULL AND a <> 'OOA') AS airports,
               (SELECT count(DISTINCT icao24) FROM {flight_list}) AS aircraft,
               (SELECT count(DISTINCT type) FROM {flight_events}) AS event_types
        """, day)


def days_trend() -> Result:
    """Flights and events per published day, from the catalogue."""
    cat = release.catalogue()
    cols = [c for c in ("day", "flights", "events") if c in cat.columns]
    return Result(
        cat[cols].copy(),
        "SELECT day, flights, events\n"
        "FROM read_parquet('catalogue.parquet')\nORDER BY day")


def example_flight(day) -> Result:
    """One complete flight, to show what a row is."""
    return run("""
        SELECT *
        FROM {flight_list}
        WHERE adep IS NOT NULL AND ades IS NOT NULL AND adep <> ades
          AND atot IS NOT NULL AND aldt IS NOT NULL
          AND icao_operator IS NOT NULL AND typecode IS NOT NULL
        ORDER BY flight_id
        LIMIT 1
        """, day)


def airports_by_departures(day) -> Result:
    counts = """
        WITH movements AS (
            SELECT adep AS airport, count(*) AS departures, 0 AS arrivals
            FROM {flight_list}
            WHERE movement_dep AND adep IS NOT NULL AND adep <> 'OOA'
            GROUP BY adep
            UNION ALL
            SELECT ades, 0, count(*)
            FROM {flight_list}
            WHERE movement_arr AND ades IS NOT NULL AND ades <> 'OOA'
            GROUP BY ades
        )"""
    if has_airports():
        return run(counts + """
        SELECT m.airport, any_value(a.name) AS name,
               any_value(a.latitude_deg) AS lat,
               any_value(a.longitude_deg) AS lon,
               sum(m.departures) AS departures, sum(m.arrivals) AS arrivals
        FROM movements m
        LEFT JOIN {airports} a ON a.ident = m.airport
        GROUP BY m.airport
        ORDER BY sum(m.departures) + sum(m.arrivals) DESC, m.airport
        """, day)
    return run(counts + """
        SELECT airport, CAST(NULL AS VARCHAR) AS name,
               CAST(NULL AS DOUBLE) AS lat, CAST(NULL AS DOUBLE) AS lon,
               sum(departures) AS departures, sum(arrivals) AS arrivals
        FROM movements
        GROUP BY airport
        ORDER BY sum(departures) + sum(arrivals) DESC, airport
        """, day)


def busiest_routes(day, n: int = 30) -> Result:
    pairs = """
        WITH routes AS (
            SELECT adep, ades, count(*) AS flights
            FROM {flight_list}
            WHERE adep IS NOT NULL AND ades IS NOT NULL AND adep <> ades
              AND adep <> 'OOA' AND ades <> 'OOA'
            GROUP BY adep, ades
            ORDER BY flights DESC, adep, ades
            LIMIT {n}
        )"""
    if has_airports():
        return run(pairs + """
        SELECT r.adep, r.ades, r.flights,
               a.latitude_deg AS adep_lat, a.longitude_deg AS adep_lon,
               b.latitude_deg AS ades_lat, b.longitude_deg AS ades_lon
        FROM routes r
        LEFT JOIN {airports} a ON a.ident = r.adep
        LEFT JOIN {airports} b ON b.ident = r.ades
        ORDER BY r.flights DESC, r.adep, r.ades
        """, day, n=n)
    return run(pairs + """
        SELECT adep, ades, flights,
               CAST(NULL AS DOUBLE) AS adep_lat, CAST(NULL AS DOUBLE) AS adep_lon,
               CAST(NULL AS DOUBLE) AS ades_lat, CAST(NULL AS DOUBLE) AS ades_lon
        FROM routes
        ORDER BY flights DESC, adep, ades
        """, day, n=n)


def flights_by_hour(day) -> Result:
    return run("""
        SELECT hour(first_seen) AS hour, count(*) AS flights
        FROM {flight_list}
        GROUP BY 1
        ORDER BY 1
        """, day)


def aircraft_types(day, n: int = 20) -> Result:
    return run("""
        SELECT typecode, count(*) AS flights
        FROM {flight_list}
        WHERE typecode IS NOT NULL
        GROUP BY typecode
        ORDER BY flights DESC, typecode
        LIMIT {n}
        """, day, n=n)


def operators(day, n: int = 20) -> Result:
    return run("""
        SELECT icao_operator AS operator, count(*) AS flights
        FROM {flight_list}
        WHERE icao_operator IS NOT NULL
        GROUP BY icao_operator
        ORDER BY flights DESC, operator
        LIMIT {n}
        """, day, n=n)


def airport_sources(day) -> Result:
    """How each end of the flight was decided."""
    return run("""
        SELECT 'departure' AS "end", adep_source AS source, count(*) AS flights
        FROM {flight_list}
        GROUP BY adep_source
        UNION ALL
        SELECT 'destination', ades_source, count(*)
        FROM {flight_list}
        GROUP BY ades_source
        ORDER BY 1, 3 DESC
        """, day)


def airborne_time_by_type(day, n: int = 12) -> Result:
    """Take-off to landing, per aircraft type, as quartiles."""
    return run("""
        WITH t AS (
            SELECT typecode, date_diff('second', atot, aldt) / 60.0 AS minutes
            FROM {flight_list}
            WHERE atot IS NOT NULL AND aldt IS NOT NULL AND typecode IS NOT NULL
        )
        SELECT typecode, count(*) AS flights,
               quantile_cont(minutes, 0.10) AS p10,
               quantile_cont(minutes, 0.25) AS q1,
               quantile_cont(minutes, 0.50) AS median,
               quantile_cont(minutes, 0.75) AS q3,
               quantile_cont(minutes, 0.90) AS p90
        FROM t
        WHERE minutes BETWEEN 0 AND 1200
        GROUP BY typecode
        ORDER BY flights DESC, typecode
        LIMIT {n}
        """, day, n=n)


# ===========================================================================
# 2 -- flight events, one type at a time
# ===========================================================================

def type_counts(day) -> Result:
    return run("""
        SELECT type, count(*) AS events, count(DISTINCT flight_id) AS flights
        FROM {flight_events}
        GROUP BY type
        ORDER BY events DESC, type
        """, day)


def sample_row(day, type_: str) -> Result:
    """One whole row of *type_*, one with details where there is one."""
    return run("""
        SELECT *
        FROM {flight_events}
        WHERE type = {type}
        ORDER BY (info LIKE '{%') DESC, event_id
        LIMIT 1
        """, day, type=type_)


def where(day, type_: str, n: int = 20000) -> Result:
    """Where events of *type_* happen: a sample of their positions.

    Sampled from the events of that type, in a subquery. A `USING SAMPLE` on
    the scan itself samples the file *before* the filter: asked for 20,000
    taxiway entries out of six million events, it returned 1,714.
    """
    return run("""
        SELECT lat, lon
        FROM (
            SELECT latitude AS lat, longitude AS lon
            FROM {flight_events}
            WHERE type = {type}
              AND latitude IS NOT NULL AND longitude IS NOT NULL
        )
        USING SAMPLE reservoir({n} ROWS) REPEATABLE (42)
        """, day, type=type_, n=n)


def by_hour(day, type_: str) -> Result:
    return run("""
        SELECT hour(event_time) AS hour, count(*) AS events
        FROM {flight_events}
        WHERE type = {type}
        GROUP BY 1
        ORDER BY 1
        """, day, type=type_)


def top_airports_for(day, type_: str, n: int = 30) -> Result:
    """The airports with the most events of *type_*."""
    return run(f"""
        WITH e AS (
            SELECT coalesce({J('apt_icao')}, {J('osm_airport')}, ades, adep)
                       AS airport
            FROM {{flight_events}}
            WHERE type = {{type}}
        )
        SELECT airport, count(*) AS events
        FROM e
        WHERE airport IS NOT NULL
        GROUP BY airport
        ORDER BY events DESC, airport
        LIMIT {{n}}
        """, day, type=type_, n=n)


def runway_use(day, airport: str) -> Result:
    """Take-offs and landings per runway and hour at *airport*."""
    return run(f"""
        WITH e AS (
            SELECT hour(event_time) AS hour, {J('runway')} AS runway,
                   {J('apt_icao')} AS airport,
                   CASE type WHEN 'ATOT' THEN 'take-off' ELSE 'landing' END
                       AS kind
            FROM {{flight_events}}
            WHERE type IN ('ATOT', 'ALDT')
        )
        SELECT hour, runway, kind, count(*) AS movements
        FROM e
        WHERE airport = {{airport}} AND runway IS NOT NULL
        GROUP BY hour, runway, kind
        ORDER BY hour, runway, kind
        """, day, airport=airport)


def runway_airports(day, n: int = 30) -> Result:
    """The airports `runway_use` has something to show for.

    Counted the way `runway_use` filters -- a take-off or landing that names
    both the airport and the runway in `info` -- so an airport offered here
    is never one whose chart then comes up empty.
    """
    return run(f"""
        WITH e AS (
            SELECT {J('apt_icao')} AS airport, {J('runway')} AS runway
            FROM {{flight_events}}
            WHERE type IN ('ATOT', 'ALDT')
        )
        SELECT airport, count(*) AS movements
        FROM e
        WHERE airport IS NOT NULL AND runway IS NOT NULL
        GROUP BY airport
        ORDER BY movements DESC, airport
        LIMIT {{n}}
        """, day, n=n)


def go_arounds_by_airport(day, n: int = 25) -> Result:
    return run(f"""
        WITH e AS (
            SELECT coalesce({J('apt_icao')}, ades) AS airport, flight_id
            FROM {{flight_events}}
            WHERE type = 'go-around'
        )
        SELECT airport, count(*) AS go_arounds,
               count(DISTINCT flight_id) AS flights
        FROM e
        WHERE airport IS NOT NULL
        GROUP BY airport
        ORDER BY go_arounds DESC, airport
        LIMIT {{n}}
        """, day, n=n)


def lineup_to_roll(day) -> Result:
    """Seconds between lining up and starting the take-off run, binned."""
    return run("""
        WITH lined AS (
            SELECT flight_id, min(event_time) AS t
            FROM {flight_events} WHERE type = 'line-up' GROUP BY flight_id
        ), rolled AS (
            SELECT flight_id, min(event_time) AS t
            FROM {flight_events} WHERE type = 'take-off-roll' GROUP BY flight_id
        )
        SELECT floor(date_diff('second', lined.t, rolled.t) / 15) * 15
                   AS seconds,
               count(*) AS flights
        FROM lined JOIN rolled USING (flight_id)
        WHERE date_diff('second', lined.t, rolled.t) BETWEEN 0 AND 1800
        GROUP BY 1
        ORDER BY 1
        """, day)


def taxi_out_by_airport(day, n: int = 25, min_flights: int = 5) -> Result:
    """Off-block to take-off, per airport."""
    return run(f"""
        WITH taxi AS (
            SELECT coalesce({J('apt_icao')}, adep) AS airport,
                   date_diff('second', event_time,
                             TRY_CAST({J('take_off')} AS TIMESTAMP)) / 60.0
                       AS minutes
            FROM {{flight_events}}
            WHERE type = 'AOBT'
        )
        SELECT airport, count(*) AS flights,
               quantile_cont(minutes, 0.5) AS median_min,
               quantile_cont(minutes, 0.9) AS p90_min
        FROM taxi
        WHERE airport IS NOT NULL AND minutes BETWEEN 0 AND 120
        GROUP BY airport
        HAVING count(*) >= {{min_flights}}
        ORDER BY flights DESC, airport
        LIMIT {{n}}
        """, day, n=n, min_flights=min_flights)


def surface_time_by_kind(day) -> Result:
    """Time spent on each kind of airport area, as quartiles."""
    return run(f"""
        WITH used AS (
            SELECT {J('osm_aeroway')} AS kind,
                   TRY_CAST({J('opdi_time_in_use_s')} AS DOUBLE) AS seconds
            FROM {{flight_events}}
            WHERE type LIKE 'exit-%'
        )
        SELECT kind, count(*) AS events,
               quantile_cont(seconds, 0.25) AS q1,
               quantile_cont(seconds, 0.50) AS median,
               quantile_cont(seconds, 0.75) AS q3,
               quantile_cont(seconds, 0.90) AS p90
        FROM used
        WHERE kind IS NOT NULL AND seconds IS NOT NULL
        GROUP BY kind
        ORDER BY events DESC, kind
        """, day)


def toc_altitude(day) -> Result:
    """Altitude of the top of climb, in 1,000 ft bins."""
    return run("""
        SELECT floor(altitude_ft / 1000) * 1000 AS altitude_ft,
               count(*) AS flights
        FROM {flight_events}
        WHERE type = 'top-of-climb' AND altitude_ft IS NOT NULL
        GROUP BY 1
        ORDER BY 1
        """, day)


def level_off_by_level(day) -> Result:
    """Level-offs by phase and altitude: how many, and how long."""
    return run(f"""
        WITH lo AS (
            SELECT CASE type WHEN 'level-off-climb-end' THEN 'climb'
                             ELSE 'descent' END AS phase,
                   TRY_CAST({J('level_ft')} AS DOUBLE) AS level_ft,
                   TRY_CAST({J('duration_s')} AS DOUBLE) AS duration_s
            FROM {{flight_events}}
            WHERE type IN ('level-off-climb-end', 'level-off-descent-end')
        )
        SELECT phase, floor(level_ft / 1000) * 1000 AS level_ft,
               count(*) AS level_offs,
               quantile_cont(duration_s, 0.5) AS median_s
        FROM lo
        WHERE level_ft IS NOT NULL
        GROUP BY phase, floor(level_ft / 1000) * 1000
        ORDER BY phase, level_ft
        """, day)


def arrival_bearings(day, airport: str) -> Result:
    """From which direction arrivals cross 40 NM around *airport*."""
    return run(f"""
        WITH e AS (
            SELECT TRY_CAST({J('bearing')} AS DOUBLE) AS bearing,
                   {J('apt_icao')} AS airport, {J('direction')} AS direction
            FROM {{flight_events}}
            WHERE type = 'xing-40nm'
        )
        SELECT floor(bearing / 10) * 10 AS bearing, count(*) AS flights
        FROM e
        WHERE airport = {{airport}} AND direction = 'inbound'
          AND bearing IS NOT NULL
        GROUP BY floor(bearing / 10) * 10
        ORDER BY 1
        """, day, airport=airport)


def holding_stats(day) -> Result:
    """Every holding of the day, with its measurements."""
    return run(f"""
        SELECT flight_id, ades AS airport,
               holding_duration_s AS duration_s,
               holding_circuits AS circuits,
               holding_distance_nm AS distance_nm,
               {J('pattern')} AS pattern, {J('context')} AS context,
               latitude AS lat, longitude AS lon
        FROM {{flight_events}}
        WHERE type = 'holding-end'
        ORDER BY duration_s DESC, flight_id
        """, day)


def holdings_by_destination(day, n: int = 25) -> Result:
    """Holdings before landing, per destination.

    Only those whose `context` is `arrival`. Every holding has a destination
    on its row, but a hold far from it, or the orbits of a training flight
    that left and returned to one aerodrome, is not a hold before landing --
    and counted in, the training aerodromes lead the ranking.
    """
    return run(f"""
        WITH h AS (
            SELECT ades AS airport, flight_id, holding_duration_s AS seconds,
                   {J('context')} AS context
            FROM {{flight_events}}
            WHERE type = 'holding-end'
        )
        SELECT airport, count(*) AS holdings,
               count(DISTINCT flight_id) AS flights,
               sum(seconds) / 60.0 AS minutes,
               quantile_cont(seconds, 0.5) / 60.0 AS median_min
        FROM h
        WHERE airport IS NOT NULL AND context = 'arrival'
        GROUP BY airport
        ORDER BY holdings DESC, airport
        LIMIT {{n}}
        """, day, n=n)


def pms_leg_vs_direct(day) -> Result:
    """Each point-merge leg flown: distance along it, and what was left."""
    return run(f"""
        SELECT flight_id, coalesce({J('apt_icao')}, ades) AS airport,
               {J('merge_point')} AS merge_point,
               pms_leg_distance_nm AS leg_nm,
               pms_direct_to_distance_nm AS direct_nm,
               pms_leg_time_s AS leg_s
        FROM {{flight_events}}
        WHERE type = 'pms-leg-exit'
        ORDER BY airport, flight_id
        """, day)


def fir_boundaries(day, n: int = 25) -> Result:
    """The airspace boundaries crossed most often, side by side."""
    return run(f"""
        WITH e AS (
            SELECT {J('fir_from')} AS fir_from, {J('fir_to')} AS fir_to,
                   {J('vertical')} AS vertical
            FROM {{flight_events}}
            WHERE type = 'xing-fir'
        )
        SELECT fir_from, fir_to, count(*) AS crossings
        FROM e
        WHERE fir_from IS NOT NULL AND fir_to IS NOT NULL
          AND coalesce(vertical, 'false') <> 'true'
        GROUP BY fir_from, fir_to
        ORDER BY crossings DESC, fir_from, fir_to
        LIMIT {{n}}
        """, day, n=n)


def track_limits(day, n: int = 20000) -> Result:
    """Where tracks begin and end: a picture of what the receivers see."""
    return run("""
        SELECT lat, lon, which
        FROM (
            SELECT latitude AS lat, longitude AS lon,
                   CASE type WHEN 'first_seen' THEN 'first seen'
                             ELSE 'last seen' END AS which
            FROM {flight_events}
            WHERE type IN ('first_seen', 'last_seen')
              AND latitude IS NOT NULL AND longitude IS NOT NULL
        )
        USING SAMPLE reservoir({n} ROWS) REPEATABLE (42)
        """, day, n=n)


# ===========================================================================
# 3 -- one flight
# ===========================================================================

#: Showcase categories, in the order offered, with what each one is.
#:
#: Named after the event they show, so the list reads as "flights with a ...".
#: There is no "most events" category: the flights with the most events are
#: long taxi sequences at big airports, which is a count, not something to
#: look at.
SHOWCASE: Dict[str, str] = {
    "Holding pattern": "Airline flights that flew a holding pattern on the "
                       "way in: loops flown while waiting to land.",
    "Go-around": "Airline flights that gave up a landing, climbed away and "
                 "came round again.",
    "Point merge": "Arrivals that flew along a point-merge leg before being "
                   "turned towards the runway.",
    "Gate to gate": "Flights followed from the stand they left to the stand "
                    "they reached, with their taxi, runway and block events.",
    "Runway crossing": "Flights that taxied across another runway on their "
                       "way to or from their own.",
    "De-icing": "Flights that stopped on a de-icing pad before take-off.",
    "Stepped descent": "Arrivals that levelled off several times on the way "
                       "down, instead of descending in one go.",
    "Many airspace crossings": "Flights that passed through the most flight "
                               "information regions.",
    "Long haul": "The longest flights that were followed from take-off to "
                 "landing.",
    "Training circuits": "Flights that left and returned to one aerodrome, "
                         "flying circuits and orbits: a good picture of what "
                         "the detectors see.",
}

#: Per category: (extra filter, score, why-text), all SQL over `f` (the flight
#: row) and `c` (its event counts).
_AIRLINE = ("f.adep IS NOT NULL AND f.ades IS NOT NULL AND f.adep <> f.ades "
            "AND f.icao_operator IS NOT NULL "
            "AND f.atot IS NOT NULL AND f.aldt IS NOT NULL")


def _counted(column: str, one: str, many: str) -> str:
    """SQL text for "1 holding" / "3 holdings"."""
    return (f"{column} || CASE {column} WHEN 1 THEN ' {one}' "
            f"ELSE ' {many}' END")


_SHOWCASE_SQL = {
    "Holding pattern": (
        _AIRLINE + " AND c.holdings > 0", "c.circuits + c.holdings",
        _counted("c.holdings", "holding", "holdings")
        + " || ', ' || round(c.circuits, 1) || ' circuits'"),
    "Go-around": (
        _AIRLINE + " AND c.go_arounds > 0", "c.go_arounds",
        _counted("c.go_arounds", "go-around", "go-arounds")),
    "Point merge": (
        _AIRLINE + " AND c.pms_legs > 0", "c.pms_legs + c.merge_points",
        _counted("c.pms_legs", "point-merge leg", "point-merge legs")),
    "Gate to gate": (
        _AIRLINE + " AND c.off_blocks > 0 AND c.in_blocks > 0",
        "c.surface",
        "c.surface || ' events on the ground, stand to stand'"),
    "Runway crossing": (
        _AIRLINE + " AND c.runway_crossings > 0", "c.runway_crossings",
        _counted("c.runway_crossings", "runway crossing",
                 "runway crossings")),
    "De-icing": (
        _AIRLINE + " AND c.deicings > 0", "c.deicings",
        _counted("c.deicings", "stop on a de-icing pad",
                 "stops on a de-icing pad")),
    "Stepped descent": (
        _AIRLINE + " AND c.descent_level_offs > 1", "c.descent_level_offs",
        "c.descent_level_offs || ' level-offs in the descent'"),
    "Many airspace crossings": (
        _AIRLINE + " AND c.fir_crossings > 0", "c.fir_crossings",
        _counted("c.fir_crossings", "airspace crossing",
                 "airspace crossings")),
    "Long haul": (
        _AIRLINE, "date_diff('minute', f.atot, f.aldt)",
        "round(date_diff('minute', f.atot, f.aldt) / 60.0, 1) "
        "|| ' h in the air'"),
    "Training circuits": (
        "f.adep IS NOT NULL AND f.adep = f.ades "
        "AND c.holdings + c.go_arounds > 0",
        "c.holdings + c.go_arounds",
        "c.holdings || ' holdings or orbits, ' || c.go_arounds "
        "|| ' go-arounds'"),
}

#: Flights longer than this get no track, so they are not offered.
MAX_FLIGHT_HOURS = 20

_FLIGHT_COLUMNS = ("f.flight_id, trim(f.flt_id) AS flt_id, f.icao24, f.adep, "
                   "f.ades, f.first_seen, f.last_seen, f.typecode, "
                   "f.icao_operator")


def showcase(day, category: str, n: int = 5) -> Result:
    """The *n* flights of *category* most worth opening."""
    if category not in _SHOWCASE_SQL:
        raise ValueError(f"unknown showcase category {category!r}; "
                         f"expected one of {list(SHOWCASE)}")
    keep, score, why = _SHOWCASE_SQL[category]

    def n_of(*types: str) -> str:
        listed = ", ".join(f"'{t}'" for t in types)
        return f"count(*) FILTER (WHERE type IN ({listed}))"

    return run(f"""
        WITH c AS (
            SELECT flight_id, count(*) AS events,
                   {n_of('holding-end')} AS holdings,
                   coalesce(sum(holding_circuits)
                            FILTER (WHERE type = 'holding-end'), 0) AS circuits,
                   {n_of('go-around')} AS go_arounds,
                   {n_of('pms-leg-exit')} AS pms_legs,
                   {n_of('pms-merge-point')} AS merge_points,
                   {n_of('runway-crossing-entry')} AS runway_crossings,
                   {n_of('entry-deicing_pad')} AS deicings,
                   {n_of('level-off-descent-end')} AS descent_level_offs,
                   {n_of('xing-fir')} AS fir_crossings,
                   {n_of('AOBT')} AS off_blocks,
                   {n_of('AIBT')} AS in_blocks,
                   count(*) FILTER (WHERE type LIKE 'entry-%'
                                    OR type IN ('AOBT', 'AIBT', 'line-up',
                                                'take-off-roll',
                                                'runway-vacated')) AS surface
            FROM {{flight_events}}
            GROUP BY flight_id
        )
        SELECT {_FLIGHT_COLUMNS}, c.events,
               {score} AS score, {why} AS why
        FROM {{flight_list}} f
        JOIN c USING (flight_id)
        WHERE {keep}
          AND date_diff('minute', f.first_seen, f.last_seen)
              < {{max_hours}} * 60
        ORDER BY score DESC, c.events DESC, f.flight_id
        LIMIT {{n}}
        """, day, n=n, max_hours=MAX_FLIGHT_HOURS)


# -- a sample of each table, to look at -------------------------------------

#: The measurement columns of the events table: what was measured at the
#: event, beside where and when it happened.
MEASUREMENT_COLUMNS = (
    "distance_flown_nm", "time_passed_s", "holding_duration_s",
    "holding_distance_nm", "holding_circuits", "pms_leg_time_s",
    "pms_leg_distance_nm", "pms_direct_to_distance_nm")

#: The event's own columns, before the flight columns repeated on each row.
EVENT_COLUMNS = ("event_id", "flight_id", "type", "event_time", "longitude",
                 "latitude", "altitude_ft", "source", "version", "info")


def sample_flight_list(day, n: int = 500) -> Result:
    """A random sample of flight-list rows, all columns."""
    return run("""
        SELECT *
        FROM {flight_list}
        USING SAMPLE reservoir({n} ROWS) REPEATABLE (7)
        """, day, n=n)


def sample_events(day, n: int = 500, type_: Optional[str] = None,
                  measured: bool = False) -> Result:
    """A random sample of event rows with their measurement columns.

    `type_` keeps one event type. `measured` keeps the rows that carry a
    holding or point-merge measurement, which are too rare (under one row in
    a thousand) to turn up in a plain sample.
    """
    columns = ", ".join(EVENT_COLUMNS + MEASUREMENT_COLUMNS)
    conditions, params = ["TRUE"], {}
    if type_:
        conditions.append("type = {type}")
        params["type"] = type_
    if measured:
        conditions.append("(holding_duration_s IS NOT NULL "
                          "OR pms_leg_time_s IS NOT NULL)")
    return run(f"""
        SELECT *
        FROM (
            SELECT {columns}
            FROM {{flight_events}}
            WHERE {' AND '.join(conditions)}
        )
        USING SAMPLE reservoir({{n}} ROWS) REPEATABLE (7)
        """, day, n=n, **params)


def search_flights(day, callsign: Optional[str] = None,
                   icao24: Optional[str] = None, n: int = 50) -> Result:
    """Flights whose callsign or address starts with the given text."""
    conditions, params = ["TRUE"], {}
    if callsign:
        conditions.append("upper(trim(f.flt_id)) LIKE upper({callsign}) || '%'")
        params["callsign"] = callsign.strip()
    if icao24:
        conditions.append("lower(f.icao24) LIKE lower({icao24}) || '%'")
        params["icao24"] = icao24.strip()
    return run(f"""
        SELECT {_FLIGHT_COLUMNS}
        FROM {{flight_list}} f
        WHERE {' AND '.join(conditions)}
        ORDER BY flt_id, f.first_seen
        LIMIT {{n}}
        """, day, n=n, **params)


def flight(day, flight_id: str) -> Result:
    """The flight-list row of one flight."""
    return run("""
        SELECT *
        FROM {flight_list}
        WHERE flight_id = {flight_id}
        """, day, flight_id=flight_id)


def flight_events(day, flight_id: str) -> Result:
    """Every event of one flight, in the order they happened."""
    return run("""
        SELECT event_id, type, event_time, latitude AS lat, longitude AS lon,
               altitude_ft, version, info, distance_flown_nm, time_passed_s,
               holding_duration_s, holding_distance_nm, holding_circuits,
               pms_leg_time_s, pms_leg_distance_nm, pms_direct_to_distance_nm
        FROM {flight_events}
        WHERE flight_id = {flight_id}
        ORDER BY event_time, event_id
        """, day, flight_id=flight_id)


# ===========================================================================
# 4 -- across flights
# ===========================================================================

def holdings_by_destination_hour(day, n: int = 15) -> Result:
    """Holding, by destination and hour, for the airports with the most."""
    return run(f"""
        WITH h AS (
            SELECT ades AS airport, hour(event_time) AS hour,
                   holding_duration_s AS seconds
            FROM {{flight_events}}
            WHERE type = 'holding-end' AND ades IS NOT NULL
              AND {J('context')} = 'arrival'
        ), top AS (
            SELECT airport FROM h GROUP BY airport
            ORDER BY count(*) DESC, airport LIMIT {{n}}
        )
        SELECT airport, hour, count(*) AS holdings,
               sum(seconds) / 60.0 AS minutes
        FROM h SEMI JOIN top USING (airport)
        GROUP BY airport, hour
        ORDER BY airport, hour
        """, day, n=n)


def level_share_in_descent(day, n: int = 25) -> Result:
    """Level flight during the descent, per arrival, by destination."""
    return run(f"""
        WITH arrived AS (
            SELECT flight_id, ades AS airport
            FROM {{flight_list}}
            WHERE movement_arr AND ades IS NOT NULL AND ades <> 'OOA'
        ), lo AS (
            -- level time of the flights that count as arrivals, so the
            -- minutes and the arrivals they are divided by are the same
            -- flights
            SELECT a.airport, e.flight_id,
                   sum(TRY_CAST({J('duration_s')} AS DOUBLE)) AS level_s
            FROM {{flight_events}} e
            JOIN arrived a USING (flight_id)
            WHERE e.type = 'level-off-descent-end'
            GROUP BY a.airport, e.flight_id
        ), arrivals AS (
            SELECT airport, count(*) AS arrivals
            FROM arrived
            GROUP BY airport
        )
        SELECT a.airport, a.arrivals,
               count(lo.flight_id) AS with_level_off,
               coalesce(sum(lo.level_s), 0) / 60.0 / a.arrivals
                   AS level_min_per_arrival
        FROM arrivals a
        LEFT JOIN lo USING (airport)
        GROUP BY a.airport, a.arrivals
        ORDER BY a.arrivals DESC, a.airport
        LIMIT {{n}}
        """, day, n=n)
