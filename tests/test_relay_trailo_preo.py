from sportorg.common.otime import OTime
from sportorg.models.memory import (
    Course,
    CourseControl,
    Group,
    Organization,
    Person,
    Race,
    RaceType,
    ResultManual,
    ResultStatus,
    Split,
    find,
    new_event,
    race,
)
from sportorg.models.result.result_calculation import ResultCalculation
from sportorg.models.result.result_tools import recalculate_results
from sportorg.models.result.split_calculation import RaceSplits
from sportorg.models.start.relay import get_team_result
from sportorg.modules.trailo.result_checker import TrailoResultChecker


def _setup_relay_preo():
    new_event([Race()])
    race().data.race_type = RaceType.RELAY
    race().data.relay_leg_count = 2
    race().set_setting("result_processing_mode", "trailo")
    race().set_setting("trailo_mode", "preo")
    race().set_setting("trailo_alternate_course", False)
    race().set_setting("trailo_custom_penalty_time_enabled", True)
    race().set_setting("trailo_wrong_answer_penalty", 60)

    org = Organization()
    org.name = "Team Alpha"

    group = Group()
    group.name = "Relay"
    group.set_type(RaceType.RELAY)

    course = Course()
    for code in ("31A", "1TT", "1T1A"):
        control = CourseControl()
        control.code = code
        course.controls.append(control)
    group.course = course

    leg1 = Person()
    leg1.group = group
    leg1.organization = org
    leg1.set_bib(1001)
    leg1.name = "Leg1"

    leg2 = Person()
    leg2.group = group
    leg2.organization = org
    leg2.set_bib(2001)
    leg2.name = "Leg2"

    race().groups.append(group)
    race().courses.append(course)
    race().persons.extend([leg1, leg2])
    return group, leg1, leg2


def _add_leg_result(person: Person, splits, trailo_score: int, finish_msec: int) -> ResultManual:
    result = ResultManual()
    result.person = person
    result.status = ResultStatus.OK
    result.start_time = OTime(msec=0)
    result.finish_time = OTime(msec=finish_msec)
    result.splits = splits
    result.trailo_score = trailo_score
    race().results.append(result)
    return result


def test_relay_preo_trailo_time_includes_main_course_errors():
    group, leg1, leg2 = _setup_relay_preo()

    split_main_wrong = Split()
    split_main_wrong.code = "31B"
    split_main_wrong.is_correct = False
    split_main_wrong.time = OTime(msec=30_000)
    split_main_wrong.course_index = 0

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

    result = _add_leg_result(leg1, [split_main_wrong, split_time, split_answer], 0, 60_000)
    TrailoResultChecker.process(result, lambda *args, **kwargs: 0)

    assert result.trailo_time.to_msec() == 50_000 + 60_000


def test_relay_preo_missing_leg2_counts_max_penalty_as_all_x():
    group, leg1, leg2 = _setup_relay_preo()
    race().set_setting("trailo_time_penalty", 60)

    split1 = Split()
    split1.code = "31A"
    split1.is_correct = True
    split1.time = OTime(msec=20_000)
    split1.course_index = 0
    split_tt1 = Split()
    split_tt1.code = "1TT"
    split_tt1.is_correct = True
    split_tt1.time = OTime(msec=40_000)
    split_tt1.course_index = 1
    split_ans1 = Split()
    split_ans1.code = "1T1A"
    split_ans1.is_correct = True
    split_ans1.time = OTime(msec=45_000)
    split_ans1.course_index = 2

    _add_leg_result(leg1, [split1, split_tt1, split_ans1], 1, 50_000)

    recalculate_results(recheck_results=True)

    team = find(race().relay_teams, bib_number=1)
    assert team is not None
    # leg2: station time 60*1 + task penalties 60*1 + main wrong 60 (TT is not counted as answer)
    assert team.get_trailo_time().to_msec() == 40_000 + 60_000 + 60_000 + 60_000
    leg2_synthetic_score, leg2_synthetic_time = (
        TrailoResultChecker.synthetic_missing_relay_leg_values(
            leg2, lambda *args, **kwargs: 0
        )
    )
    assert leg2_synthetic_time.to_msec() == 60_000 + 60_000 + 60_000
    assert leg2_synthetic_score == 0


