"""Build TrailO answer protocol rows from race JSON (mirrors 1_results_trailo.html)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from sportorg.modules.trailo.codes import expand_trailo_control_code_strings, parse_trailo_code

MAX_ORG_NAME = 40
MAX_PERSON_NAME = 60
RELAY_MISSING_DASH = "—"
RESULT_STATUS_DISQUALIFIED = 3
STATUS_PRIORITY = [8, 4, 3, 5, 13]
RELAY_MERGED_FIELDS = ["index", "result_relay", "place_show"]

QUALIFICATION_NAMES: Dict[Union[int, str], str] = {
    "": "б/р",
    0: "б/р",
    1: "Iю",
    2: "IIю",
    3: "IIIю",
    4: "I",
    5: "II",
    6: "III",
    7: "КМС",
    8: "МС",
    9: "МСМК",
}

_RE_MAIN = re.compile(r"^\d+[A-Za-z]$")
_RE_TC_TIME_NEW = re.compile(r"^\d{1,2}TT$")
_RE_TC_TIME_LEGACY = re.compile(r"^\d{3}TT$")


@dataclass
class SplitCell:
    text: str
    is_answer: bool = False
    is_correct: Optional[bool] = None


@dataclass
class ProtocolField:
    key: str
    title: str
    active: bool = True
    is_time: bool = False


@dataclass
class ProtocolBlock:
    name: str
    fields: List[ProtocolField]
    rows: List[Dict[str, Any]]
    hide_answer_labels: bool = False
    short_name: str = ""
    group: Optional[Dict[str, Any]] = None
    course: Optional[Dict[str, Any]] = None


def prepare_race_dict(race: Dict[str, Any]) -> Dict[str, Any]:
    """Link nested objects the same way racePreparation() does in script.js.html."""
    race = dict(race)
    org_by_id = {str(o["id"]): o for o in race.get("organizations", [])}
    group_by_id = {str(g["id"]): g for g in race.get("groups", [])}
    course_by_id = {str(c["id"]): c for c in race.get("courses", [])}
    persons: List[Dict[str, Any]] = []
    for person in race.get("persons", []):
        p = dict(person)
        org_id = p.get("organization_id")
        p["organization"] = org_by_id.get(str(org_id)) if org_id else None
        group_id = p.get("group_id")
        p["group"] = group_by_id.get(str(group_id)) if group_id else None
        persons.append(p)
    race["persons"] = persons
    person_by_id = {str(p["id"]): p for p in persons}

    results: List[Dict[str, Any]] = []
    for result in race.get("results", []):
        r = dict(result)
        if r.get("status") == 16:
            r["status"] = 1
        person_id = r.get("person_id")
        r["person"] = person_by_id.get(str(person_id)) if person_id else None
        results.append(r)
    race["results"] = results

    groups: List[Dict[str, Any]] = []
    for group in race.get("groups", []):
        g = dict(group)
        course_id = g.get("course_id")
        g["course"] = course_by_id.get(str(course_id)) if course_id else None
        groups.append(g)
    race["groups"] = sorted(groups, key=lambda item: str(item.get("name", "")).upper())
    race["courses"] = sorted(
        race.get("courses", []), key=lambda item: str(item.get("name", "")).upper()
    )
    race["organizations"] = sorted(
        race.get("organizations", []), key=lambda item: str(item.get("name", "")).upper()
    )
    return race


def enrich_courses_for_trailo_docx(
    race: Dict[str, Any], mode: TrailoMode
) -> List[Dict[str, Any]]:
    """Add trailo_main_cp_count / trailo_time_cp_count for Word protocol headers."""
    courses: List[Dict[str, Any]] = []
    for course in race.get("courses") or []:
        course_dict = dict(course)
        main_count, time_tc_count = count_trailo_course_controls(course_dict, mode)
        course_dict["trailo_main_cp_count"] = main_count
        course_dict["trailo_time_cp_count"] = time_tc_count
        courses.append(course_dict)
    return courses


def format_race_dict_for_trailo_docx(race: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare race dict for TrailO Word templates (trailo_time in display units)."""
    race = prepare_race_dict(race)
    mode = TrailoMode(race)
    formatted_results: List[Dict[str, Any]] = []
    for result in race.get("results") or []:
        r = dict(result)
        r["trailo_time"] = _format_trailo_time(r, mode)
        formatted_results.append(r)
    race["results"] = formatted_results
    race["courses"] = enrich_courses_for_trailo_docx(race, mode)
    return race


