"""Регрессия: расчёт сплитов TrailO не падает на кодах вида 1T1B (не int(prefix))."""

from sportorg.models.memory import (
    Course,
    CourseControl,
    Group,
    Person,
    Race,
    ResultSportident,
    new_event,
    race,
)
from sportorg.models.result.split_calculation import PersonSplits


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
