from typing import List, Tuple

import pytest

from sportorg.common.otime import OTime
from sportorg.models.memory import (
    Course,
    Group,
    Person,
    Race,
    ResultSportident,
    ResultStatus,
    Split,
    new_event,
    race,
)
from sportorg.models.result.result_checker import ResultChecker
from sportorg.utils.time import hhmmss_to_time

# Settings calculation time.
# credit_time_enabled [bool] - is enabled calculation credit time
# credit_time_сp [int] - number control point for credit time


@pytest.fixture
def new_race():
    course = Course()
    group = Group()
    group.course = course
    person = Person()
    person.group = group
    result = ResultSportident()
    result.person = person
    new_event([Race()])
    race().courses.append(course)
    race().groups.append(group)
    race().persons.append(person)
    race().results.append(result)
    race().set_setting("credit_time_cp", 41)

    return race


@pytest.fixture
def new_split1() -> List[Split]:
    return make_split(
        [
            ("31", "01:00:00"),
            ["41", "01:02:35"],
            ["51", "02:03:35"],
            ["41", "03:01:35"],
        ]
    )


@pytest.fixture
def new_split2() -> List[Split]:
    return make_split(
        [
            ("31", "12:03:00"),
            ["41", "13:04:35"],
            ["51", "14:02:35"],
            ["41", "15:02:35"],
        ]
    )


def make_split(splits: List[Tuple[str, str]]) -> List[Split]:
    ret = []
    for code, time in splits:
        split = Split()
        split.code = str(code)
        split.time = hhmmss_to_time(time)
        ret.append(split)
    return ret


def test_credit_calculation_when_credit_time_disabled(
    new_race: Race, new_split1, new_split2
):
    race().set_setting("credit_time_enabled", False)
    ok(new_split1, expected_result=OTime())
    ok(new_split2, expected_result=OTime())


def test_credit_calculation_when_credit_time_enabled(
    new_race: Race, new_split1, new_split2
):
    race().set_setting("credit_time_enabled", True)
    ok(new_split1, expected_result=hhmmss_to_time("01:00:35"))
    ok(new_split2, expected_result=hhmmss_to_time("02:01:35"))


def test_credit_calculation_caps_segment_at_maximum(
    new_race: Race, new_split1,
):
    race().set_setting("credit_time_enabled", True)
    race().set_setting("credit_time_max", 30 * 60 * 1000)
    # 2:35 for first 41 punch + 30:00 capped for second (58 min leg)
    ok(new_split1, expected_result=hhmmss_to_time("00:32:35"))


def ok(
    splits: List[Split],
    expected_result: OTime,
):
    result = race().results[0]
    result.splits = splits

    result.status = ResultStatus.OK
    ResultChecker.checking(result)
    result_credit = result.get_credit_time()
    assert result_credit == expected_result


def test_rogaine_penalty_uses_credit_time_on_first_check(new_race: Race):
    race().set_setting("result_processing_mode", "scores")
    race().set_setting("result_processing_score_mode", "fixed")
    race().set_setting("result_processing_fixed_score_value", 10)
    race().set_setting("result_processing_scores_minute_penalty", 1)
    race().set_setting("credit_time_enabled", True)
    race().set_setting("credit_time_cp", 250)
    race().set_setting("credit_time_max", 20 * 60 * 1000)

    group = race().groups[0]
    group.max_time = OTime(hour=2)

    result = race().results[0]
    result.status = ResultStatus.OK
    result.start_time = OTime(hour=0)
    result.finish_time = OTime(hour=2, minute=19)
    result.person.start_time = OTime(hour=0)
    result.splits = make_split(
        [
            ("31", "00:30:00"),
            ("90", "01:00:00"),
            ("250", "01:20:00"),
        ]
    )

    ResultChecker.checking(result)

    assert result.get_credit_time() == hhmmss_to_time("00:20:00")
    assert result.get_result_otime() == hhmmss_to_time("01:59:00")
    assert result.rogaine_penalty == 0
    assert result.rogaine_score == 30
