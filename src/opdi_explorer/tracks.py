"""One flight's track, from OpenSky's raw state vectors.

The published files hold a flight's events, not the path between them. The
path is in OpenSky's state-vector store: one folder per hour
(`hour=<unix hour>/`), every aircraft in the world in it, one row a second.
Reading one aircraft out of one hour is quick, so a flight's track is fetched
when the flight is opened -- the hours from first seen to last seen, that
aircraft only.

These are the **raw** samples: not thinned to five seconds, not cleaned, not
split into tracks. They are what the pipeline started from, drawn so the
events can be seen against the flight that produced them.
"""

import calendar
import datetime as dt
import math
from typing import Callable, List, Optional

import pandas as pd

from opdi_explorer import config, read
from opdi_explorer.units import M_TO_FT, MS_TO_FT_MIN, MS_TO_KT

#: A flight longer than this gets no track. Each hour is a separate read of
#: an ~850 MB file, about two seconds; past twenty the wait stops being worth
#: the picture, and a "flight" that long is usually a track that never closed.
MAX_HOURS = 20

#: How many points a drawn track keeps. A long-haul at one sample a second is
#: tens of thousands of points, which a browser map draws slowly and no eye
#: can tell from four thousand.
MAX_POINTS = 4000

COLUMNS = ["event_time", "lat", "lon", "altitude_ft", "speed_kt",
           "roc_ft_min", "on_ground"]


class TrackUnavailable(Exception):
    """The track could not be read. `str()` is a line for the user."""


def _unix(when) -> float:
    """Seconds since the epoch for a UTC time given without a zone."""
    ts = pd.Timestamp(when)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return calendar.timegm(ts.timetuple()) + ts.microsecond / 1e6


def hours(first_seen, last_seen) -> List[int]:
    """The unix hours a window touches, both ends included."""
    start = int(_unix(first_seen)) // 3600 * 3600
    end = int(_unix(last_seen)) // 3600 * 3600
    return list(range(start, end + 1, 3600))


def _hour_source(hour: int) -> str:
    return f"{config.TRACKS.rstrip('/')}/hour={hour}/*.parquet"


def fetch(icao24: str, first_seen, last_seen,
          progress: Optional[Callable[[int, int], None]] = None
          ) -> pd.DataFrame:
    """The samples of *icao24* between the two times, in aviation units.

    All the hours are read in one query first: DuckDB then works on several
    hour files at once, which is what makes a long flight bearable. That
    query fails as a whole if a single hour's folder is missing, so on
    failure the hours are read one by one and the missing ones skipped --
    slower, and `progress(done, total)` says how far it has got.
    """
    if not config.TRACKS:
        raise TrackUnavailable(
            "The track store is not configured (OPDI_TRACKS is empty), so "
            "there is no track to draw.")
    lo, hi = math.floor(_unix(first_seen)), math.ceil(_unix(last_seen))
    if hi - lo > MAX_HOURS * 3600:
        raise TrackUnavailable(
            f"This flight lasts {(hi - lo) / 3600:.0f} hours. Tracks are read "
            f"for flights of up to {MAX_HOURS} hours.")
    address = str(icao24).strip().lower().replace("'", "")
    wanted = hours(first_seen, last_seen)

    def read_hours(some: List[int]) -> pd.DataFrame:
        sources = ", ".join(f"'{_hour_source(h)}'" for h in some)
        return read.query(f"""
            SELECT time, lat, lon, baroAltitude, velocity, vertRate, onGround
            FROM read_parquet([{sources}])
            WHERE icao24 = '{address}'
              AND time BETWEEN {lo} AND {hi}
            """)

    frames, unreadable = [], 0
    try:
        frames.append(read_hours(wanted))
        if progress is not None:
            progress(len(wanted), len(wanted))
    except Exception:  # noqa: BLE001
        for i, hour in enumerate(wanted, start=1):
            try:
                frames.append(read_hours([hour]))
            except Exception:  # noqa: BLE001
                # No folder for that hour, or it could not be read: a gap in
                # the store, not a reason to draw nothing.
                unreadable += 1
            if progress is not None:
                progress(i, len(wanted))
    if unreadable == len(wanted):
        raise TrackUnavailable(
            "There are no state vectors to read for the hours of this flight "
            "(the store has no folder for them, or it could not be reached).")
    raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not raw.empty:
        # Rows without a position are dropped here, not in the query. Adding
        # `lat IS NOT NULL AND lon IS NOT NULL` to the WHERE made one hour
        # take 7 s or more instead of under one: the aircraft filter is what
        # lets DuckDB skip most of an 850 MB file, and the extra conditions
        # got in its way.
        raw = raw.dropna(subset=["lat", "lon"])
    if raw.empty:
        raise TrackUnavailable(
            "There are no state vectors for this aircraft in the hours of "
            "this flight.")
    raw = raw.sort_values("time").drop_duplicates("time")
    return pd.DataFrame({
        "event_time": pd.to_datetime(raw["time"], unit="s"),
        "lat": raw["lat"].astype(float),
        "lon": raw["lon"].astype(float),
        "altitude_ft": raw["baroAltitude"].astype(float) * M_TO_FT,
        "speed_kt": raw["velocity"].astype(float) * MS_TO_KT,
        "roc_ft_min": raw["vertRate"].astype(float) * MS_TO_FT_MIN,
        "on_ground": raw["onGround"].astype("boolean"),
    }, columns=COLUMNS).reset_index(drop=True)


def thin(frame: pd.DataFrame, max_points: int = MAX_POINTS) -> pd.DataFrame:
    """Every k-th row, always keeping the first and the last."""
    if len(frame) <= max_points:
        return frame
    step = math.ceil(len(frame) / max_points)
    kept = frame.iloc[::step]
    if kept.index[-1] != frame.index[-1]:
        kept = pd.concat([kept, frame.iloc[[-1]]])
    return kept
