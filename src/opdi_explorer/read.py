"""One DuckDB connection per process, and nothing that writes.

Explorer reads parquet files straight from where they are published. There is
no database, no cache on disk and no build step.
"""

import os
import threading
from typing import Optional

import pandas as pd

from opdi_explorer import config

_CON = None

#: One connection, one query at a time.
#:
#: Streamlit runs every rerun in its own thread, and a rerun starts while the
#: previous one may still be in a query. DuckDB's Python connection does not
#: support two `execute()` calls at once: the second resets the first's
#: result, which then surfaces as a `None` frame in an unrelated caller.
_LOCK = threading.RLock()


def _quoted(text) -> str:
    return "'" + str(text).replace("'", "''") + "'"


def _host(endpoint: str) -> str:
    return endpoint.replace("https://", "").replace("http://", "")


def _configure_s3(con) -> None:
    """Point the connection at the store the release is on."""
    con.execute("INSTALL httpfs; LOAD httpfs;")
    if config.S3_ENDPOINT:
        con.execute(f"SET s3_endpoint={_quoted(_host(config.S3_ENDPOINT))};")
        con.execute("SET s3_url_style='path';")
        con.execute("SET s3_use_ssl="
                    + ("false" if config.S3_ENDPOINT.startswith("http://")
                       else "true") + ";")
    if os.environ.get("AWS_ACCESS_KEY_ID"):
        con.execute("SET s3_access_key_id="
                    f"{_quoted(os.environ['AWS_ACCESS_KEY_ID'])};")
        con.execute("SET s3_secret_access_key="
                    f"{_quoted(os.environ.get('AWS_SECRET_ACCESS_KEY', ''))};")
    _configure_tracks(con)


def _configure_tracks(con) -> None:
    """A second store, for flight tracks.

    The release and the state vectors may be on different stores under
    different keys. The settings above are global, so the track store gets a
    *secret* scoped to its own bucket: DuckDB uses a secret whose scope
    matches the path before it falls back to the settings, and nothing else
    on the connection is affected.
    """
    tracks = config.TRACKS or ""
    if not tracks.startswith("s3://"):
        return      # unset, or a local folder: nothing to authenticate
    keys = config.track_keys()
    if not keys:
        return      # read with the release's own key
    # With the trailing slash. A scope is a prefix, so `s3://bucket` would
    # also claim `s3://bucket-other/...` and read it with the wrong key.
    bucket = "s3://" + tracks[len("s3://"):].split("/")[0] + "/"
    endpoint = (f"ENDPOINT {_quoted(_host(config.TRACKS_ENDPOINT))}, "
                "URL_STYLE 'path', " if config.TRACKS_ENDPOINT else "")
    con.execute(f"""
        CREATE OR REPLACE SECRET opdi_tracks (
            TYPE s3, KEY_ID {_quoted(keys['id'])},
            SECRET {_quoted(keys['secret'])},
            {endpoint}SCOPE '{bucket}')""")


def connect():
    """The process-wide DuckDB connection."""
    with _LOCK:
        return _connect_locked()


def _connect_locked():
    global _CON
    if _CON is None:
        import duckdb

        _CON = duckdb.connect(":memory:")
        # Bounded deliberately: an unbounded DuckDB takes whatever memory is
        # left while scanning a day of events, and a small host then kills
        # the app. Spilling is slower than dying is expensive.
        _CON.execute(f"SET memory_limit={_quoted(config.MEMORY_LIMIT)};")
        _CON.execute(f"SET threads={int(config.THREADS)};")
        try:
            _configure_s3(_CON)
        except Exception:  # noqa: BLE001
            # A local release needs no httpfs at all, and a missing extension
            # must not stop the app opening against one.
            pass
    return _CON


def query(sql: str, params: Optional[list] = None) -> pd.DataFrame:
    with _LOCK:
        result = _connect_locked().execute(sql, params or []).df()
    if result is None:
        # Should be unreachable while the lock holds. Raised so that if it
        # ever happens it names itself here, not in whichever caller
        # subscripts the result.
        raise RuntimeError(
            "DuckDB returned no result frame for a query that should produce "
            f"one. The query was: {sql.strip()[:200]}")
    return result
