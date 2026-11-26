# OPDI Explorer

A guided tour of the data published by the
Open Performance Data Initiative (OPDI): the **flight
list** and the **flight events** table. It is a Streamlit app for someone who
has just found the files and wants to know what is in them.

Five steps, read in order:

1. **Start** — the two tables, how they join, the day in numbers.
2. **Flight list** — what a row is, the 46 columns in groups with a real
   example, a sample of the table, and what the table answers by itself
   (airports, routes, hours, aircraft).
3. **Flight events** — pick a family, then an event type: what it means, what
   its `info` fields hold, a real row, where and when it happens, one chart of
   its family, and a sample of the table with its measurement columns.
4. **One flight** — a showcase flight (holding pattern, go-around, point merge,
   gate to gate, runway crossing, de-icing, stepped descent, …) or any flight
   by search, drawn on its track with its events on it.
5. **Across flights** — questions one day of events answers: holdings,
   go-arounds, taxi-out, point merge, runway use, level flight in the descent,
   airspace boundaries.

Every chart has a **Show the query** under it: the SQL that produced it,
written against the file names of a downloaded copy, so you can run it
yourself in DuckDB.

## How it works

The app reads the published parquet files directly with
[DuckDB](https://duckdb.org). There is no database, no build step and nothing
is written anywhere. It reads one day at a time:

```
<release>/published/catalogue.parquet                      which days exist
<release>/published/flight_list/flight_list_YYYYMMDD.parquet
<release>/published/flight_events/flight_events_YYYYMMDD.parquet
<release>/oa_airports/*.parquet                            names and positions (optional)
```

A release without the airports table still works; the airport and route maps
say why they are empty.

## Run it

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt

export OPDI_EXPLORER_RELEASE=s3://<bucket>/<path>/<release>   # the folder holding published/
export OPDI_S3_ENDPOINT=https://<your-s3-endpoint>            # omit for AWS itself
export AWS_ACCESS_KEY_ID=<key id>
export AWS_SECRET_ACCESS_KEY=<secret>

.venv/bin/streamlit run streamlit_app.py
```

A release on local disk needs only `OPDI_EXPLORER_RELEASE=/path/to/release`.

## Settings

All settings are environment variables.

| Variable | What it does |
|---|---|
| `OPDI_EXPLORER_RELEASE` | The release folder — the one that holds `published/`. An `s3://` address or a local path. **Required.** |
| `OPDI_S3_ENDPOINT` | The S3 endpoint the release is on. Omit for AWS itself. |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | The key that can read the release. |
| `OPDI_EXPLORER_FROM_DAY` | Optional, `YYYY-MM-DD`. Days before this one are left out everywhere: the day picker, the per-day chart, and every example. |
| `OPDI_TRACKS` | Optional. Where flight tracks are read from: a folder of raw state vectors, one sub-folder per hour named `hour=<unix hour>`. Without it, step 4 draws a flight from its events alone. |
| `OPDI_TRACKS_ENDPOINT` | The endpoint the tracks are on. Defaults to `OPDI_S3_ENDPOINT`. |
| `OPDI_TRACKS_KEY_ID`, `OPDI_TRACKS_SECRET` | The key for the tracks, when it is not the release's key. |
| `OPDI_EXPLORER_ENV_FILE` | Optional. A file of `NAME = value` lines holding any of the above, for a machine where the keys already live in a file. Keep that file outside the repository. |
| `OPDI_EXPLORER_MEMORY` | DuckDB's memory limit. Default `2GB`; lower it on a small host. |

### Tracks

Step 4 can draw a flight on the position reports it was built from. Those are
raw state vectors: one row a second per aircraft, not cleaned and not split
into flights. The app reads the hours between the flight's first and last
report for that one aircraft and thins them to at most 4,000 points for
drawing. Expect a couple of seconds per hour of flight the first time a flight
is opened; it is remembered after that. Flights longer than 20 hours get no
track. If the track cannot be read, the flight is drawn from its events alone
and the page says why.

## Keys and secrets

**No key belongs in this repository.** The code holds none and reads them only
from the environment, from the hosting platform's secrets, or from a file you
name with `OPDI_EXPLORER_ENV_FILE`.

- `.gitignore` excludes `.env`, `*.env`, `env`, and `.streamlit/secrets.toml`.
  Do not force-add them.
- `.streamlit/secrets.toml.example` shows the names to set. Copy it to
  `.streamlit/secrets.toml` for local use; that copy is ignored by git.
- A hosted app gives everyone who can open it read access to the release
  through the key you configured. Use a key that can read only what the app
  should show, and decide who may open the app before you deploy it.

## Hosting it

On a platform that runs Streamlit apps from a repository, point it at
`streamlit_app.py` and enter the settings above as the platform's secrets
(top-level names, as in `.streamlit/secrets.toml.example`). The app copies
them into its environment when it starts. Set `OPDI_EXPLORER_MEMORY` to fit
the host.

## Tests

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

The tests build a small release and a slice of state vectors on local disk.
They need no network and no key.

## Where the wording comes from

The description of every event type and every flight-list column is copied
from the OPDI data dictionary (`src/opdi_explorer/catalogue.py` and
`_columns.py` name the source). An event type that is in the data but not yet
in the dictionary is still selectable, under "Not described yet".