def test_relay_preo_dnf_leg2_counts_max_penalty_as_all_x():
    group, leg1, leg2 = _setup_relay_preo()
    race().set_setting("trailo_time_penalty", 60)

    split1 = Split()
    split1.code = "31A"
    split1.is_correct = True
    split1.time = OTime(msec=20_000)
    split_tt1 = Split()
    split_tt1.code = "1TT"
    split_tt1.is_correct = True
    split_tt1.time = OTime(msec=40_000)
    split_ans1 = Split()
    split_ans1.code = "1T1A"
    split_ans1.is_correct = True
    split_ans1.time = OTime(msec=45_000)

    _add_leg_result(leg1, [split1, split_tt1, split_ans1], 1, 50_000)

    leg2_result = ResultManual()
    leg2_result.person = leg2
    leg2_result.status = ResultStatus.DID_NOT_FINISH
    leg2_result.splits = []
    race().results.append(leg2_result)

    recalculate_results(recheck_results=True)

    team = find(race().relay_teams, bib_number=1)
    assert team is not None
    assert team.get_trailo_time().to_msec() == 40_000 + 60_000 + 60_000 + 60_000


def test_relay_preo_team_result_is_sum_of_leg_trailo_times():
    group, leg1, leg2 = _setup_relay_preo()

    split1 = Split()
    split1.code = "31A"
    split1.is_correct = True
    split1.time = OTime(msec=20_000)
    split1.course_index = 0
    split_tt1 = Split()
    split_tt1.code = "1TT"
    split_tt1.is_correct = True
    split_tt1.time = OTime(msec=40_000)
    split_tt1.course_index = 1
    split_ans1 = Split()
    split_ans1.code = "1T1A"
    split_ans1.is_correct = True
    split_ans1.time = OTime(msec=45_000)
    split_ans1.course_index = 2

    split2 = Split()
    split2.code = "31A"
    split2.is_correct = True
    split2.time = OTime(msec=25_000)
    split2.course_index = 0
    split_tt2 = Split()
    split_tt2.code = "1TT"
    split_tt2.is_correct = True
    split_tt2.time = OTime(msec=70_000)
    split_tt2.course_index = 1
    split_ans2 = Split()
    split_ans2.code = "1T1A"
    split_ans2.is_correct = True
    split_ans2.time = OTime(msec=75_000)
    split_ans2.course_index = 2

    _add_leg_result(leg1, [split1, split_tt1, split_ans1], 1, 50_000)
    _add_leg_result(leg2, [split2, split_tt2, split_ans2], 1, 80_000)

    RaceSplits(race()).generate()
    for result in race().results:
        TrailoResultChecker.process(result, lambda *args, **kwargs: 0)
    ResultCalculation(race()).process_results()

    team = find(race().relay_teams, bib_number=1)
    assert team is not None
    assert team.get_trailo_time().to_msec() == 110_000
    assert get_team_result(leg1).to_msec() == 110_000
    assert race().find_person_result(leg1).get_result_relay()

    leg1_result = race().find_person_result(leg1)
    leg2_result = race().find_person_result(leg2)
    assert leg1_result.get_result_otime().to_msec() == 40_000
    assert leg2_result.get_result_otime().to_msec() == 70_000
    assert leg1_result.get_result_otime().to_msec() != team.get_trailo_time().to_msec()


