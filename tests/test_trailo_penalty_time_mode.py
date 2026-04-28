from sportorg.models.memory import Race, create, new_event, race
from sportorg.modules.trailo.result_checker import TrailoResultChecker


def create_race() -> None:
    new_event([create(Race)])


def test_custom_trailo_penalty_time_used_when_enabled() -> None:
    create_race()
    race().set_setting("trailo_custom_penalty_time_enabled", True)
    race().set_setting("trailo_time_penalty", 45)
    race().set_setting("trailo_mode", "preo")

    assert TrailoResultChecker.get_penalty_time_for_mode().to_msec() == 45000


def test_trailo_penalty_time_preo_default_when_custom_disabled() -> None:
    create_race()
    race().set_setting("trailo_custom_penalty_time_enabled", False)
    race().set_setting("trailo_time_penalty", 5)
    race().set_setting("trailo_mode", "preo")

    assert TrailoResultChecker.get_penalty_time_for_mode().to_msec() == 60000


def test_trailo_penalty_time_tempo_default_when_custom_disabled() -> None:
    create_race()
    race().set_setting("trailo_custom_penalty_time_enabled", False)
    race().set_setting("trailo_time_penalty", 5)
    race().set_setting("trailo_mode", "tempo")

    assert TrailoResultChecker.get_penalty_time_for_mode().to_msec() == 30000


def test_trailo_penalty_time_preo_sprint_default_when_custom_disabled() -> None:
    create_race()
    race().set_setting("trailo_custom_penalty_time_enabled", False)
    race().set_setting("trailo_time_penalty", 5)
    race().set_setting("trailo_mode", "preo_sprint")

    assert TrailoResultChecker.get_penalty_time_for_mode().to_msec() == 0
