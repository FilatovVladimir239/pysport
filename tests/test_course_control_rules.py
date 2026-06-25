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
    set_current_race_index,
)
from sportorg.models.result.course_control_rules import (
    build_rogaine_score_breakdown,
    calculate_control_chain_bonus,
    format_rogaine_course_control_codes,
    parse_allowed_control_codes,
    parse_control_chain_bonuses,
    parse_control_start_delay_minutes,
    parse_rogaine_course_control_codes,
    split_counts_for_course_score,
)
from sportorg.models.result.result_checker import ResultChecker


def _prepare_race(*, group: Group, person: Person, result: ResultSportident) -> None:
    new_event([Race()])
    set_current_race_index(0)
    race().set_setting("result_processing_score_mode", "rogain")
    race().set_setting("system_start_source", "protocol")
    race().groups.append(group)
    race().persons.append(person)
    race().results.append(result)


def test_parse_allowed_control_codes():
    assert parse_allowed_control_codes("") == []
    assert parse_allowed_control_codes("31, 32\n45") == ["31", "32", "45"]


def test_parse_rogaine_course_control_codes():
    assert parse_rogaine_course_control_codes("") == []
    assert parse_rogaine_course_control_codes("31\n32\n45") == ["31", "32", "45"]
    assert parse_rogaine_course_control_codes("31 150\n32") == ["31", "32"]


def test_format_rogaine_course_control_codes():
    controls = [CourseControl(), CourseControl()]
    controls[0].code = "31"
    controls[1].code = "32"
    assert format_rogaine_course_control_codes(controls) == "31\n32"
    assert format_rogaine_course_control_codes([], ["45", "67"]) == "45\n67"


def test_parse_control_start_delay_minutes():
    assert parse_control_start_delay_minutes("") == {}
    assert parse_control_start_delay_minutes("45 60\n50=90") == {"45": 60, "50": 90}


def test_parse_control_chain_bonuses():
    assert parse_control_chain_bonuses("") == []
    assert parse_control_chain_bonuses("45 67 32 5") == [
        {"codes": ["45", "67", "32"], "bonus": 5}
    ]
    assert parse_control_chain_bonuses("45,67,32=10") == [
        {"codes": ["45", "67", "32"], "bonus": 10}
    ]


def test_calculate_control_chain_bonus_non_overlapping():
    chains = [{"codes": ["45", "67"], "bonus": 5}]
    assert calculate_control_chain_bonus(["45", "67", "45", "67"], chains) == 10
    assert calculate_control_chain_bonus(["45", "31", "67"], chains) == 0


def test_rogaine_score_filters_by_allowed_controls():
    course = Course()
    course.allowed_control_codes = ["31", "32"]

    group = Group()
    group.course = course

    person = Person()
    person.group = group
    person.start_time = OTime(minute=0)

    result = ResultSportident()
    result.person = person

    split31 = Split()
    split31.code = "31"
    split31.time = OTime(minute=10)

    split45 = Split()
    split45.code = "45"
    split45.time = OTime(minute=20)

    result.splits = [split31, split45]
    _prepare_race(group=group, person=person, result=result)
    race().courses.append(course)

    assert ResultChecker.calculate_rogaine_score(result) == 3


def test_rogaine_score_ignores_early_control():
    course = Course()
    course.control_start_delay_minutes = {"45": 60}

    group = Group()
    group.course = course

    person = Person()
    person.group = group
    person.start_time = OTime(hour=10, minute=0, sec=0)

    result = ResultSportident()
    result.person = person

    early = Split()
    early.code = "45"
    early.time = OTime(hour=10, minute=30, sec=0)

    late = Split()
    late.code = "45"
    late.time = OTime(hour=11, minute=5, sec=0)

    result.splits = [early, late]
    _prepare_race(group=group, person=person, result=result)
    race().courses.append(course)

    assert ResultChecker.calculate_rogaine_score(result) == 4


def test_split_counts_without_times_keeps_backward_compat():
    course = Course()
    course.control_start_delay_minutes = {"45": 60}

    result = ResultSportident()
    result.person = Person()
    result.person.group = Group()
    result.person.group.course = course

    split = Split()
    split.code = "45"
    split.time = OTime(0)

    assert split_counts_for_course_score(result, split, course) is True


def test_rogaine_score_adds_chain_bonus():
    course = Course()
    course.control_chain_bonuses = [{"codes": ["45", "67", "32"], "bonus": 5}]

    group = Group()
    group.course = course

    person = Person()
    person.group = group

    result = ResultSportident()
    result.person = person
    result.splits = [
        _split("45"),
        _split("67"),
        _split("32"),
    ]
    _prepare_race(group=group, person=person, result=result)
    race().courses.append(course)
    race().set_setting("result_processing_score_mode", "fixed")
    race().set_setting("result_processing_fixed_score_value", 1)

    # 3 CP * 1 point + 5 chain bonus
    assert ResultChecker.calculate_rogaine_score(result) == 8


def test_chain_bonus_not_awarded_if_controls_not_consecutive():
    course = Course()
    course.control_chain_bonuses = [{"codes": ["45", "67", "32"], "bonus": 5}]

    group = Group()
    group.course = course

    person = Person()
    person.group = group

    result = ResultSportident()
    result.person = person
    result.splits = [
        _split("45"),
        _split("31"),
        _split("67"),
        _split("32"),
    ]
    _prepare_race(group=group, person=person, result=result)
    race().courses.append(course)
    race().set_setting("result_processing_score_mode", "fixed")
    race().set_setting("result_processing_fixed_score_value", 1)

    assert ResultChecker.calculate_rogaine_score(result) == 4


def test_build_rogaine_score_breakdown_with_early_and_chain_bonus():
    course = Course()
    course.allowed_control_codes = ["31", "45", "67", "32"]
    course.control_start_delay_minutes = {"45": 60}
    course.control_chain_bonuses = [{"codes": ["45", "67", "32"], "bonus": 5}]

    group = Group()
    group.course = course

    person = Person()
    person.group = group
    person.start_time = OTime(hour=10, minute=0, sec=0)

    result = ResultSportident()
    result.person = person
    result.splits = [
        _split("31", hour=10, minute=10),
        _split("45", hour=10, minute=30),  # too early for CP 45
        _split("67", hour=11, minute=5),
        _split("32", hour=11, minute=20),
        _split("45", hour=11, minute=40),  # counts
        _split("67", hour=11, minute=50),
        _split("32", hour=12, minute=0),
    ]
    _prepare_race(group=group, person=person, result=result)
    race().courses.append(course)
    race().set_setting("result_processing_score_mode", "fixed")
    race().set_setting("result_processing_fixed_score_value", 1)

    breakdown = build_rogaine_score_breakdown(result)
    assert breakdown["splits"][1]["skip_reason"] == "early"
    assert breakdown["splits"][1]["points"] == 0
    assert breakdown["splits"][4]["counts"] is True
    assert breakdown["cp_score"] == 4
    assert breakdown["chain_bonus"] == 10
    assert breakdown["gross_score"] == 14


def _split(code: str, minute: int = 1, hour: int = 0) -> Split:
    split = Split()
    split.code = code
    split.time = OTime(hour=hour, minute=minute)
    return split
