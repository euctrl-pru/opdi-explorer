"""OPDI Explorer: a guided tour of the published flight list and flight events.

Run with `streamlit run streamlit_app.py`. See README.md for the settings.
"""

import sys
from pathlib import Path

# The package lives under `src/`. Put it on the path so the app runs from a
# plain checkout, without an install step.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import os  # noqa: E402

import streamlit as st  # noqa: E402


def _secrets_to_environment() -> None:
    """Make the hosting platform's secrets visible as environment variables.

    The settings are read from the environment (see `opdi_explorer/config.py`).
    On a host that keeps them as Streamlit secrets, copy the plain text ones
    across before the settings are read. A value already in the environment
    wins, and with no secrets at all there is nothing to do.
    """
    try:
        for name, value in st.secrets.items():
            if isinstance(value, str) and name not in os.environ:
                os.environ[name] = value
    except Exception:  # noqa: BLE001 -- no secrets file: environment only
        pass


_secrets_to_environment()

from opdi_explorer import config, style, ui  # noqa: E402
from opdi_explorer.steps import (  # noqa: E402
    across, events, flight, flight_list, start,
)

st.set_page_config(page_title="OPDI Explorer", page_icon="🧭", layout="wide",
                   initial_sidebar_state="collapsed")

if not config.RELEASE:
    st.markdown(style.page_css(), unsafe_allow_html=True)
    st.title("OPDI Explorer")
    st.info(
        "Explorer reads a release's published files directly, and no release "
        "is set. Set `OPDI_EXPLORER_RELEASE` to the release folder — the one "
        "that holds `published/` — and, for a release on S3, the endpoint and "
        "a key:\n\n"
        "```\n"
        "OPDI_EXPLORER_RELEASE=s3://<bucket>/<path>/<release>\n"
        "OPDI_S3_ENDPOINT=https://<your-s3-endpoint>\n"
        "AWS_ACCESS_KEY_ID=<key id>\n"
        "AWS_SECRET_ACCESS_KEY=<secret>\n"
        "```\n\n"
        "Give them as environment variables, or as secrets on the platform "
        "that hosts the app. See the README for the rest.")
    st.stop()

_RENDER = {"start": start.render, "flight_list": flight_list.render,
           "events": events.render, "flight": flight.render,
           "across": across.render}

pages = []
for number, (key, title, _) in enumerate(ui.STEPS, start=1):
    page = st.Page(_RENDER[key], title=f"{number} {title}", url_path=key,
                   default=(key == "start"))
    ui.PAGES[key] = page
    pages.append(page)

st.navigation(pages, position="top").run()
