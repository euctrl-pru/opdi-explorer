"""Where a release keeps its published files, and which days it holds.

A release publishes two files per day -- `flight_list_YYYYMMDD.parquet` and
`flight_events_YYYYMMDD.parquet` -- and a `catalogue.parquet` listing the
days. Both day files are sorted by flight, so DuckDB can look a flight up in
them without reading the whole day.
"""

import datetime as dt
import time
from typing import List

import pandas as pd

from opdi_explorer import config

#: How long a read of the catalogue is reused. Streamlit reruns a page on
#: every widget change and each rerun asks which days exist.
_CATALOGUE_TTL_S = 60.0
_catalogue = {"at": 0.0, "key": None, "frame": None}


def base() -> str:
    """The release's `published/` folder, in the scheme DuckDB speaks."""
    return config.RELEASE.rstrip("/").replace("s3a://", "s3://") + "/published"


def day_file(kind: str, day: dt.date) -> str:
    return f"{base()}/{kind}/{kind}_{day:%Y%m%d}.parquet"


def catalogue() -> pd.DataFrame:
    """One row per published day, or an empty frame if it cannot be read.

    Unreadable is reported as "no days", not raised: the app has to be able
    to open and say so.
    """
    from opdi_explorer import read

    now = time.time()
    key = (base(), config.FROM_DAY)
    if (_catalogue["key"] == key
            and now - _catalogue["at"] < _CATALOGUE_TTL_S):
        return _catalogue["frame"]
    try:
        frame = read.query(
            f"SELECT * FROM read_parquet('{base()}/catalogue.parquet') "
            "ORDER BY day")
    except Exception:  # noqa: BLE001
        frame = pd.DataFrame(columns=["day", "flights", "events"])
    frame["day"] = [d.date() if hasattr(d, "date") else d
                    for d in frame["day"]]
    if config.FROM_DAY is not None:
        # Left out here, at the one place every list of days comes from, so
        # no page can offer -- or take an example from -- an earlier day.
        frame = frame[[d >= config.FROM_DAY for d in frame["day"]]
                      ].reset_index(drop=True)
    _catalogue.update(at=now, key=key, frame=frame)
    return frame


def days() -> List[dt.date]:
    return list(catalogue()["day"])
