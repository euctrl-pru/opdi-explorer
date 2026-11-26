"""The five steps run, top to bottom, against a local release."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from opdi_explorer import config

EXPLORER = Path(__file__).resolve().parents[1] / "streamlit_app.py"
STEPS = ["start", "flight_list", "events", "flight", "across"]


def run_step(step: str) -> AppTest:
    at = AppTest.from_string(
        f"from opdi_explorer.steps import {step}\n"
        f"{step}.render()\n", default_timeout=120)
    return at.run()


def all_text(at: AppTest) -> str:
    parts = []
    for kind in ("markdown", "caption", "info", "warning", "header",
                 "subheader", "title"):
        parts += [str(e.value) for e in at.get(kind)]
    for df in at.dataframe:
        parts.append(df.value.to_string())
    return "\n".join(parts)


def pick(at: AppTest, label: str, value) -> AppTest:
    box = [s for s in at.selectbox if s.label == label][0]
    return box.set_value(value).run()


@pytest.mark.parametrize("step", STEPS)
def test_every_step_opens(explorer_release, state_vectors, step):
    at = run_step(step)
    assert not at.exception, [e.value for e in at.exception]


def test_the_entry_script_opens_on_the_first_step(explorer_release,
                                                  state_vectors):
    at = AppTest.from_file(str(EXPLORER), default_timeout=120).run()
    assert not at.exception, [e.value for e in at.exception]
    assert "Step 1 of 5" in all_text(at)


def test_without_a_release_explorer_says_what_to_set(monkeypatch):
    monkeypatch.setattr(config, "RELEASE", None)
    at = AppTest.from_file(str(EXPLORER), default_timeout=60).run()
    assert not at.exception
    assert any("OPDI_EXPLORER_RELEASE" in m.value for m in at.info)


def test_a_release_that_cannot_be_read_is_explained(tmp_path, monkeypatch):
    from opdi_explorer import release

    monkeypatch.setattr(config, "RELEASE", str(tmp_path / "nothing"))
    monkeypatch.setitem(release._catalogue, "key", None)
    at = run_step("start")
    assert not at.exception
    assert any("No published days" in w.value for w in at.warning)


def test_the_start_shows_the_day_in_numbers_and_one_flight(explorer_release):
    text = all_text(run_step("start"))
    assert "28 April 2026 in numbers" in text
    assert "One row is one flight" in text
    # The example flight's first events come with their meaning.
    assert "The first position report of the track." in text


def test_the_flight_list_step_explains_every_column_group(explorer_release):
    at = run_step("flight_list")
    text = all_text(at)
    assert "Unique identifier of the flight." in text
    assert "London Heathrow Airport" in text
    assert [t.label for t in at.tabs][:2] == [
        "Identity", "Route and how the airports were found"]


def test_every_chart_offers_its_query(explorer_release):
    at = run_step("flight_list")
    assert sum(e.label == "Show the query" for e in at.expander) >= 6
    assert any("flight_list/flight_list_20260428.parquet" in c.value
               for c in at.code)


def test_a_release_without_airports_still_renders_the_flight_list_step(
        explorer_release_no_airports):
    at = run_step("flight_list")
    assert not at.exception
    assert "no table of airport positions" in all_text(at)


def test_choosing_an_event_type_explains_it(explorer_release):
    at = run_step("events")
    at = pick(at, "Family", "Holding")
    at = pick(at, "Event type", "holding-end")
    assert not at.exception, [e.value for e in at.exception]
    text = all_text(at)
    assert "Last turning sample of the pattern" in text
    assert "Number of loops" in text              # the meaning of `circuits`
    assert "racetrack" in text                    # ...and its real value


def test_every_family_present_can_be_opened(explorer_release):
    from opdi_explorer import catalogue

    at = run_step("events")
    for family in catalogue.FAMILIES:
        at = pick(at, "Family", family)
        assert not at.exception, (family, [e.value for e in at.exception])


def test_a_family_with_no_events_on_the_day_says_so(
        explorer_release_no_point_merge):
    at = pick(run_step("events"), "Family", "Point merge")
    assert not at.exception
    assert any("No event of this family" in i.value for i in at.info)


def test_a_type_missing_from_the_catalogue_is_shown_not_broken(
        explorer_release):
    at = pick(run_step("events"), "Family", "Not described yet")
    assert not at.exception, [e.value for e in at.exception]
    text = all_text(at)
    assert "xing-tma" in text
    assert "not yet in the data dictionary" in text
    assert "LONDON" in text                       # its raw field still shown


def test_a_showcase_flight_draws_its_track_with_its_events(explorer_release,
                                                           state_vectors):
    at = run_step("flight")       # first category, first flight: H1
    assert not at.exception, [e.value for e in at.exception]
    assert len(at.get("plotly_chart")) >= 4       # map, profile, timeline, close-up
    text = all_text(at)
    assert "DLH900" in text and "Close-ups" in text
    assert "racetrack, 2.0 circuits, 10 minutes" in text
    assert not any("events alone" in i.value for i in at.info)


def test_every_showcase_category_opens(explorer_release, state_vectors):
    from opdi_explorer import data

    at = run_step("flight")
    for category in data.SHOWCASE:
        at = pick(at, "Flights with a…", category)
        assert not at.exception, (category, [e.value for e in at.exception])


def test_a_flight_across_midnight_gets_its_track(explorer_release,
                                                 state_vectors):
    at = pick(run_step("flight"), "Flights with a…", "Long haul")
    assert not at.exception
    assert "BAW117" in all_text(at)
    assert not any("events alone" in i.value for i in at.info)


def test_an_unreadable_track_falls_back_to_the_events(explorer_release,
                                                      monkeypatch):
    monkeypatch.setattr(config, "TRACKS", None)
    at = run_step("flight")
    assert not at.exception, [e.value for e in at.exception]
    assert any("not configured" in i.value and "events alone" in i.value
               for i in at.info)
    assert len(at.get("plotly_chart")) >= 3


def test_search_finds_a_flight_by_call_sign(explorer_release, state_vectors):
    at = run_step("flight")
    at = [r for r in at.radio if r.label == "Find a flight"][0].set_value(
        "Search").run()
    assert any("Type the start" in i.value for i in at.info)
    at = at.text_input[0].set_value("afr").run()
    assert not at.exception
    assert "AFR100" in all_text(at)


def test_a_day_with_no_point_merge_says_so(explorer_release_no_point_merge):
    at = run_step("across")
    assert not at.exception
    assert any("No point-merge leg" in i.value for i in at.info)


def test_the_across_step_answers_with_numbers(explorer_release):
    text = all_text(run_step("across"))
    assert "Where do aircraft hold before landing" in text
    # One holding before landing (H1 into Heathrow); the training flight's
    # two holds are not before a landing and are not counted here.
    assert "1 holding before landing" in text
