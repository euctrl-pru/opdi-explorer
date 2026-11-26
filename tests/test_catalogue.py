"""Every published event type and flight-list column is described."""

from opdi_explorer import catalogue

#: The 49 event types published on dev for 2026-04-28.
PUBLISHED_TYPES = [
    "level-end", "level-start", "entry-taxiway", "exit-taxiway",
    "level-off-descent-end", "level-off-descent-start", "xing-fir",
    "xing-40nm", "xing-50nm", "first_seen", "last_seen", "xing-fl50",
    "xing-60nm", "xing-fl70", "xing-fl100", "top-of-climb", "top-of-descent",
    "xing-100nm", "xing-110nm", "xing-120nm", "exit-parking_position",
    "entry-parking_position", "xing-fl245", "level-off-climb-end",
    "level-off-climb-start", "ALDT", "ATOT", "exit-apron", "entry-apron",
    "runway-vacated", "take-off-roll", "line-up", "xing-runway-threshold",
    "AIBT", "AOBT", "entry-threshold", "exit-threshold", "pms-merge-point",
    "holding-start", "holding-end", "exit-deicing_pad", "entry-deicing_pad",
    "go-around", "pms-leg-exit", "pms-leg-entry", "exit-hangar",
    "entry-hangar", "runway-crossing-entry", "runway-crossing-vacated",
]


def test_every_published_type_is_described():
    assert len(PUBLISHED_TYPES) == 49
    assert [t for t in PUBLISHED_TYPES
            if not catalogue.event(t).described] == []


def test_the_catalogue_describes_nothing_that_is_not_published():
    assert sorted(catalogue.all_types()) == sorted(PUBLISHED_TYPES)


def test_every_type_belongs_to_one_of_the_ten_families():
    assert len(catalogue.FAMILIES) == 10
    assert {catalogue.event(t).family
            for t in PUBLISHED_TYPES} == set(catalogue.FAMILIES)
    assert set(catalogue.FAMILY_NOTES) == set(catalogue.FAMILIES)


def test_every_family_has_a_colour_group_and_there_are_six():
    assert len(catalogue.GROUPS) == 6
    assert sorted(f for fs in catalogue.GROUPS.values()
                  for f in fs) == sorted(catalogue.FAMILIES)
    assert catalogue.group_of("Holding") == "Holding and point merge"


def test_an_unknown_type_is_explained_as_not_described():
    e = catalogue.event("xing-tma")
    assert not e.described and e.fields == {}
    assert "not yet" in e.description
    assert e.family == catalogue.UNDESCRIBED
    assert catalogue.group_of(e.family) == catalogue.UNDESCRIBED


def test_wording_is_the_dictionarys():
    assert catalogue.event("ATOT").description == (
        "Actual take-off time: the wheels leave the runway.")
    assert catalogue.event("holding-end").fields["circuits"].startswith(
        "Number of loops")
    assert catalogue.event("level-start").fields == {}
    assert catalogue.event("first_seen").fields == {}
    assert "merge point" in catalogue.event("pms-merge-point").description


def test_take_off_and_landing_carry_both_methods_fields():
    fields = catalogue.event("ALDT").fields
    assert {"runway", "method", "bracket_s", "at_track_edge"} <= set(fields)


def test_types_in_a_family_keep_the_dictionarys_order():
    assert catalogue.types_in("Take-off and landing") == [
        "take-off-roll", "ATOT", "xing-runway-threshold", "ALDT"]
    assert catalogue.types_in("Holding") == ["holding-start", "holding-end"]


def test_every_flight_list_column_is_in_one_group():
    cols = [c for g in catalogue.COLUMN_GROUPS.values() for c, _ in g]
    assert len(cols) == len(set(cols)) == 46
    assert set(catalogue.COLUMN_GROUP_NOTES) == set(catalogue.COLUMN_GROUPS)
    assert all(meaning for g in catalogue.COLUMN_GROUPS.values()
               for _, meaning in g)


def test_a_column_meaning_is_the_dictionarys_first_sentence():
    meaning = dict(catalogue.COLUMN_GROUPS["Identity"])["flight_id"]
    assert meaning == "Unique identifier of the flight."
    assert catalogue.column("no_such_column") == ("", "", "", "")


def test_explorer_does_not_say_where_aircraft_details_come_from():
    shown = [catalogue.column(c) for g in catalogue.COLUMN_GROUPS.values()
             for c, _ in g]
    text = " ".join(part for row in shown for part in row)
    text += " ".join(m for g in catalogue.COLUMN_GROUPS.values() for _, m in g)
    text += " ".join(catalogue.COLUMN_GROUP_NOTES.values())
    assert "aircraft database" not in text.lower()
    # The description itself is still there.
    assert catalogue.column("typecode")[2] == (
        "ICAO aircraft type designator, for example A320.")
    assert catalogue.column("registration")[3] == (
        "Registration of the aircraft (its tail number). NULL when it is not "
        "known.")
