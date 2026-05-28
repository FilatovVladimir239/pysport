from sportorg.common.otime import OTime
from sportorg.models.memory import (
    Group,
    Person,
    Race,
    ResultManual,
    ResultStatus,
    new_event,
    race,
)
from sportorg.models.result.result_calculation import ResultCalculation


def _create_trailo_race(trailo_mode: str = "preo"):
    new_event([Race()])
    race().set_setting("result_processing_mode", "trailo")
    race().set_setting("trailo_mode", trailo_mode)

    group = Group()
    group.name = "M21"
    person_a = Person()
    person_a.group = group
    person_a.name = "Athlete A"
    person_b = Person()
    person_b.group = group
    person_b.name = "Athlete B"
    person_c = Person()
    person_c.group = group
    person_c.name = "Athlete C"
    persons = [person_a, person_b, person_c]

    race().groups.append(group)
    race().persons.extend(persons)
    return group, persons


def _add_ok_result(person: Person, trailo_score: int, trailo_time_msec: int) -> ResultManual:
    result = ResultManual()
    result.person = person
    result.status = ResultStatus.OK
    result.trailo_score = trailo_score
    result.trailo_time = OTime(msec=trailo_time_msec)
    result.start_time = OTime(msec=0)
    result.finish_time = OTime(msec=trailo_time_msec)
    race().results.append(result)
    return result


def _assign_places(group: Group) -> None:
    calculation = ResultCalculation(race())
    finishes = calculation.get_group_finishes(group)
    finishes.sort()
    calculation.set_places(finishes)


def test_trailo_preo_tied_score_and_time_share_place():
    group, persons = _create_trailo_race("preo")
    _add_ok_result(persons[0], 10, 120_000)
    _add_ok_result(persons[1], 10, 120_000)
    _add_ok_result(persons[2], 9, 100_000)

    _assign_places(group)

    places = {
        race().find_person_result(person).person.name: race().find_person_result(person).place
        for person in persons
    }
    assert places["Athlete A"] == 1
    assert places["Athlete B"] == 1
    assert places["Athlete C"] == 3


def test_trailo_preo_same_score_different_time_get_separate_places():
    group, persons = _create_trailo_race("preo")
    _add_ok_result(persons[0], 10, 100_000)
    _add_ok_result(persons[1], 10, 110_000)

    _assign_places(group)

    places = sorted(
        race().find_person_result(person).place for person in persons[:2]
    )
    assert places == [1, 2]


def test_trailo_preo_sprint_same_score_faster_gets_better_place():
    group, persons = _create_trailo_race("preo_sprint")
    _add_ok_result(persons[0], 8, 100_000)
    _add_ok_result(persons[1], 8, 110_000)
    _add_ok_result(persons[2], 7, 90_000)

    _assign_places(group)

    places = {
        race().find_person_result(person).person.name: race().find_person_result(person).place
        for person in persons
    }
    assert places["Athlete A"] == 1
    assert places["Athlete B"] == 2
    assert places["Athlete C"] == 3


def test_trailo_preo_sprint_tied_score_and_time_share_place():
    group, persons = _create_trailo_race("preo_sprint")
    _add_ok_result(persons[0], 8, 100_000)
    _add_ok_result(persons[1], 8, 100_000)
    _add_ok_result(persons[2], 7, 100_000)

    _assign_places(group)

    places = sorted(
        race().find_person_result(person).place for person in persons
    )
    assert places == [1, 1, 3]


def test_trailo_tempo_tied_time_share_place():
    group, persons = _create_trailo_race("tempo")
    _add_ok_result(persons[0], 0, 90_000)
    _add_ok_result(persons[1], 0, 90_000)
    _add_ok_result(persons[2], 0, 95_000)

    _assign_places(group)

    places = sorted(
        race().find_person_result(person).place for person in persons
    )
    assert places == [1, 1, 3]