def test_relay_preo_recalculate_results_sets_team_trailo_time():
    group, leg1, leg2 = _setup_relay_preo()

    split1 = Split()
    split1.code = "31A"
    split1.is_correct = True
    split1.time = OTime(msec=20_000)
    split_tt1 = Split()
    split_tt1.code = "1TT"
    split_tt1.is_correct = True
    split_tt1.time = OTime(msec=40_000)
    split_ans1 = Split()
    split_ans1.code = "1T1A"
    split_ans1.is_correct = True
    split_ans1.time = OTime(msec=45_000)

    split2 = Split()
    split2.code = "31A"
    split2.is_correct = True
    split2.time = OTime(msec=25_000)
    split_tt2 = Split()
    split_tt2.code = "1TT"
    split_tt2.is_correct = True
    split_tt2.time = OTime(msec=30_000)
    split_ans2 = Split()
    split_ans2.code = "1T1A"
    split_ans2.is_correct = True
    split_ans2.time = OTime(msec=35_000)

    _add_leg_result(leg1, [split1, split_tt1, split_ans1], 1, 50_000)
    _add_leg_result(leg2, [split2, split_tt2, split_ans2], 1, 55_000)

    recalculate_results(recheck_results=True)

    team = find(race().relay_teams, bib_number=1)
    assert team is not None
    assert team.get_trailo_time().to_msec() == 70_000
    assert race().find_person_result(leg1).place == 1


