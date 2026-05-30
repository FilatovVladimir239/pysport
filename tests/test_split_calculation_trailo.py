"""Регрессия: расчёт сплитов TrailO не падает на кодах вида 1T1B (не int(prefix))."""

from sportorg.common.otime import OTime
from sportorg.models.memory import (
    Course,
    CourseControl,
    Group,
    Person,
    Race,
    ResultSportident,
    Split,
    new_event,
    race,
)
from sportorg.models.result.split_calculation import PersonSplits
from sportorg.modules.trailo.codes import parse_trailo_code, trailo_sort_key


def test_trailo_generate_with_tc_answer_codes_no_int_error():
    course = Course()
    for code in ("1A", "2C", "1TT", "1T1B", "1T2E"):
        cp = CourseControl()
        cp.code = code
        course.controls.append(cp)

    group = Group()
    group.course = course
    person = Person()
    person.group = group
    result = ResultSportident()
    result.person = person

    new_event([Race()])
    r = race()
    r.courses.append(course)
    r.groups.append(group)
    r.persons.append(person)
    r.results.append(result)
    r.set_setting("result_processing_mode", "trailo")

    PersonSplits(r, result).generate()

    missing_1t1 = [s for s in result.splits if s.code == "1T1X"]
    assert len(missing_1t1) == 1
    assert missing_1t1[0].course_index == 3


def test_trailo_duplicate_main_cp_uses_earliest_punch_only():
    course = Course()
    for code in ("9Z", "10D", "11Z"):
        cp = CourseControl()
        cp.code = code
        course.controls.append(cp)

    group = Group()
    group.course = course
    person = Person()
    person.group = group
    result = ResultSportident()
    result.person = person

    split_9 = Split()
    split_9.code = "9Z"
    split_9.time = OTime(msec=1000)

    split_late = Split()
    split_late.code = "10D"
    split_late.time = OTime(msec=12 * 3600_000 + 22 * 60_000)

    split_first = Split()
    split_first.code = "10E"
    split_first.time = OTime(msec=12 * 3600_000 + 21 * 60_000 + 51_000)

    split_11 = Split()
    split_11.code = "11Z"
    split_11.time = OTime(msec=3000)

    result.splits = [split_late, split_first, split_9, split_11]

    new_event([Race()])
    r = race()
    r.courses.append(course)
    r.groups.append(group)
    r.persons.append(person)
    r.results.append(result)
    r.set_setting("result_processing_mode", "trailo")

    PersonSplits(r, result).generate()

    by_code = {s.code: s for s in result.splits}
    assert by_code["10E"].course_index >= 0
    assert by_code["10D"].course_index == -1
    assert by_code["10E"].is_correct is False
    main_codes = [
        s.code
        for s in sorted(result.splits, key=trailo_sort_key)
        if parse_trailo_code(s.code).kind == "main"
    ]
    assert main_codes.index("9Z") < main_codes.index("10E") < main_codes.index("11Z")
