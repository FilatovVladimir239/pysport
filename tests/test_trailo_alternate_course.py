from sportorg.common.otime import OTime
from sportorg.models.memory import (
    Course,
    CourseControl,
    Group,
    Person,
    Race,
    ResultManual,
    ResultStatus,
    Split,
    new_event,
    race,
)
from sportorg.models.result.result_calculation import ResultCalculation
from sportorg.models.result.result_tools import recalculate_results
from sportorg.modules.trailo.config import (
    SETTING_ALTERNATE_COURSE,
    SETTING_MAIN_POINTS,
    SETTING_STATION,
    TrailoConfig,
)
from sportorg.modules.trailo.result_checker import TrailoResultChecker


def _setup_trailo_person():
    new_event([Race()])
    race().set_setting("result_processing_mode", "trailo")

    group = Group()
    group.name = "TrailO"
    course = Course()
    for code in ("31A", "1TT", "1T1A"):
        control = CourseControl()
        control.code = code
        course.controls.append(control)
    group.course = course

    person = Person()
    person.group = group
    person.set_bib(1)
    person.name = "Athlete"

    race().groups.append(group)
    race().courses.append(course)
    race().persons.append(person)
    return person, course


def _add_result(person: Person, splits) -> ResultManual:
    result = ResultManual()
    result.person = person
    result.status = ResultStatus.OK
    result.start_time = OTime(msec=0)
    result.finish_time = OTime(msec=60_000)
    result.splits = splits
    race().results.append(result)
    return result


def test_alternate_course_points_then_station_time_ranking():
    person, _course = _setup_trailo_person()
    race().set_setting(SETTING_ALTERNATE_COURSE, True)
    race().set_setting("trailo_main_course_enabled", True)
    race().set_setting(SETTING_MAIN_POINTS, True)
    race().set_setting(SETTING_STATION, True)
    race().set_setting("trailo_time_penalty", 0)

    split_main = Split()
    split_main.code = "31A"
    split_main.is_correct = True
    split_main.time = OTime(msec=10_000)
    split_main.course_index = 0
    split_tt = Split()
    split_tt.code = "1TT"
    split_tt.is_correct = True
    split_tt.time = OTime(msec=40_000)
    split_tt.course_index = 1

    _add_result(person, [split_main, split_tt])
    recalculate_results(recheck_results=True)

    result = race().find_person_result(person)
    assert result.trailo_score == 1
    assert result.get_trailo_time().to_msec() == 40_000
    assert TrailoConfig.points_enabled()
    assert TrailoConfig.station_enabled()


def test_alternate_course_time_only_without_points():
    person, _course = _setup_trailo_person()
    race().set_setting(SETTING_ALTERNATE_COURSE, True)
    race().set_setting("trailo_main_course_enabled", True)
    race().set_setting(SETTING_MAIN_POINTS, False)
    race().set_setting(SETTING_STATION, True)

    split_tt = Split()
    split_tt.code = "1TT"
    split_tt.is_correct = True
    split_tt.time = OTime(msec=25_000)
    split_tt.course_index = 1

    _add_result(person, [split_tt])
    recalculate_results(recheck_results=True)

    result = race().find_person_result(person)
    assert result.trailo_score == 0
    assert result.get_trailo_time().to_msec() == 25_000
    assert TrailoConfig.place_comparison_key(result) == (25_000,)


def test_alternate_course_passage_time_when_station_disabled():
    person, _course = _setup_trailo_person()
    race().set_setting(SETTING_ALTERNATE_COURSE, True)
    race().set_setting(SETTING_MAIN_POINTS, False)
    race().set_setting(SETTING_STATION, False)

    split_tt = Split()
    split_tt.code = "1TT"
    split_tt.is_correct = True
    split_tt.time = OTime(msec=25_000)
    split_tt.course_index = 1

    _add_result(person, [split_tt])
    recalculate_results(recheck_results=True)

    result = race().find_person_result(person)
    assert result.get_trailo_time().to_msec() == 60_000


def test_alternate_course_station_penalty_setting():
    race().set_setting(SETTING_ALTERNATE_COURSE, True)
    race().set_setting(SETTING_STATION, True)
    race().set_setting("trailo_time_penalty", 33)

    assert TrailoResultChecker.get_penalty_time_for_mode().to_msec() == 33_000
