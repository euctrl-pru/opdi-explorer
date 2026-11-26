"""What every event type and every flight-list column means.

The wording is the data dictionary's, copied -- not rewritten -- from
opdi-portal `content/data/dictionary.qmd` (sections "Event types" and "Fields
of the info column"). A second description of the same events would drift from
the first, and a reader comparing the two would not know which to believe.

Copied rather than read at run time: the dashboard must not depend on a
checkout of another repository. `SOURCE` records where the copy was taken, and
`tests/explorer/test_catalogue.py` fails when a published type has no entry.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from opdi_explorer._columns import COLUMNS

#: Where the wording was copied from.
SOURCE = "opdi-portal feature/new-topics @ 8b59651"

#: The dictionary's ten families, in its order.
FAMILIES: Tuple[str, ...] = (
    "Take-off and landing", "Other runway events", "Block times",
    "Airport surface", "Vertical profile", "Distance rings", "Holding",
    "Point merge", "Airspace", "Track limits",
)

#: One or two sentences on each family, from the dictionary where it has them.
FAMILY_NOTES: Dict[str, str] = {
    "Take-off and landing": "The four moments on the runway that start and "
                            "end the time in the air.",
    "Other runway events": "What else happens on a runway: lining up, "
                           "leaving it, crossing it, or giving up a landing.",
    "Block times": "When the aircraft leaves its parking position and when it "
                   "stops at one.",
    "Airport surface": "The aircraft enters or leaves an area of the airport: "
                       "a taxiway, an apron, a stand, a threshold, a hangar or "
                       "a de-icing pad.",
    "Vertical profile": "The shape of the flight in height: the tops, the "
                        "periods of level flight, and the flight levels "
                        "crossed. A flight level is an altitude in hundreds of "
                        "feet on the standard air pressure of 1013.25 hPa: "
                        "level 100 is about 10,000 ft.",
    "Distance rings": "Crossings of circles of 40 to 120 NM around the "
                      "flight's departure or destination airport.",
    "Holding": "A holding pattern is a loop flown while waiting for "
               "permission to continue.",
    "Point merge": "A point merge system is an arrival procedure in which "
                   "aircraft fly along an arc, called a leg, at a fixed "
                   "distance from a merge point until they are sent directly "
                   "to it.",
    "Airspace": "The flight passes from one flight information region to "
                "another.",
    "Track limits": "The first and the last position report of the track.",
}

#: Six colour groups: the number of hues that can be told apart together.
#: Families inside one group share a colour and differ by marker shape.
GROUPS: Dict[str, Tuple[str, ...]] = {
    "Runway": ("Take-off and landing", "Other runway events"),
    "Ground": ("Block times", "Airport surface"),
    "Vertical profile": ("Vertical profile",),
    "Rings and airspace": ("Distance rings", "Airspace"),
    "Holding and point merge": ("Holding", "Point merge"),
    "Track limits": ("Track limits",),
}

#: The family, and the colour group, of a type the dictionary does not know.
UNDESCRIBED = "Not described yet"

_GROUP_OF = {f: g for g, families in GROUPS.items() for f in families}


def group_of(family: str) -> str:
    """The colour group of *family*; an undescribed family is its own."""
    return _GROUP_OF.get(family, UNDESCRIBED)


@dataclass(frozen=True)
class EventType:
    type: str
    family: str
    description: str
    fields: Dict[str, str] = field(default_factory=dict)
    described: bool = True


# -- the fields of `info`, per kind of event --------------------------------

_RUNWAY = {
    "apt_icao": "ICAO code of the airport.",
    "runway": "Runway direction used, for example 27R.",
    "rwy_ident": "The same, under the name used by earlier releases.",
    "runway_bearing_deg": "True bearing of the runway centre line, in degrees "
                          "clockwise from true north.",
    "traversal_class": "Class of the runway pass: departure, arrival or "
                       "crossing.",
    "align_deg": "Angle between the aircraft's track and the runway, in "
                 "degrees.",
    "max_gs_kt": "Highest ground speed during the runway pass, in knots (kt).",
    "osn_flight_id": "Call sign received during the runway pass.",
    "milestone": "Label of the moment in the PRU flight diagram: T06 line-up, "
                 "T07 take-off roll, T08 take-off, T16 threshold, T17 "
                 "touchdown, T19 runway vacated. The PRU numbered them for "
                 "this diagram only; they have no official status and differ "
                 "from the A-CDM Implementation Manual's milestone numbers. "
                 "Not set on runway crossings.",
    "height_reference": "What the height above the ground was measured from: "
                        "track (the aircraft's own altitude on the ground at "
                        "that airport) or elevation (the airport's published "
                        "elevation).",
}

#: `ATOT` and `ALDT` carry the runway fields, two of their own, and -- when
#: the time was found from the climb or descent instead -- the legacy fields.
_TAKE_OFF_LANDING = dict(_RUNWAY, **{
    "method": "acdm when the time was found on the runway; legacy when it "
              "could not be and was found from the climb or the descent "
              "instead.",
    "bracket_s": "Seconds between the two position reports the 15 ft crossing "
                 "was placed between.",
    "role": "With method legacy: departure or arrival.",
    "bearing_error_deg": "With method legacy: angle between the aircraft's "
                         "median track and the runway, in degrees.",
    "n_samples": "With method legacy: number of position reports the time was "
                 "found from.",
    "at_track_edge": "With method legacy: true when the report the time comes "
                     "from is the first report of the track (take-off) or its "
                     "last (landing).",
})

_GO_AROUND = {
    "apt_icao": "ICAO code of the destination airport.",
    "osn_flight_id": "Call sign received.",
    "low_height_ft": "Lowest height above the airport during the approach, in "
                     "feet.",
    "recovery_roc_ft_min": "Highest rate of climb after that point, in feet "
                           "per minute.",
    "excursion_seconds": "Duration of the excursion, in seconds.",
}

_AOBT = {
    "stand_exit": "Time of the exit from the stand this off-block leaves. "
                  "Absent when the part of the track holds no such stand "
                  "passage.",
    "stand": "Name in OpenStreetMap of the stand of stand_exit, when it has "
             "one.",
    "apt_icao": "ICAO code of the airport of that stand.",
    "first_seen_on": "Where the aircraft was when first received on the "
                     "ground: stand, apron, taxiway or other. First seen on a "
                     "taxiway, the time is mostly minutes late. Absent when "
                     "the track holds the landing before the departure.",
    "take_off": "The take-off of the same part of the track.",
    "take_off_method": "The method that found that take-off (acdm or legacy).",
}

_AIBT = {
    "stand_entry": "Time of the entry into the stand this in-block reaches. "
                   "Absent when the part of the track holds no such stand "
                   "passage.",
    "stand": "Name in OpenStreetMap of the stand of stand_entry, when it has "
             "one.",
    "apt_icao": "ICAO code of the airport of that stand.",
    "landing": "The landing of the same part of the track.",
    "landing_method": "The method that found that landing.",
}

_SURFACE = {
    "osm_id": "Identifier of the area in OpenStreetMap, the open map of the "
              "world. Where the aircraft enters or leaves several areas of one "
              "kind at the same report, the event names the smallest "
              "identifier.",
    "osm_aeroway": "Kind of area in OpenStreetMap, for example taxiway.",
    "osm_ref": "Name or number of the area in OpenStreetMap, for example a "
               "stand number.",
    "osm_airport": "ICAO code of the airport.",
    "opdi_time_in_use_s": "Time spent in the area, in seconds.",
    "osn_icao24": "ICAO 24-bit address of the aircraft.",
    "osn_flight_id": "Call sign received.",
    "at_track_start": "true on an entry at the first report with a position "
                      "of the track: reception started there.",
    "at_track_end": "true on an exit at the last report with a position of "
                    "the track: reception stopped there.",
    "ground_only": "true on the events of a track that never leaves the "
                   "ground and whose aircraft type is unknown or a vehicle "
                   "type, in practice an airport vehicle.",
    "encloses_stand": "true on the passage of a stand area that contains a "
                      "smaller stand passed at the same time.",
}

_TOPS = {
    "d200_time": "Time of the top as first found, before moving.",
    "d200_altitude_ft": "Altitude of the top as first found, in feet.",
    "relocated": "true when the top was moved, false otherwise.",
    "analysis_radius_nm": "Radius of the analysis around the airport, in NM "
                          "(200).",
    "method": "pru: the method of the EUROCONTROL Performance Review Unit.",
    "observed": "false when the track shows no altitude at least 3,000 ft "
                "below the top before it (top of climb) or after it (top of "
                "descent): the top is at the edge of reception.",
}

_LEVEL_OFF = {
    "kpi": "ICAO indicator the level-off counts for: KPI17 (climb) or KPI19 "
           "(descent).",
    "duration_s": "Duration of the level-off, in seconds.",
    "distance_nm": "Distance flown during the level-off, in NM.",
    "level_ft": "Altitude of the level-off, in feet.",
}

_FL = {
    "crossing_seq": "Number of the crossing of that level on the flight "
                    "(first = 1).",
    "direction": "up or down.",
    "bracket_s": "Seconds between the two position reports the crossing was "
                 "placed between.",
}

_RING = {
    "apt_icao": "ICAO code of the airport the circle is drawn around.",
    "direction": "inbound (towards the airport) or outbound.",
    "crossing_seq": "Number of the crossing of this circle on the flight "
                    "(first = 1).",
    "bearing": "Direction of the crossing point from the airport, in degrees "
               "clockwise from true north.",
    "flight_level": "Flight level of the aircraft at the crossing.",
    "bracket_s": "Seconds between the two position reports the crossing was "
                 "placed between.",
    "position_jump": "true when the two reports the crossing was placed "
                     "between imply more than 1,000 kt: the position stepped, "
                     "as near areas of GPS spoofing.",
}

_HOLDING = {
    "holding_seq": "Number of the holding pattern on the flight (first = 1).",
    "pattern": "racetrack or orbit.",
    "direction": "Direction of turn: R (right) or L (left).",
    "circuits": "Number of loops: total turn divided by 360 degrees, to one "
                "decimal.",
    "duration_s": "Time in the holding pattern, in seconds.",
    "distance_nm": "Distance flown in it, in NM.",
    "altitude_start_ft": "Altitude at the start, in feet.",
    "altitude_end_ft": "Altitude at the end, in feet.",
    "straight_pct": "Share of the time flown straight, in percent.",
    "context": "arrival (the flight lands at its destination within 60 "
               "minutes and 150 NM of the end of the hold), en-route (it "
               "lands later or further away) or other (local flight, no "
               "landing, three or more holds, or holds over half the time in "
               "the air).",
}

_PMS_LEG = {
    "apt_icao": "ICAO code of the airport the system serves.",
    "pms_id": "Identifier of the point merge system.",
    "merge_point": "Name of the merge point.",
    "leg_seq": "Number of the leg flown on the flight (first = 1).",
    "direction": "Direction of flight along the arc: cw (clockwise) or ccw "
                 "(counter-clockwise).",
    "leg_distance_nm": "Distance of the leg from the merge point, in NM.",
    "leg_level_ft": "Altitude on the leg, in feet.",
    "duration_s": "Time on the leg, in seconds.",
    "distance_nm": "Distance flown along the leg, in NM.",
    "direct_to_distance_nm": "Distance to the merge point on leaving the leg, "
                             "in NM.",
    "direct_aligned": "true when the aircraft then flew straight to the merge "
                      "point.",
}

_PMS_POINT = {
    "apt_icao": "ICAO code of the airport the system serves.",
    "pms_id": "Identifier of the point merge system.",
    "merge_point": "Name of the merge point.",
    "closest_nm": "Closest distance to the merge point, in NM.",
    "via_leg": "true when the aircraft flew a leg of the system just before.",
}

_FIR = {
    "crossing_seq": "Number of the crossing on the flight (first = 1).",
    "fir_from": "The region left, for example EGTTFIR.",
    "fir_to": "The region entered.",
    "fl": "Flight level at the crossing.",
    "bracket_s": "Time between the last position report in the old region and "
                 "the first in the new one, in seconds.",
    "airac_cfmu": "The AIRAC cycle of the boundaries used (524). An AIRAC "
                  "cycle is the 28-day period in which aeronautical data such "
                  "as airspace boundaries take effect.",
    "airac_validity_start": "First day of that cycle.",
    "airac_validity_end": "Last day of that cycle.",
    "vertical": "true when the two regions lie one above the other (a lower "
                "and an upper region), so the crossing is a climb or descent "
                "through their boundary level.",
}

_ELEMENTS = {
    "taxiway": "a taxiway", "apron": "an apron",
    "parking_position": "a parking position (a stand)",
    "threshold": "a runway threshold area", "hangar": "a hangar",
    "deicing_pad": "a de-icing pad",
}


def _entries() -> List[EventType]:
    e = []

    def add(type_, family, description, fields=None):
        e.append(EventType(type_, family, description, dict(fields or {})))

    f = "Take-off and landing"
    add("take-off-roll", f, "The aircraft starts its take-off run.", _RUNWAY)
    add("ATOT", f, "Actual take-off time: the wheels leave the runway.",
        _TAKE_OFF_LANDING)
    add("xing-runway-threshold", f,
        "The aircraft passes the runway threshold (the start of the landing "
        "part of the runway), a few seconds before touchdown.", _RUNWAY)
    add("ALDT", f, "Actual landing time: the wheels touch the runway.",
        _TAKE_OFF_LANDING)

    f = "Other runway events"
    add("line-up", f, "A departing aircraft enters the runway to take off.",
        _RUNWAY)
    add("runway-vacated", f,
        "An arriving aircraft leaves the runway after landing.", _RUNWAY)
    add("runway-crossing-entry", f,
        "A taxiing aircraft enters a runway to cross it.", _RUNWAY)
    add("runway-crossing-vacated", f,
        "The same aircraft leaves the runway on the other side.", _RUNWAY)
    add("go-around", f,
        "An approaching aircraft gives up the landing and climbs away; placed "
        "at the lowest point of the approach.", _GO_AROUND)

    f = "Block times"
    add("AOBT", f,
        "Actual off-block time: the aircraft starts to move away from its "
        "parking position (stand).", _AOBT)
    add("AIBT", f,
        "Actual in-block time: the aircraft stops at its stand after landing.",
        _AIBT)

    f = "Airport surface"
    for element, words in _ELEMENTS.items():
        add(f"entry-{element}", f,
            f"The aircraft enters an area of the airport: {words}.", _SURFACE)
        add(f"exit-{element}", f, f"The aircraft leaves that area: {words}.",
            _SURFACE)

    f = "Vertical profile"
    add("top-of-climb", f,
        "End of the climb to cruise, with the method of EUROCONTROL's "
        "vertical flight efficiency indicators.", _TOPS)
    add("top-of-descent", f, "Start of the final descent, same method.",
        _TOPS)
    add("level-start", f, "Start of a period of level flight, cruise "
        "included.")
    add("level-end", f, "End of that period.")
    add("level-off-climb-start", f,
        "Start of a level-off during the climb: level flight below the "
        "cruise.", _LEVEL_OFF)
    add("level-off-climb-end", f, "End of that level-off.", _LEVEL_OFF)
    add("level-off-descent-start", f,
        "Start of a level-off during the descent.", _LEVEL_OFF)
    add("level-off-descent-end", f, "End of that level-off.", _LEVEL_OFF)
    for level in (50, 70, 100, 245):
        add(f"xing-fl{level}", f,
            f"A crossing of flight level {level}, up or down.", _FL)

    f = "Distance rings"
    for radius in (40, 50, 60, 100, 110, 120):
        add(f"xing-{radius}nm", f,
            f"A crossing of a circle of {radius} NM around the flight's "
            "departure or destination airport.", _RING)

    f = "Holding"
    add("holding-start", f,
        "First turning sample of a holding pattern: a loop flown while "
        "waiting for permission to continue.", _HOLDING)
    add("holding-end", f,
        "Last turning sample of the pattern. Carries the holding "
        "measurements.", _HOLDING)

    f = "Point merge"
    add("pms-leg-entry", f, "The aircraft starts flying along a leg.",
        _PMS_LEG)
    add("pms-leg-exit", f,
        "The aircraft leaves the leg towards the merge point. Carries the "
        "point merge measurements.", _PMS_LEG)
    add("pms-merge-point", f,
        "The aircraft passes closest to a merge point, within 3 NM of it.",
        _PMS_POINT)

    f = "Airspace"
    add("xing-fir", f,
        "The flight passes from one flight information region (FIR) or upper "
        "information region (UIR) to another.", _FIR)

    f = "Track limits"
    add("first_seen", f, "The first position report of the track.")
    add("last_seen", f, "The last position report of the track.")
    return e


_EVENTS: Dict[str, EventType] = {e.type: e for e in _entries()}


def event(type_: str) -> EventType:
    """What *type_* is. Never raises: a type the dictionary does not know yet
    is still an event in the data, and has to be showable."""
    known = _EVENTS.get(type_)
    if known is not None:
        return known
    return EventType(
        type_, UNDESCRIBED,
        "This event type is in the data but not yet in the data dictionary.",
        {}, described=False)


def family_of(type_: str) -> str:
    return event(type_).family


def types_in(family: str) -> List[str]:
    """The described types of *family*, in the dictionary's order."""
    return [e.type for e in _EVENTS.values() if e.family == family]


