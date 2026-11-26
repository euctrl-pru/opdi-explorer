"""The pieces every step is built from.

One place for the things that make explorer read the same on every step: the
numbered header with the day picker, the figure with its query underneath,
the row of big numbers, Back and Next.
"""

import datetime as dt
from typing import Dict, List, Optional

import streamlit as st

from opdi_explorer import config, release
from opdi_explorer import data, style

#: The steps, in order: (key, title, one line on what it holds).
#: `streamlit_app.py` registers a page for each key in `PAGES`, which is how
#: Back/Next find them.
STEPS = [
    ("start", "Start", "The two tables and the day in numbers"),
    ("flight_list", "Flight list", "One row per flight"),
    ("events", "Flight events", "One row per event of a flight"),
    ("flight", "One flight", "A flight on its track, with its events"),
    ("across", "Across flights", "Questions a whole day can answer"),
]
PAGES: Dict[str, object] = {}

_DAY_KEY = "explorer_day"


def days() -> List[dt.date]:
    """Published days, newest first."""
    return sorted(release.days(), reverse=True)


@st.cache_data(ttl=3600, show_spinner=False)
def _ask(release_root: str, name: str, args: tuple, kwargs: tuple):
    return getattr(data, name)(*args, **dict(kwargs))


def ask(name: str, *args, **kwargs) -> data.Result:
    """`data.<name>(*args)`, remembered for the session.

    Keyed on the release as well as the arguments: the same day of another
    release is another answer.
    """
    return _ask(config.RELEASE, name, args, tuple(sorted(kwargs.items())))


def header(key: str, lead: str) -> Optional[dt.date]:
    """The step's number, title and lead, and the day picker.

    Returns the chosen day, or stops the page when the release lists none.
    """
    index = [k for k, _, _ in STEPS].index(key)
    title = STEPS[index][1]
    st.markdown(style.page_css(), unsafe_allow_html=True)
    published = days()
    left, right = st.columns([4, 1])
    with left:
        st.markdown(f"<div class='ex-step'>Step {index + 1} of {len(STEPS)}"
                    "</div>", unsafe_allow_html=True)
        st.title(title)
    if not published:
        st.warning(
            "No published days were found. The release's "
            "`published/catalogue.parquet` could not be read — check "
            "`OPDI_EXPLORER_RELEASE`, the endpoint and the key"
            + (", and `OPDI_EXPLORER_FROM_DAY`, which leaves out earlier days."
               if config.FROM_DAY else "."))
        st.stop()
    current = st.session_state.get(_DAY_KEY)
    with right:
        # The widget has its own key per step: Streamlit forgets a widget's
        # value when a page does not draw it, so the chosen day is kept in
        # session state and handed back to each step's picker.
        day = st.selectbox(
            "Day", published,
            index=published.index(current) if current in published else 0,
            key=f"day_{key}", format_func=lambda d: f"{d:%d %b %Y}",
            help="Everything on this step is computed from this one day's "
                 "files.")
    st.session_state[_DAY_KEY] = day
    st.markdown(f"<p class='ex-lead'>{lead}</p>", unsafe_allow_html=True)
    return day


def numbers(values: Dict[str, str]) -> None:
    """A row of big numbers with small labels."""
    boxes = "".join(
        f"<div class='ex-numbox'><div class='ex-num'>{value}</div>"
        f"<div class='ex-numlabel'>{label}</div></div>"
        for label, value in values.items())
    st.markdown(f"<div class='ex-nums'>{boxes}</div>", unsafe_allow_html=True)


def table(rows, headers, classes=None) -> None:
    """A small table whose text wraps.

    For tables that are read, not sorted: Streamlit's dataframe keeps every
    cell on one line and cuts a long description off mid-sentence, which is
    the wrong trade for a column of meanings.
    """
    import html

    classes = classes or [""] * len(headers)
    head = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(
            f"<td class='{c}'>{html.escape(str(cell))}</td>"
            for cell, c in zip(row, classes)) + "</tr>"
        for row in rows)
    st.markdown(f"<table class='ex-table'><thead><tr>{head}</tr></thead>"
                f"<tbody>{body}</tbody></table>", unsafe_allow_html=True)


def chart(fig, result: Optional[data.Result], key: str,
          note: Optional[str] = None) -> None:
    """A figure, an optional line on how to read it, and its query."""
    st.plotly_chart(fig, width="stretch", key=key)
    if note:
        st.caption(note)
    if result is not None:
        query(result)


def query(result: data.Result, label: str = "Show the query") -> None:
    """The SQL behind an answer, runnable against the downloaded files."""
    with st.expander(label):
        st.code(result.sql, language="sql")
        st.caption("Runs in DuckDB from the folder that holds the published "
                   "files.")


def question(text: str, answer: Optional[str] = None) -> None:
    st.markdown(f"<div class='ex-q'>{text}</div>", unsafe_allow_html=True)
    if answer:
        st.markdown(answer)


def tag(text: str, colour: str) -> str:
    return f"<span class='ex-tag' style='background:{colour}'>{text}</span>"


def back_next(key: str) -> None:
    """Back and Next at the foot of a step."""
    keys = [k for k, _, _ in STEPS]
    i = keys.index(key)
    st.divider()
    left, _, right = st.columns([2, 3, 2])
    if i > 0 and keys[i - 1] in PAGES:
        left.page_link(PAGES[keys[i - 1]],
                       label=f"← {i}. {STEPS[i - 1][1]}")
    if i + 1 < len(keys) and keys[i + 1] in PAGES:
        right.page_link(PAGES[keys[i + 1]],
                        label=f"{i + 2}. {STEPS[i + 1][1]} →")


def number(value, digits: int = 0) -> str:
    """A count as people write it."""
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return "–"
