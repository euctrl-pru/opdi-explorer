"""Showing only the days from a given date on."""

import datetime as dt

import pandas as pd
import pytest

from opdi_explorer import config, release
from opdi_explorer import data, ui

from .conftest import DAY
from .test_pages import all_text, run_step

EARLIER = dt.date(2026, 4, 3)


@pytest.fixture
def two_days(explorer_release):
    """The release of the other tests, with an earlier day beside it."""
    pub = explorer_release / "published"
    cat = pd.read_parquet(pub / "catalogue.parquet")
    older = cat.iloc[[0]].assign(day=EARLIER, flights=99)
    pd.concat([older, cat]).to_parquet(pub / "catalogue.parquet")
    for kind in ("flight_list", "flight_events"):
        frame = pd.read_parquet(pub / kind / f"{kind}_20260428.parquet")
        frame.assign(dof=EARLIER).to_parquet(
            pub / kind / f"{kind}_20260403.parquet")
    release._catalogue["key"] = None
    return explorer_release


def test_without_the_setting_every_day_is_listed(two_days):
    assert release.days() == [EARLIER, DAY]
    assert ui.days() == [DAY, EARLIER]


def test_days_before_the_cut_off_are_left_out_everywhere(two_days,
                                                         monkeypatch):
    monkeypatch.setattr(config, "FROM_DAY", dt.date(2026, 4, 28))
    assert release.days() == [DAY]
    assert ui.days() == [DAY]
    assert list(data.days_trend().frame["day"]) == [DAY]


def test_the_cut_off_day_itself_is_kept(two_days, monkeypatch):
    monkeypatch.setattr(config, "FROM_DAY", EARLIER)
    assert release.days() == [EARLIER, DAY]


def test_changing_the_cut_off_is_not_answered_from_memory(two_days,
                                                          monkeypatch):
    assert len(release.days()) == 2
    monkeypatch.setattr(config, "FROM_DAY", dt.date(2026, 4, 28))
    assert len(release.days()) == 1


def test_a_cut_off_after_every_day_is_explained_not_an_error(two_days,
                                                             monkeypatch):
    monkeypatch.setattr(config, "FROM_DAY", dt.date(2027, 1, 1))
    at = run_step("start")
    assert not at.exception
    assert any("No published days" in w.value for w in at.warning)


def test_the_start_says_which_days_are_shown(two_days, monkeypatch):
    monkeypatch.setattr(config, "FROM_DAY", dt.date(2026, 4, 28))
    at = run_step("start")
    assert not at.exception
    text = all_text(at)
    assert "1 day** shown, from 28 April 2026 on" in text
    assert "28 April 2026 in numbers" in text


def test_the_setting_is_a_date():
    assert config.day_from("2026-07-01", "X") == dt.date(2026, 7, 1)
    assert config.day_from("", "X") is None and config.day_from(None, "X") is None
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        config.day_from("July 2026", "OPDI_EXPLORER_FROM_DAY")
