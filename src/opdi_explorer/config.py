"""Settings, all read from the environment. Nothing here has a secret in it.

Explorer needs to be told where the release is and how to read it:

==========================  =================================================
``OPDI_EXPLORER_RELEASE``   The release folder, e.g. ``s3://bucket/opdi/v2.0.0``
                            or a local folder. Explorer reads
                            ``<release>/published/``. Required.
``OPDI_S3_ENDPOINT``        The S3 endpoint the release is on, when it is not
                            AWS itself.
``AWS_ACCESS_KEY_ID``,      The key for the release.
``AWS_SECRET_ACCESS_KEY``
``OPDI_EXPLORER_FROM_DAY``  Optional ``YYYY-MM-DD``: leave out earlier days.
``OPDI_TRACKS``             Optional: where flight tracks are read from (a
                            folder of ``hour=<unix hour>/`` state vectors).
``OPDI_TRACKS_ENDPOINT``    The endpoint the tracks are on; defaults to
                            ``OPDI_S3_ENDPOINT``.
``OPDI_TRACKS_KEY_ID``,     The key for the tracks, when it is not the
``OPDI_TRACKS_SECRET``      release's.
``OPDI_EXPLORER_ENV_FILE``  Optional: a file of ``NAME = value`` lines holding
                            any of the above, for running on a machine where
                            the keys already live in a file.
``OPDI_EXPLORER_MEMORY``    DuckDB's memory limit; default ``2GB``.
==========================  =================================================

Keys are only ever read from the environment or from a file outside the
repository. Never write one into this file, into the code, or into a commit.
"""

import datetime as dt
import os
from typing import Optional


def parse_env_file(path) -> dict:
    """`NAME = value` lines from *path*, as a dict.

    Parsed, never executed. Spaces around the `=` and around the value are
    dropped: a secret with a leading space is a secret the store rejects with
    a message about the key not existing, not about the space. Comments and
    lines without `=` are skipped; a missing file is an empty dict.
    """
    out = {}
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except (OSError, TypeError):
        return out
    for line in lines:
        if line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip():
            out[key.strip()] = value.strip()
    return out


def day_from(value: Optional[str], name: str) -> Optional[dt.date]:
    """An ISO date from a setting, or ``None`` when it is unset."""
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value.strip())
    except ValueError:
        raise ValueError(
            f"{name} must be a date written YYYY-MM-DD, not {value!r}")


#: A file of settings that takes precedence over the process environment.
#: Applied before anything below reads the environment.
ENV_FILE = os.environ.get("OPDI_EXPLORER_ENV_FILE")
if ENV_FILE:
    os.environ.update(parse_env_file(ENV_FILE))

#: The release folder explorer reads. Unset, the app opens on a page that
#: says what to set.
RELEASE = os.environ.get("OPDI_EXPLORER_RELEASE") or None

#: The S3 endpoint the release is on. Unset means AWS's own.
S3_ENDPOINT = os.environ.get("OPDI_S3_ENDPOINT") or None

#: The first published day shown.
#:
#: A release's `published/` folder can hold days from several runs -- an early
#: sample day beside the days that matter. Set, days before this one are left
#: out everywhere: the day picker, the per-day chart, and so every example,
#: which is always drawn from a listed day.
FROM_DAY = day_from(os.environ.get("OPDI_EXPLORER_FROM_DAY"),
                    "OPDI_EXPLORER_FROM_DAY")

#: Where a single flight's track is read from: raw state vectors, one folder
#: per hour (`hour=<unix hour>/`). Unset, flights are drawn from their events
#: alone.
TRACKS = os.environ.get("OPDI_TRACKS") or None

#: The endpoint the tracks are on. Not necessarily `S3_ENDPOINT`: the release
#: and the state vectors may be on different stores.
TRACKS_ENDPOINT = os.environ.get("OPDI_TRACKS_ENDPOINT") or S3_ENDPOINT

#: An optional key file for the track store, for when its key differs from
#: the release's and lives in a file. `OPDI_TRACKS_KEY_ID` and
#: `OPDI_TRACKS_SECRET` in the environment do the same without a file.
TRACKS_ENV_FILE = os.environ.get("OPDI_TRACKS_ENV_FILE") or None

#: DuckDB's memory limit and thread count. Lower the limit on a small host:
#: an unbounded DuckDB takes what is left and the host kills the app.
MEMORY_LIMIT = os.environ.get("OPDI_EXPLORER_MEMORY", "2GB")
THREADS = int(os.environ.get("OPDI_EXPLORER_THREADS", "4"))


def track_keys() -> dict:
    """`{"id": ..., "secret": ...}` for the track store, or `{}`.

    From `OPDI_TRACKS_KEY_ID` / `OPDI_TRACKS_SECRET`, else from the key file
    named by `OPDI_TRACKS_ENV_FILE`. Empty when neither is set, in which case
    the tracks are read with the release's own key.
    """
    key_id = os.environ.get("OPDI_TRACKS_KEY_ID")
    secret = os.environ.get("OPDI_TRACKS_SECRET")
    if key_id and secret:
        return {"id": key_id, "secret": secret}
    if TRACKS_ENV_FILE:
        keys = parse_env_file(TRACKS_ENV_FILE)
        if keys.get("AWS_ACCESS_KEY_ID"):
            return {"id": keys["AWS_ACCESS_KEY_ID"],
                    "secret": keys.get("AWS_SECRET_ACCESS_KEY", "")}
    return {}
