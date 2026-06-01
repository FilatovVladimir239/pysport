"""TrailO start time must follow timekeeping system_start_source setting."""

from sportorg.common.otime import OTime
from sportorg.models.memory import (
    Group,
    Organization,
    Person,
    Race,
    RaceType,
    ResultSportident,
    ResultStatus,
    new_event,
    race,
)
from sportorg.modules.reports.trailo_protocol import TrailoMode, preo_pass_time


def _setup_trailo_preo_person():
    new_event([Race()])
    race().set_setting("result_processing_mode", "trailo")
    race().set_setting("trailo_mode", "preo")

    org = Organization()
    org.name = "Club"

    group = Group()
    group.name = "Open"

    person = Person()
    person.group = group
    person.organization = org
    person.set_bib(101)
    person.start_time = OTime(msec=10_000)

    race().groups.append(group)
    race().persons.append(person)
    return person


def test_preo_pass_time_uses_start_msec_not_raw_start_time():
    mode = TrailoMode(
        {
            "settings": {"result_processing_mode": "trailo", "trailo_mode": "preo"},
            "data": {},
        }
    )
    result = {
        "start_time": 20_000,
        "start_msec": 10_000,
        "finish_time": 50_000,
        "finish_msec": 50_000,
        "status": 1,
    }
    assert preo_pass_time(result, mode) == "00:00:40"


def test_result_sportident_get_start_time_respects_source():
    person = _setup_trailo_preo_person()

    result = ResultSportident()
    result.person = person
    result.status = ResultStatus.OK
    result.start_time = OTime(msec=20_000)
    result.finish_time = OTime(msec=50_000)
    race().results.append(result)

    race().set_setting("system_start_source", "protocol")
    assert result.get_start_time().to_msec() == 10_000

    race().set_setting("system_start_source", "station")
    assert result.get_start_time().to_msec() == 20_000


def test_trailo_relay_leg_passage_time_respects_start_source():
    from sportorg.models.result.result_tools import recalculate_results

    person = _setup_trailo_preo_person()
    race().data.race_type = RaceType.RELAY
    race().data.relay_leg_count = 1
    person.set_bib(1001)

    result = ResultSportident()
    result.person = person
    result.status = ResultStatus.OK
    result.start_time = OTime(msec=20_000)
    result.finish_time = OTime(msec=50_000)
    race().results.append(result)

    race().set_setting("system_start_source", "protocol")
    recalculate_results(recheck_results=True)
    team = race().relay_teams[0]
    assert team.get_trailo_leg_passage_time(1).to_msec() == 40_000

    result.start_time = OTime(msec=20_000)
    person.start_time = OTime(msec=10_000)
    race().set_setting("system_start_source", "station")
    recalculate_results(recheck_results=True)
    assert team.get_trailo_leg_passage_time(1).to_msec() == 30_000