def ms_to_hhmmss(msec: int) -> str:
    if msec < 0:
        msec += 24 * 60 * 60 * 1000
    total_sec = int(msec // 1000)
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    seconds = total_sec % 60
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def format_birth_date(value: Any) -> str:
    if not value:
        return ""
    date_string = str(value)
    iso_match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", date_string)
    if iso_match:
        return f"{iso_match.group(3)}.{iso_match.group(2)}.{iso_match.group(1)}"
    return date_string[:10] if len(date_string) >= 10 else date_string


def person_name_part(value: Any) -> str:
    s = str(value or "").strip()
    if not s or s in ("—", "-", "–", "−"):
        return ""
    return s


def format_person_name(person: Optional[Dict[str, Any]]) -> str:
    if not person:
        return ""
    parts = [
        person_name_part(person.get("surname")),
        person_name_part(person.get("name")),
        person_name_part(person.get("middle_name")),
    ]
    return " ".join(part for part in parts if part)[:MAX_PERSON_NAME]


def format_relay_bib(bib: Any) -> str:
    n = int(bib or 0)
    if n <= 1000:
        return str(n)
    leg = n // 1000
    team = n % 1000
    if leg > 0 and team > 0:
        return f"{team}.{leg}"
    return str(n)


def relay_team_bib(row: Dict[str, Any]) -> int:
    bib = row.get("bib_raw", row.get("bib"))
    return int(bib or 0) % 1000


def relay_leg_number(row: Dict[str, Any]) -> int:
    bib = row.get("bib_raw", row.get("bib"))
    return int(bib or 0) // 1000


class TrailoMode:
    def __init__(self, race: Dict[str, Any]) -> None:
        settings = race.get("settings") or {}
        self.trailo_mode = str(settings.get("trailo_mode") or "")
        self.trailo_alternate_course = bool(
            settings.get("trailo_alternate_course")
            or settings.get("trailo_custom_penalty_time_enabled")
        )
        self.settings = settings
        self.is_trailo = settings.get("result_processing_mode") == "trailo"
        self.is_relay = int((race.get("data") or {}).get("race_type") or 0) == 3
        self.is_preo = self.trailo_uses_station_time() and self.trailo_mode == "preo"
        self.is_tempo = not self.trailo_uses_points()
        self.is_preo_sprint = not self.trailo_uses_station_time()

    def trailo_uses_points(self) -> bool:
        if self.trailo_alternate_course:
            main_on = self.settings.get("trailo_main_course_enabled", True) is not False
            return main_on and bool(self.settings.get("trailo_main_course_points_enabled"))
        return self.trailo_mode != "tempo"

    def trailo_uses_station_time(self) -> bool:
        if self.trailo_alternate_course:
            return bool(self.settings.get("trailo_station_enabled"))
        return self.trailo_mode != "preo_sprint"

    def trailo_main_course_enabled(self) -> bool:
        if self.trailo_alternate_course:
            return self.settings.get("trailo_main_course_enabled", True) is not False
        return self.trailo_mode != "tempo"

    def trailo_skip_pre_station_controls(self) -> bool:
        if not self.trailo_alternate_course and self.trailo_mode == "tempo":
            return True
        if self.trailo_alternate_course and not self.trailo_main_course_enabled():
            return True
        return False

    def time_control_title(self) -> str:
        return "Станция" if self.is_tempo else "Время Тайм-КП"

    def trailo_station_penalty_sec(self) -> int:
        if self.trailo_alternate_course:
            if not self.trailo_uses_station_time():
                return 0
            return int(self.settings.get("trailo_time_penalty") or 0)
        if self.settings.get("trailo_custom_penalty_time_enabled"):
            return int(self.settings.get("trailo_time_penalty") or 0)
        if self.trailo_mode == "preo":
            return 60
        if self.trailo_mode == "tempo":
            return 30
        return 0

    def trailo_wrong_answer_penalty_sec(self) -> int:
        if self.trailo_alternate_course:
            if not self.trailo_main_course_enabled():
                return 0
            if not self.settings.get("trailo_main_course_wrong_answer_penalty_enabled"):
                return 0
        elif not self.settings.get("trailo_custom_penalty_time_enabled"):
            return 0
        elif not int(self.settings.get("trailo_wrong_answer_penalty") or 0):
            return 0
        return int(self.settings.get("trailo_wrong_answer_penalty") or 0)


def is_trailo_time_control_code(code: Any) -> bool:
    code = str(code or "")
    if _RE_TC_TIME_NEW.match(code):
        return True
    if re.match(r"^\d{1,2}T\d+[A-Za-z]$", code):
        return True
    if _RE_TC_TIME_LEGACY.match(code):
        return True
    if re.match(r"^\d{3}T[A-Za-z]$", code):
        return True
    return False


def trailo_control_is_time_punch_column(code: Any) -> bool:
    code = str(code or "").strip()
    if not code:
        return False
    if _RE_TC_TIME_NEW.match(code) or _RE_TC_TIME_LEGACY.match(code):
        return True
    return code[-1] == "T"


def is_trailo_main_control_code(code: Any) -> bool:
    code = str(code or "").strip()
    if not code or is_trailo_time_control_code(code):
        return False
    return bool(_RE_MAIN.match(code))


def trailo_protocol_include_split(split: Dict[str, Any], mode: TrailoMode) -> bool:
    ci = int(split.get("course_index") or 0)
    if ci > 0:
        return True
    if is_trailo_time_control_code(split.get("code")):
        return True
    return mode.trailo_main_course_enabled() and is_trailo_main_control_code(
        split.get("code")
    )


def trailo_protocol_cell_key(
    split: Dict[str, Any], course: Optional[Dict[str, Any]]
) -> Optional[str]:
    code = str(split.get("code") or "").strip()
    if not code:
        return None
    base = code[:-1]
    ci = int(split.get("course_index") or 0)
    if ci >= 1:
        return f"{ci - 1}_{base}"
    if course and course.get("controls"):
        raw_codes = [
            str(ctrl.get("code") or "").strip() for ctrl in course["controls"]
        ]
        expanded = expand_trailo_control_code_strings(raw_codes)
        for index, expanded_code in enumerate(expanded):
            if expanded_code[:-1] == base:
                return f"{index}_{base}"
    return None


def find_course_by_name(race: Dict[str, Any], name: Any) -> Optional[Dict[str, Any]]:
    if name is None or name == "":
        return None
    key = str(name)
    for course in race.get("courses", []):
        if str(course.get("name")) == key:
            return course
    return None


def find_course_for_person(
    race: Dict[str, Any], person: Optional[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    if not person:
        return None
    bib = int(person.get("bib") or 0)
    by_bib = find_course_by_name(race, str(bib))
    if by_bib:
        return by_bib
    if bib > 1000:
        leg = bib // 1000
        team = bib % 1000
        if leg > 0 and team > 0:
            by_bib = find_course_by_name(race, f"{team}.{leg}")
            if by_bib:
                return by_bib
    group = person.get("group")
    if group and group.get("course"):
        return group["course"]
    return None


def get_person_course(
    race: Dict[str, Any],
    person: Optional[Dict[str, Any]],
    group: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    return find_course_for_person(race, person) or (
        group.get("course") if group else None
    )


def trailo_control_field_defs_for_course(
    course: Optional[Dict[str, Any]], mode: TrailoMode
) -> List[ProtocolField]:
    if not course or not course.get("controls"):
        return []
    raw_codes = [str(ctrl.get("code") or "").strip() for ctrl in course["controls"]]
    expanded_codes = expand_trailo_control_code_strings(raw_codes)
    tempo_station_started = False
    defs: List[ProtocolField] = []
    time_title = mode.time_control_title()
    for index, code in enumerate(expanded_codes):
        if not mode.trailo_main_course_enabled() and is_trailo_main_control_code(code):
            continue
        is_time = trailo_control_is_time_punch_column(code)
        if mode.trailo_skip_pre_station_controls():
            if is_time:
                tempo_station_started = True
            elif not tempo_station_started:
                continue
        title = time_title if is_time else (code[-1] if code else "")
        defs.append(
            ProtocolField(
                key=f"{index}_{code[:-1]}",
                title=title,
                is_time=is_time,
            )
        )
    return defs


def format_group_control_time(group: Optional[Dict[str, Any]]) -> str:
    if not group:
        return ""
    msec = int(group.get("max_time") or 0)
    if msec <= 0:
        return ""
    return ms_to_hhmmss(msec)


def count_trailo_course_controls(
    course: Optional[Dict[str, Any]], mode: TrailoMode
) -> Tuple[int, int]:
    """Return (main control count, time-control station count) on the course."""
    if not course or not course.get("controls"):
        return 0, 0
    raw_codes = [str(ctrl.get("code") or "").strip() for ctrl in course["controls"]]
    expanded_codes = expand_trailo_control_code_strings(raw_codes)
    main_count = 0
    time_tc_indexes = set()
    tempo_station_started = False
    for code in expanded_codes:
        if not mode.trailo_main_course_enabled() and is_trailo_main_control_code(code):
            continue
        is_time = trailo_control_is_time_punch_column(code)
        if mode.trailo_skip_pre_station_controls():
            if is_time:
                tempo_station_started = True
            elif not tempo_station_started:
                continue
        parsed = parse_trailo_code(code)
        if parsed.kind == "main":
            main_count += 1
        elif parsed.kind == "tc_time" and parsed.tc_idx is not None:
            time_tc_indexes.add(parsed.tc_idx)
    return main_count, len(time_tc_indexes)


def course_distance_km_text(course: Optional[Dict[str, Any]]) -> str:
    if not course:
        return ""
    length_m = int(course.get("length") or 0)
    if length_m <= 0:
        return ""
    km = length_m / 1000.0
    if abs(km - round(km)) < 0.05:
        return str(int(round(km)))
    return f"{km:.1f}".replace(".", ",")


def _station_count_phrase(count: int) -> str:
    n = abs(int(count)) % 100
    n1 = n % 10
    if 11 <= n <= 19:
        word = "станций"
    elif n1 == 1:
        word = "станция"
    elif 2 <= n1 <= 4:
        word = "станции"
    else:
        word = "станций"
    return f"{count} {word}"


def preo_course_summary_lines(
    course: Optional[Dict[str, Any]], mode: TrailoMode
) -> List[str]:
    if mode.trailo_mode != "preo":
        return []
    km = course_distance_km_text(course)
    main_count, time_tc_count = count_trailo_course_controls(course, mode)
    km_text = km if km else "—"
    return [
        f"Дистанция: КМ — {km_text}, КП — {main_count}, тайм КП — {time_tc_count}"
    ]


def tempo_course_summary_lines(
    course: Optional[Dict[str, Any]], mode: TrailoMode
) -> List[str]:
    if mode.trailo_mode != "tempo":
        return []
    _, station_count = count_trailo_course_controls(course, mode)
    return [f"Дистанция: {_station_count_phrase(station_count)}"]


def group_header_detail_lines(
    group: Optional[Dict[str, Any]],
    course: Optional[Dict[str, Any]],
    mode: TrailoMode,
) -> List[str]:
    lines: List[str] = []
    control_time = format_group_control_time(group)
    if control_time:
        lines.append(f"Контрольное время — {control_time}")
    lines.extend(preo_course_summary_lines(course, mode))
    lines.extend(tempo_course_summary_lines(course, mode))
    return lines


def trailo_station_task_counts_by_idx(course: Optional[Dict[str, Any]]) -> Dict[int, int]:
    counts: Dict[int, int] = {}
    if not course or not course.get("controls"):
        return counts
    raw_codes = [str(ctrl.get("code") or "").strip() for ctrl in course["controls"]]
    for code in expand_trailo_control_code_strings(raw_codes):
        parsed = parse_trailo_code(code)
        if parsed.kind == "tc_answer" and parsed.tc_idx is not None:
            counts[parsed.tc_idx] = counts.get(parsed.tc_idx, 0) + 1
    return counts


def preo_pass_time(result: Optional[Dict[str, Any]], mode: TrailoMode) -> str:
    if not mode.is_preo or not result:
        return ""
    # start_msec comes from Result.get_start_time() and respects system_start_source.
    start = result.get("start_msec")
    if start is None:
        start = result.get("start_time")
    finish = result.get("finish_time", result.get("finish_msec"))
    if start is None or finish is None:
        return ""
    diff = int(finish) - int(start)
    if diff < 0:
        diff += 24 * 60 * 60 * 1000
    return ms_to_hhmmss(diff)


def split_cell_value(
    split: Dict[str, Any], mode: TrailoMode
) -> Tuple[str, bool, Optional[bool]]:
    code = str(split.get("code") or "")
    is_time = code[-1:] == "T" if code else False
    if is_time:
        time_msec = int(split.get("time") or 0)
        if mode.is_preo or mode.is_tempo:
            return str(time_msec // 1000), False, None
        return ms_to_hhmmss(time_msec), False, None
    letter = code[-1] if code else ""
    return letter, True, bool(split.get("is_correct", True))


def build_base_fields(mode: TrailoMode) -> List[ProtocolField]:
    result_key = "trailo_time" if (mode.is_tempo or mode.is_preo) else "result"
    result_title = "Результат Время"
    fields = [
        ProtocolField("index", "№"),
        ProtocolField("group", "Группа", active=False),
        ProtocolField("name", "Фамилия Имя Отчество"),
        ProtocolField("org", "Команда"),
        ProtocolField("year", "Дата рождения"),
        ProtocolField("qual", "Разряд"),
        ProtocolField("bib", "Номер"),
        ProtocolField("preo_pass_time", "Время", active=mode.is_preo),
        ProtocolField(
            "preo_team_pass_time",
            "Время",
            active=mode.is_preo and mode.is_relay,
        ),
        ProtocolField("trailo_score_penalty", "ШтрафКВ", active=mode.is_preo),
        ProtocolField("trailo_score", "Результат очки", active=not mode.is_tempo),
        ProtocolField(result_key, result_title),
        ProtocolField("result_relay", "Результат команды", active=mode.is_relay),
        ProtocolField("place_show", "Место"),
    ]
    return [f for f in fields if f.active]


def append_trailo_protocol_fields(
    fields: List[ProtocolField],
    rows: List[Dict[str, Any]],
    race: Dict[str, Any],
    fallback_course: Optional[Dict[str, Any]],
    mode: TrailoMode,
) -> None:
    by_key: Dict[str, ProtocolField] = {}
    order: List[str] = []

    def add_course(course: Optional[Dict[str, Any]]) -> None:
        if not course:
            return
        for field_def in trailo_control_field_defs_for_course(course, mode):
            if field_def.key not in by_key:
                by_key[field_def.key] = field_def
                order.append(field_def.key)

    add_course(fallback_course)
    for row in rows:
        person = (row.get("data") or {}).get("person")
        add_course(find_course_for_person(race, person))
    for key in order:
        fields.append(by_key[key])


def protocol_answer_labels_differ(
    rows: List[Dict[str, Any]],
    race: Dict[str, Any],
    fallback_course: Optional[Dict[str, Any]],
    mode: TrailoMode,
) -> bool:
    courses: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def add(course: Optional[Dict[str, Any]]) -> None:
        if not course or course.get("id") is None:
            return
        cid = str(course["id"])
        if cid in seen:
            return
        seen.add(cid)
        courses.append(course)

    add(fallback_course)
    for row in rows:
        person = (row.get("data") or {}).get("person")
        add(find_course_for_person(race, person))
    if len(courses) <= 1:
        return False
    signatures = [
        "|".join(
            f"{f.key}={f.title}"
            for f in trailo_control_field_defs_for_course(course, mode)
        )
        for course in courses
    ]
    return len(set(signatures)) > 1


def _format_trailo_time(result: Dict[str, Any], mode: TrailoMode) -> Any:
    trailo_time = int(result.get("trailo_time") or 0)
    if mode.is_preo or mode.is_tempo:
        return trailo_time // 1000
    return ms_to_hhmmss(trailo_time)


def _build_result_row(
    race: Dict[str, Any],
    result: Dict[str, Any],
    mode: TrailoMode,
    *,
    is_relay: bool,
    group: Optional[Dict[str, Any]] = None,
    course_for_keys: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    person = result.get("person") or {}
    org = person.get("organization") or {}
    qual_code = person.get("qual")
    row: Dict[str, Any] = {
        "index": 0,
        "name": format_person_name(person),
        "org": str(org.get("name") or "")[:MAX_ORG_NAME],
        "qual": QUALIFICATION_NAMES.get(qual_code, ""),
        "bib": format_relay_bib(person.get("bib")) if is_relay else person.get("bib"),
        "bib_raw": person.get("bib"),
        "year": format_birth_date(person.get("birth_date")),
        "preo_pass_time": preo_pass_time(result, mode),
        "preo_team_pass_time": "",
        "trailo_score_penalty": result.get("trailo_score_penalty"),
        "trailo_score": result.get("trailo_score"),
        "trailo_time": _format_trailo_time(result, mode),
        "result": result.get("result_current"),
        "result_relay": result.get("result_relay"),
        "result_msec": result.get("result_msec"),
        "place": result.get("place"),
        "status": result.get("status"),
        "place_show": (
            "o/c"
            if person.get("is_out_of_competition")
            else ("" if result.get("place") in (0, -1) else result.get("place"))
        ),
        "is_out_of_competition": person.get("is_out_of_competition"),
        "data": result,
    }
    if group:
        row["group"] = (person.get("group") or {}).get("name", "")
    if result.get("status") != 1:
        row["place_show"] = ""
        if result.get("status") == 13 and result.get("status_comment"):
            row["preo_pass_time"] = result.get("status_comment")
        if mode.is_preo:
            row["trailo_score"] = ""

    course = course_for_keys or get_person_course(race, person, group)
    for split in result.get("splits") or []:
        if not trailo_protocol_include_split(split, mode):
            continue
        text, is_answer, is_correct = split_cell_value(split, mode)
        cell_key = trailo_protocol_cell_key(split, course)
        if cell_key:
            row[cell_key] = SplitCell(text, is_answer=is_answer, is_correct=is_correct)
    return row


def _status_sort_key(status: int) -> int:
    try:
        return STATUS_PRIORITY.index(status)
    except ValueError:
        return len(STATUS_PRIORITY)


def get_results_by_group(
    race: Dict[str, Any],
    group: Dict[str, Any],
    mode: TrailoMode,
    count: int = 0,
) -> List[Dict[str, Any]]:
    is_relay = group.get("__type") == 3 or mode.is_relay
    results: List[Dict[str, Any]] = []
    group_id = group.get("id")
    for result in race.get("results", []):
        person = result.get("person")
        if not person or not person.get("group"):
            continue
        if str(person["group"].get("id")) != str(group_id):
            continue
        place = int(result.get("place") or 0)
        if count and not (0 < place <= count):
            continue
        results.append(
            _build_result_row(
                race,
                result,
                mode,
                is_relay=is_relay,
                group=group,
                course_for_keys=get_person_course(race, person, group),
            )
        )
    if is_relay:
        inject_missing_relay_leg_rows(results, race, group, mode)
    results.sort(key=lambda row: _row_sort_key(row, is_relay, mode))
    if is_relay:
        return finalize_relay_results_list(results, race, mode)
    for index, row in enumerate(results, start=1):
        row["index"] = index
    return results


def get_results_by_course(
    race: Dict[str, Any],
    course: Dict[str, Any],
    mode: TrailoMode,
    count: int = 0,
) -> List[Dict[str, Any]]:
    is_relay = mode.is_relay
    results: List[Dict[str, Any]] = []
    course_id = course.get("id")
    for result in race.get("results", []):
        person = result.get("person")
        if not person or not person.get("group"):
            continue
        person_course = find_course_for_person(race, person)
        if not person_course or str(person_course.get("id")) != str(course_id):
            continue
        place = int(result.get("place") or 0)
        if count and not (0 < place <= count):
            continue
        results.append(
            _build_result_row(
                race,
                result,
                mode,
                is_relay=is_relay,
                course_for_keys=person_course,
            )
        )
    if is_relay:
        inject_missing_relay_leg_rows(results, race, course, mode, by_course=True)
    results.sort(key=lambda row: _row_sort_key(row, is_relay, mode))
    if is_relay:
        return finalize_relay_results_list(results, race, mode)
    for index, row in enumerate(results, start=1):
        row["index"] = index
    return results


def _row_sort_key(row: Dict[str, Any], is_relay: bool, mode: TrailoMode) -> tuple:
    if is_relay:
        place = int(row.get("place") or 999999)
        if place < 1:
            return (1, relay_leg_number(row))
        return (0, place, relay_leg_number(row))
    status_a = int(row.get("status") or 0)
    if status_a != 1:
        return (1, _status_sort_key(status_a))
    place = int(row.get("place") or 999999)
    if place < 1:
        return (2, _status_sort_key(status_a))
    return (0, place)


def find_race_result_for_person(
    race: Dict[str, Any], person: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    for result in race.get("results", []):
        res_person = result.get("person")
        if not res_person:
            continue
        if person.get("id") is not None and res_person.get("id") == person.get("id"):
            return result
        if res_person.get("bib") == person.get("bib"):
            return result
    return None


def is_relay_leg_missing_for_protocol(
    person: Dict[str, Any], result: Optional[Dict[str, Any]]
) -> bool:
    leg = int(person.get("bib") or 0) // 1000
    if leg < 2:
        return False
    if not result:
        return True
    return int(result.get("status") or 0) != 1


def find_relay_team_row_in_results(
    results: List[Dict[str, Any]], team_num: int
) -> Optional[Dict[str, Any]]:
    lead = None
    any_row = None
    for row in results:
        bib_raw = int(row.get("bib_raw") or row.get("bib") or 0)
        if bib_raw % 1000 != team_num:
            continue
        any_row = row
        if bib_raw // 1000 == 1:
            lead = row
    return lead or any_row


def fill_missing_relay_leg_protocol_cells(
    row: Dict[str, Any],
    course_or_group: Dict[str, Any],
    mode: TrailoMode,
) -> None:
    course = course_or_group.get("course") or course_or_group
    if not course or not course.get("controls"):
        return
    penalty_sec = mode.trailo_station_penalty_sec()
    task_counts = trailo_station_task_counts_by_idx(course)
    wrong_main_sec = mode.trailo_wrong_answer_penalty_sec()
    raw_codes = [str(ctrl.get("code") or "").strip() for ctrl in course["controls"]]
    expanded_codes = expand_trailo_control_code_strings(raw_codes)
    tempo_station_started = False
    total_trailo_msec = 0
    main_errors = 0

    for index, code in enumerate(expanded_codes):
        if not mode.trailo_main_course_enabled() and is_trailo_main_control_code(code):
            continue
        if mode.trailo_skip_pre_station_controls():
            is_time_col = trailo_control_is_time_punch_column(code)
            if is_time_col:
                tempo_station_started = True
            elif not tempo_station_started:
                continue
        cell_key = f"{index}_{code[:-1]}"
        if trailo_control_is_time_punch_column(code):
            parsed = parse_trailo_code(code)
            tc_idx = parsed.tc_idx
            tasks = task_counts.get(tc_idx, 0) if tc_idx is not None else 0
            station_time_sec = penalty_sec * tasks
            station_answer_penalty_sec = penalty_sec * tasks
            total_trailo_msec += (station_time_sec + station_answer_penalty_sec) * 1000
            row[cell_key] = SplitCell(str(station_time_sec), is_answer=False)
        elif is_trailo_main_control_code(code):
            main_errors += 1
            row[cell_key] = SplitCell("X", is_answer=True, is_correct=False)
        else:
            row[cell_key] = SplitCell("X", is_answer=True, is_correct=False)
    if wrong_main_sec > 0:
        total_trailo_msec += wrong_main_sec * 1000 * main_errors
    if mode.is_preo or mode.is_tempo:
        row["trailo_time"] = total_trailo_msec // 1000
    else:
        row["trailo_time"] = ms_to_hhmmss(total_trailo_msec)
    if mode.trailo_uses_points():
        row["trailo_score"] = 0
        row["trailo_score_penalty"] = 0
    else:
        row["trailo_score"] = ""
        row["trailo_score_penalty"] = ""


def build_missing_relay_leg_protocol_row(
    person: Dict[str, Any],
    course_or_group: Dict[str, Any],
    team_row: Optional[Dict[str, Any]],
    mode: TrailoMode,
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "index": 0,
        "name": "",
        "org": "",
        "qual": "",
        "year": "",
        "bib": format_relay_bib(person.get("bib")),
        "bib_raw": person.get("bib"),
        "preo_pass_time": "",
        "preo_team_pass_time": "",
        "trailo_score_penalty": "",
        "trailo_score": 0 if mode.trailo_uses_points() else "",
        "result": "",
        "result_relay": team_row.get("result_relay", "") if team_row else "",
        "result_msec": 0,
        "place": team_row.get("place", 0) if team_row else 0,
        "status": 0,
        "place_show": team_row.get("place_show", "") if team_row else "",
        "is_out_of_competition": False,
        "is_missing_relay_leg": True,
        "data": {"person": person, "splits": [], "status": 0},
    }
    row["name"] = format_person_name(person)
    org = person.get("organization") or {}
    row["org"] = str(org.get("name") or "")[:MAX_ORG_NAME]
    row["year"] = format_birth_date(person.get("birth_date"))
    qual_code = person.get("qual")
    row["qual"] = QUALIFICATION_NAMES.get(qual_code, "")
    row["preo_pass_time"] = RELAY_MISSING_DASH
    fill_missing_relay_leg_protocol_cells(row, course_or_group, mode)
    return row


def inject_missing_relay_leg_rows(
    results: List[Dict[str, Any]],
    race: Dict[str, Any],
    group_or_course: Dict[str, Any],
    mode: TrailoMode,
    *,
    by_course: bool = False,
) -> None:
    if not mode.is_relay or not mode.is_trailo:
        return
    is_group_context = bool(group_or_course.get("course"))
    course = group_or_course.get("course") or group_or_course
    row_by_bib = {
        int(row.get("bib_raw") or row.get("bib") or 0): index
        for index, row in enumerate(results)
    }
    for person in race.get("persons", []):
        if not person.get("group"):
            continue
        if is_group_context and str(person["group"].get("id")) != str(
            group_or_course.get("id")
        ):
            continue
        if not is_group_context and course:
            person_course = find_course_for_person(race, person)
            if not person_course or str(person_course.get("id")) != str(course.get("id")):
                continue
        bib_raw = int(person.get("bib") or 0)
        if bib_raw <= 1000:
            continue
        if bib_raw // 1000 < 2:
            continue
        race_result = find_race_result_for_person(race, person)
        if not is_relay_leg_missing_for_protocol(person, race_result):
            continue
        team_row = find_relay_team_row_in_results(results, bib_raw % 1000)
        leg_course = find_course_for_person(race, person) or course
        if not leg_course:
            continue
        if bib_raw in row_by_bib:
            row = results[row_by_bib[bib_raw]]
            row["name"] = format_person_name(person)
            org = person.get("organization") or {}
            row["org"] = str(org.get("name") or "")[:MAX_ORG_NAME]
            row["year"] = format_birth_date(person.get("birth_date"))
            qual_code = person.get("qual")
            row["qual"] = QUALIFICATION_NAMES.get(qual_code, "")
            row["preo_pass_time"] = RELAY_MISSING_DASH
            row["is_missing_relay_leg"] = True
            if team_row:
                if team_row.get("result_relay"):
                    row["result_relay"] = team_row["result_relay"]
                if team_row.get("place_show"):
                    row["place_show"] = team_row["place_show"]
                if int(team_row.get("place") or 0) > 0:
                    row["place"] = team_row["place"]
            fill_missing_relay_leg_protocol_cells(row, {"course": leg_course}, mode)
        else:
            results.append(
                build_missing_relay_leg_protocol_row(
                    person, {"course": leg_course}, team_row, mode
                )
            )


def relay_team_group_sort_key(
    team_legs: List[Dict[str, Any]], relay_leg_count: int
) -> tuple:
    is_dq = False
    ok_legs = 0
    participants = len(team_legs)
    place = 999999
    trailo_score = 0
    trailo_time = 999999999
    for row in team_legs:
        res = row.get("data") or {}
        if int(res.get("status") or 0) == RESULT_STATUS_DISQUALIFIED:
            is_dq = True
        if int(row.get("status") or 0) == 1 or int(res.get("status") or 0) == 1:
            ok_legs += 1
        row_place = int(row.get("place") or 0)
        if 0 < row_place < place:
            place = row_place
        if row.get("trailo_score") not in ("", None):
            trailo_score = max(trailo_score, int(row.get("trailo_score") or 0))
        if row.get("trailo_time") not in ("", None):
            trailo_time = min(trailo_time, int(row.get("trailo_time") or trailo_time))
    is_complete = ok_legs >= relay_leg_count and participants >= relay_leg_count
    team_bib = relay_team_bib(team_legs[0])
    if is_dq:
        return (2, 0 if is_complete else 1, -participants, trailo_score, trailo_time, team_bib)
    if is_complete and place < 999999:
        return (0, place, -trailo_score, trailo_time, team_bib)
    not_started = all(
        int(row.get("status") or 0) != 1
        and int((row.get("data") or {}).get("status") or 0) != 1
        for row in team_legs
    )
    if not_started:
        return (3, participants, team_bib)
    return (1, -ok_legs, -participants, trailo_score, trailo_time, team_bib)


def annotate_relay_leg_passage_times(team_legs: List[Dict[str, Any]], mode: TrailoMode) -> int:
    team_legs.sort(key=relay_leg_number)
    team_sum_msec = 0
    for row in team_legs:
        if row.get("is_missing_relay_leg"):
            continue
        res = row.get("data") or {}
        if int(res.get("status") or 0) != 1:
            continue
        row["preo_pass_time"] = preo_pass_time(res, mode)
        team_sum_msec += int(res.get("trailo_time") or 0)
    return team_sum_msec


def relay_team_trailo_score_penalty(team_legs: List[Dict[str, Any]]) -> Any:
    for row in team_legs:
        if relay_leg_number(row) == 1:
            penalty = row.get("trailo_score_penalty")
            return "" if penalty in ("", None) else penalty
    return ""


def annotate_relay_team_group(
    team_legs: List[Dict[str, Any]], team_index: int, mode: TrailoMode
) -> None:
    if not team_legs:
        return
    first = team_legs[0]
    first["index"] = team_index
    first["_relay_rowspan"] = len(team_legs)
    if team_index > 1:
        first["_relay_team_separator"] = True
    merged_fields = list(RELAY_MERGED_FIELDS)
    if mode.is_preo:
        team_pass_msec = annotate_relay_leg_passage_times(team_legs, mode)
        first["preo_team_pass_time"] = (
            ms_to_hhmmss(team_pass_msec) if team_pass_msec > 0 else ""
        )
        first["trailo_score_penalty"] = relay_team_trailo_score_penalty(team_legs)
        merged_fields.extend(["preo_team_pass_time", "trailo_score_penalty"])
    first["_relay_merged_fields"] = merged_fields
    for row in team_legs[1:]:
        row["index"] = ""
        row["result_relay"] = ""
        row["_relay_skip_fields"] = list(merged_fields)


def finalize_relay_results_list(
    results_list: List[Dict[str, Any]], race: Dict[str, Any], mode: TrailoMode
) -> List[Dict[str, Any]]:
    teams: List[List[Dict[str, Any]]] = []
    pos = 0
    while pos < len(results_list):
        team_bib = relay_team_bib(results_list[pos])
        team_legs = []
        while pos < len(results_list) and relay_team_bib(results_list[pos]) == team_bib:
            team_legs.append(results_list[pos])
            pos += 1
        teams.append(team_legs)
    relay_leg_count = int((race.get("data") or {}).get("relay_leg_count") or 0)
    teams.sort(key=lambda legs: relay_team_group_sort_key(legs, relay_leg_count))
    out: List[Dict[str, Any]] = []
    for team_index, team_legs in enumerate(teams, start=1):
        annotate_relay_team_group(team_legs, team_index, mode)
        out.extend(team_legs)
    return out


@dataclass
class TrailoProtocolOptions:
    show_protocol_by_course: bool = False
    show_answers: bool = True
    show_podium_only: bool = False
    count: int = 0


def group_display_name(group: Dict[str, Any]) -> str:
    """Full group title for protocol headers (long_name when set)."""
    long_name = str(group.get("long_name") or "").strip()
    if long_name:
        return long_name
    return str(group.get("name") or "")


def build_protocol_blocks(
    race: Dict[str, Any], options: Optional[TrailoProtocolOptions] = None
) -> List[ProtocolBlock]:
    options = options or TrailoProtocolOptions()
    race = prepare_race_dict(race)
    mode = TrailoMode(race)
    effective_count = 3 if options.show_podium_only else options.count
    show_control_columns = options.show_answers
    blocks: List[ProtocolBlock] = []
    items = race.get("courses", []) if options.show_protocol_by_course else race.get("groups", [])
    for item in items:
        if options.show_protocol_by_course:
            course = item
            rows = get_results_by_course(race, course, mode, effective_count)
            fallback_course = course
            block_name = str(course.get("name") or "")
            sheet_name = block_name
        else:
            group = item
            rows = get_results_by_group(race, group, mode, effective_count)
            fallback_course = group.get("course")
            block_name = group_display_name(group)
            sheet_name = str(group.get("name") or block_name)
        if not rows:
            continue
        fields = build_base_fields(mode)
        if show_control_columns:
            append_trailo_protocol_fields(fields, rows, race, fallback_course, mode)
        hide_answer_labels = show_control_columns and protocol_answer_labels_differ(
            rows, race, fallback_course, mode
        )
        blocks.append(
            ProtocolBlock(
                name=block_name,
                fields=fields,
                rows=rows,
                hide_answer_labels=hide_answer_labels,
                short_name=sheet_name,
                group=group if not options.show_protocol_by_course else None,
                course=fallback_course,
            )
        )
    return blocks