def _assert_relay_trailo_team_sum(trailo_mode: str):
    group, leg1, leg2 = _setup_relay_preo()
    race().set_setting("trailo_mode", trailo_mode)

    split1 = Split()
    split1.code = "31A"
    split1.is_correct = True
    split1.time = OTime(msec=20_000)
    split1.course_index = 0
    split_tt1 = Split()
    split_tt1.code = "1TT"
    split_tt1.is_correct = True
    split_tt1.time = OTime(msec=40_000)
    split_tt1.course_index = 1
    split_ans1 = Split()
    split_ans1.code = "1T1A"
    split_ans1.is_correct = True
    split_ans1.time = OTime(msec=45_000)
    split_ans1.course_index = 2

    split2 = Split()
    split2.code = "31A"
    split2.is_correct = True
    split2.time = OTime(msec=25_000)
    split2.course_index = 0
    split_tt2 = Split()
    split_tt2.code = "1TT"
    split_tt2.is_correct = True
    split_tt2.time = OTime(msec=30_000)
    split_tt2.course_index = 1
    split_ans2 = Split()
    split_ans2.code = "1T1A"
    split_ans2.is_correct = True
    split_ans2.time = OTime(msec=35_000)
    split_ans2.course_index = 2

    _add_leg_result(leg1, [split1, split_tt1, split_ans1], 1, 50_000)
    _add_leg_result(leg2, [split2, split_tt2, split_ans2], 2, 55_000)

    recalculate_results(recheck_results=True)

    team = find(race().relay_teams, bib_number=1)
    assert team is not None
    if trailo_mode == "preo_sprint":
        # leg1 full leg time + leg2 time from previous leg's finish as start
        expected_team_msec = 55_000
    else:
        expected_team_msec = 70_000
    assert team.get_trailo_time().to_msec() == expected_team_msec
    if trailo_mode != "tempo":
        leg1_result = race().find_person_result(leg1)
        leg2_result = race().find_person_result(leg2)
        assert team.get_trailo_score() == (
            leg1_result.trailo_score + leg2_result.trailo_score
        )
    assert str(expected_team_msec // 1000) in race().find_person_result(leg1).get_result_relay()
    assert race().find_person_result(leg1).place == 1


def test_relay_preo_sprint_team_sum():
    _assert_relay_trailo_team_sum("preo_sprint")


def test_relay_tempo_team_sum():
    _assert_relay_trailo_team_sum("tempo")


def test_relay_preo_leg_and_team_passage_times():
    group, leg1, leg2 = _setup_relay_preo()

    split1 = Split()
    split1.code = "31A"
    split1.is_correct = True
    split1.time = OTime(msec=20_000)
    split_tt1 = Split()
    split_tt1.code = "1TT"
    split_tt1.is_correct = True
    split_tt1.time = OTime(msec=40_000)
    split_ans1 = Split()
    split_ans1.code = "1T1A"
    split_ans1.is_correct = True
    split_ans1.time = OTime(msec=45_000)

    split2 = Split()
    split2.code = "31A"
    split2.is_correct = True
    split2.time = OTime(msec=25_000)
    split_tt2 = Split()
    split_tt2.code = "1TT"
    split_tt2.is_correct = True
    split_tt2.time = OTime(msec=70_000)
    split_ans2 = Split()
    split_ans2.code = "1T1A"
    split_ans2.is_correct = True
    split_ans2.time = OTime(msec=75_000)

    _add_leg_result(leg1, [split1, split_tt1, split_ans1], 1, 50_000)
    _add_leg_result(leg2, [split2, split_tt2, split_ans2], 1, 80_000)

    recalculate_results(recheck_results=True)

    team = find(race().relay_teams, bib_number=1)
    assert team is not None
    assert team.get_trailo_leg_passage_time(1).to_msec() == 50_000
    assert team.get_trailo_leg_passage_time(2).to_msec() == 30_000
    leg1_trailo = race().find_person_result(leg1).trailo_time.to_msec()
    leg2_trailo = race().find_person_result(leg2).trailo_time.to_msec()
    assert team.get_trailo_time().to_msec() == leg1_trailo + leg2_trailo
    assert team.get_trailo_passage_time() == team.get_trailo_time()


def test_relay_preo_team_kv_penalty_applied_once_for_whole_team():
    group, leg1, leg2 = _setup_relay_preo()
    group.max_time = OTime(msec=40_000)

    split1 = Split()
    split1.code = "31A"
    split1.is_correct = True
    split1.time = OTime(msec=20_000)
    split_tt1 = Split()
    split_tt1.code = "1TT"
    split_tt1.is_correct = True
    split_tt1.time = OTime(msec=40_000)
    split_ans1 = Split()
    split_ans1.code = "1T1A"
    split_ans1.is_correct = True
    split_ans1.time = OTime(msec=45_000)

    split2 = Split()
    split2.code = "31A"
    split2.is_correct = True
    split2.time = OTime(msec=25_000)
    split_tt2 = Split()
    split_tt2.code = "1TT"
    split_tt2.is_correct = True
    split_tt2.time = OTime(msec=70_000)
    split_ans2 = Split()
    split_ans2.code = "1T1A"
    split_ans2.is_correct = True
    split_ans2.time = OTime(msec=75_000)

    _add_leg_result(leg1, [split1, split_tt1, split_ans1], 2, 50_000)
    _add_leg_result(leg2, [split2, split_tt2, split_ans2], 2, 80_000)

    recalculate_results(recheck_results=True)

    team = find(race().relay_teams, bib_number=1)
    assert team is not None
    leg1_result = race().find_person_result(leg1)
    leg2_result = race().find_person_result(leg2)
    raw = leg1_result.trailo_score + leg2_result.trailo_score
    team_penalty = team.get_trailo_score_penalty()
    assert team_penalty > 0
    assert leg1_result.trailo_score_penalty == team_penalty
    assert leg2_result.trailo_score_penalty == 0
    assert team.get_trailo_score() == raw - team_penalty


def test_relay_preo_team_sort_complete_incomplete_disqualified():
    group, leg1, leg2 = _setup_relay_preo()

    org2 = Organization()
    org2.name = "Team Two"
    leg1_t2 = Person()
    leg1_t2.group = group
    leg1_t2.organization = org2
    leg1_t2.set_bib(1002)
    leg1_t2.name = "T2L1"

    org3 = Organization()
    org3.name = "Team Three"
    leg1_t3 = Person()
    leg1_t3.group = group
    leg1_t3.organization = org3
    leg1_t3.set_bib(1003)
    leg1_t3.name = "T3L1"
    leg2_t3 = Person()
    leg2_t3.group = group
    leg2_t3.organization = org3
    leg2_t3.set_bib(2003)
    leg2_t3.name = "T3L2"
    race().persons.extend([leg1_t2, leg1_t3, leg2_t3])

    def leg_splits(tc_msec):
        s_main = Split()
        s_main.code = "31A"
        s_main.is_correct = True
        s_main.time = OTime(msec=10_000)
        s_tt = Split()
        s_tt.code = "1TT"
        s_tt.is_correct = True
        s_tt.time = OTime(msec=tc_msec)
        s_ans = Split()
        s_ans.code = "1T1A"
        s_ans.is_correct = True
        s_ans.time = OTime(msec=tc_msec + 1000)
        return [s_main, s_tt, s_ans]

    _add_leg_result(leg1, leg_splits(40_000), 1, 50_000)
    _add_leg_result(leg2, leg_splits(30_000), 1, 45_000)
    _add_leg_result(leg1_t2, leg_splits(35_000), 1, 48_000)
    _add_leg_result(leg1_t3, leg_splits(40_000), 1, 50_000)
    leg2_t3_result = ResultManual()
    leg2_t3_result.person = leg2_t3
    leg2_t3_result.status = ResultStatus.DISQUALIFIED
    leg2_t3_result.start_time = OTime(msec=50_000)
    leg2_t3_result.finish_time = OTime(msec=80_000)
    leg2_t3_result.splits = leg_splits(70_000)
    race().results.append(leg2_t3_result)

    recalculate_results(recheck_results=True)

    teams = sorted(race().relay_teams, key=lambda team: team.order)
    assert [team.bib_number for team in teams] == [1, 2, 3]
    assert teams[0].get_is_team_placed()
    assert not teams[1].get_is_team_placed()
    assert teams[1].get_participant_count() == 1
    assert teams[2].get_is_disqualified()
    assert teams[0].place == 1
    assert teams[1].place == 2
    assert teams[2].place == -1


def test_relay_preo_teams_with_equal_trailo_result_share_place():
    group, leg1, leg2 = _setup_relay_preo()

    # Team 1
    org1 = leg1.organization
    leg1b = Person()
    leg1b.group = group
    leg1b.organization = org1
    leg1b.set_bib(2001)
    leg1b.name = "T1L2"
    race().persons.append(leg1b)

    # Team 2 — same trailo totals as team 1
    org2 = Organization()
    org2.name = "Team Beta"
    leg3 = Person()
    leg3.group = group
    leg3.organization = org2
    leg3.set_bib(1002)
    leg3.name = "T2L1"
    leg4 = Person()
    leg4.group = group
    leg4.organization = org2
    leg4.set_bib(2002)
    leg4.name = "T2L2"
    race().persons.extend([leg3, leg4])

    def leg_splits(tc_msec):
        s_main = Split()
        s_main.code = "31A"
        s_main.is_correct = True
        s_main.time = OTime(msec=10_000)
        s_tt = Split()
        s_tt.code = "1TT"
        s_tt.is_correct = True
        s_tt.time = OTime(msec=tc_msec)
        s_ans = Split()
        s_ans.code = "1T1A"
        s_ans.is_correct = True
        s_ans.time = OTime(msec=tc_msec + 1000)
        return [s_main, s_tt, s_ans]

    _add_leg_result(leg1, leg_splits(40_000), 1, 50_000)
    _add_leg_result(leg1b, leg_splits(30_000), 1, 45_000)
    _add_leg_result(leg3, leg_splits(40_000), 1, 50_000)
    _add_leg_result(leg4, leg_splits(30_000), 1, 45_000)

    RaceSplits(race()).generate()
    for result in race().results:
        TrailoResultChecker.process(result, lambda *args, **kwargs: 0)
    ResultCalculation(race()).process_results()

    team1 = find(race().relay_teams, bib_number=1)
    team2 = find(race().relay_teams, bib_number=2)
    assert team1.get_trailo_time() == team2.get_trailo_time()
    assert team1.place == 1
    assert team2.place == 1
