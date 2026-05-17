from sportorg.models.memory import Race, new_event, race
from sportorg.modules.trailo.result_checker import TrailoResultChecker


def create_race() -> None:
    new_event([Race()])


def test_custom_trailo_penalty_time_used_when_enabled() -> None:
    create_race()
    race().set_setting("trailo_custom_penalty_time_enabled", True)
    race().set_setting("trailo_time_penalty", 45)
    race().set_setting("trailo_mode", "preo")

    assert TrailoResultChecker.get_penalty_time_for_mode().to_msec() == 45000


def test_trailo_station_penalty_preo_default_when_custom_disabled() -> None:
    create_race()
    race().set_setting("trailo_custom_penalty_time_enabled", False)
    race().set_setting("trailo_time_penalty", 5)
    race().set_setting("trailo_wrong_answer_penalty", 60)
    race().set_setting("trailo_mode", "preo")

    assert TrailoResultChecker.get_penalty_time_for_mode().to_msec() == 60000
    assert TrailoResultChecker.get_wrong_answer_penalty_for_mode().to_msec() == 0


def test_trailo_wrong_answer_penalty_used_when_enabled() -> None:
    create_race()
    race().set_setting("trailo_custom_penalty_time_enabled", True)
    race().set_setting("trailo_wrong_answer_penalty", 45)

    assert TrailoResultChecker.get_wrong_answer_penalty_for_mode().to_msec() == 45000


def test_trailo_penalty_time_preo_sprint_default_when_custom_disabled() -> None:
    create_race()
    race().set_setting("trailo_custom_penalty_time_enabled", False)
    race().set_setting("trailo_time_penalty", 5)
    race().set_setting("trailo_mode", "preo_sprint")

    assert TrailoResultChecker.get_penalty_time_for_mode().to_msec() == 0