def all_types() -> List[str]:
    return list(_EVENTS)


# -- the flight list --------------------------------------------------------

_COLUMN_GROUPING: Dict[str, Tuple[str, ...]] = {
    "Identity": ("flight_id", "icao24", "flt_id", "dof"),
    "Route and how the airports were found": (
        "adep", "ades", "adep_p", "ades_p", "adep_source", "ades_source"),
    "Aircraft": ("registration", "model", "typecode", "icao_aircraft_class",
                 "icao_operator"),
    "Times": ("first_seen", "last_seen", "atot", "aldt", "aobt", "aibt",
              "track_duration_min"),
    "Runway and stand": ("rwy_dep", "rwy_dep_bearing_deg", "rwy_arr",
                         "rwy_arr_bearing_deg", "stnd_dep", "stnd_arr"),
    "Ring crossings": (
        "c40_arr", "c50_arr", "c60_arr", "c100_arr", "c110_arr", "c120_arr",
        "c40_dep", "c50_dep", "c60_dep", "c100_dep", "c110_dep", "c120_dep"),
    "Movement flags and versions": (
        "superseded_dep", "superseded_arr", "movement_dep", "movement_arr",
        "version", "release"),
}

#: One line on what each group of columns is for.
COLUMN_GROUP_NOTES: Dict[str, str] = {
    "Identity": "Which flight, which aircraft, which day.",
    "Route and how the airports were found":
        "Where the flight went, the other airports it could have been, and "
        "how each end was decided.",
    "Aircraft": "What flew it: registration, model, type and operator.",
    "Times": "When it was seen, took off, landed, and left and reached its "
             "stand.",
    "Runway and stand": "Which runway and which parking position at each end.",
    "Ring crossings": "When it crossed circles of 40 to 120 NM around each "
                      "airport.",
    "Movement flags and versions":
        "Whether the row counts as a departure or an arrival, and which "
        "method and release produced it.",
}

def _shown(text: str) -> str:
    """A column description as explorer shows it.

    The one place the wording departs from the dictionary's: explorer does
    not say where the aircraft details come from. The dictionary's copy in
    `_columns.py` is left as it is.
    """
    text = text.replace(", from the OpenSky aircraft database", "")
    text = text.replace(" NULL when the aircraft is not in that database.",
                        " NULL when it is not known.")
    return text


#: group -> [(column, meaning)], the meaning being the dictionary's first
#: sentence for that column.
COLUMN_GROUPS: Dict[str, List[Tuple[str, str]]] = {
    group: [(c, _shown(COLUMNS[c][2])) for c in columns]
    for group, columns in _COLUMN_GROUPING.items()
}


def column(name: str) -> Tuple[str, str, str, str]:
    """`(type, unit, first sentence, full description)` of a flight-list
    column; a column the dictionary does not list gets empty text."""
    typ, unit, first, full = COLUMNS.get(name, ("", "", "", ""))
    return typ, unit, _shown(first), _shown(full)
