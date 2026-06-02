"""Shared SportOrg in-memory fixtures for Excel export tests."""
from datetime import date

from sportorg.common.otime import OTime
from sportorg.models.memory import (
    Course,
    CourseControl,
    Group,
    Organization,
    Person,
    Qualification,
    Race,
    RaceType,
    ResultManual,
    ResultStatus,
    Split,
    new_event,
    race,
)
from sportorg.modules.trailo.result_checker import TrailoResultChecker


def setup_preo_group():
    new_event([Race()])
    race().data.race_type = RaceType.INDIVIDUAL_RACE
    race().set_setting("result_processing_mode", "trailo")
    race().set_setting("trailo_mode", "preo")
    race().set_setting("trailo_alternate_course", False)
    race().set_setting("trailo_custom_penalty_time_enabled", True)
    race().data.chief_referee = "Сидоров С.С."
    race().data.secretary = "Кузнецова К.К."

    org = Organization()
    org.name = "Club A"

    group = Group()
    group.name = "M21"
    group.long_name = "Мужчины 21"
    group.max_time = OTime(msec=45 * 60 * 1000)

    course = Course()
    course.length = 5500
    for code in ("31A", "1TT", "1T1A", "1T2B"):
        control = CourseControl()
        control.code = code
        course.controls.append(control)
    group.course = course

    person = Person()
    person.group = group
    person.organization = org
    person.set_bib(101)
    person.surname = "Ivanov"
    person.name = "Ivan"
    person.birth_date = date(1990, 5, 15)
    person.qual = Qualification.III

    split_main = Split()
    split_main.code = "31A"
    split_main.is_correct = True
    split_main.time = OTime(msec=20_000)
    split_main.course_index = 0

    split_time = Split()
    split_time.code = "1TT"
    split_time.is_correct = True
    split_time.time = OTime(msec=50_000)
    split_time.course_index = 1

    split_answer = Split()
    split_answer.code = "1T1A"
    split_answer.is_correct = True
    split_answer.time = OTime(msec=55_000)
    split_answer.course_index = 2

    result = ResultManual()
    result.person = person
    result.status = ResultStatus.OK
    result.start_time = OTime(msec=0)
    result.finish_time = OTime(msec=60_000)
    result.splits = [split_main, split_time, split_answer]
    result.trailo_score = 1
    TrailoResultChecker.process(result, lambda *args, **kwargs: 0)

    race().groups.append(group)
    race().courses.append(course)
    race().persons.append(person)
    race().results.append(result)

    person_dns = Person()
    person_dns.group = group
    person_dns.organization = org
    person_dns.set_bib(102)
    person_dns.surname = "Petrov"
    person_dns.name = "Petr"
    person_dns.birth_date = date(1991, 1, 1)
    person_dns.qual = Qualification.III

    result_dns = ResultManual()
    result_dns.person = person_dns
    result_dns.status = ResultStatus.DID_NOT_START
    TrailoResultChecker.process(result_dns, lambda *args, **kwargs: 0)

    race().persons.append(person_dns)
    race().results.append(result_dns)
    return race().to_dict()
