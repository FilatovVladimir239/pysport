"""TrailO race settings: preset modes and alternate course layout."""

from typing import Optional, Tuple

from sportorg.models.memory import Race, Result, race

SETTING_ALTERNATE_COURSE = "trailo_alternate_course"
SETTING_LEGACY_CUSTOM_PENALTY = "trailo_custom_penalty_time_enabled"
SETTING_MAIN_COURSE = "trailo_main_course_enabled"
SETTING_MAIN_POINTS = "trailo_main_course_points_enabled"
SETTING_MAIN_WRONG_ANSWER = "trailo_main_course_wrong_answer_penalty_enabled"
SETTING_STATION = "trailo_station_enabled"
SETTING_STATION_PENALTY = "trailo_time_penalty"
SETTING_WRONG_ANSWER_PENALTY = "trailo_wrong_answer_penalty"
SETTING_MODE = "trailo_mode"


class TrailoConfig:
    @staticmethod
    def _race(r: Optional[Race] = None) -> Race:
        return r if r is not None else race()

    @staticmethod
    def alternate_course_enabled(r: Optional[Race] = None) -> bool:
        return bool(TrailoConfig._race(r).get_setting(SETTING_ALTERNATE_COURSE, False))

    @staticmethod
    def legacy_custom_penalty_enabled(r: Optional[Race] = None) -> bool:
        return bool(
            TrailoConfig._race(r).get_setting(SETTING_LEGACY_CUSTOM_PENALTY, False)
        )

    @staticmethod
    def main_course_enabled(r: Optional[Race] = None) -> bool:
        obj = TrailoConfig._race(r)
        if not TrailoConfig.alternate_course_enabled(obj):
            return True
        return bool(obj.get_setting(SETTING_MAIN_COURSE, True))

    @staticmethod
    def points_enabled(r: Optional[Race] = None) -> bool:
        obj = TrailoConfig._race(r)
        if TrailoConfig.alternate_course_enabled(obj):
            return TrailoConfig.main_course_enabled(obj) and bool(
                obj.get_setting(SETTING_MAIN_POINTS, True)
            )
        return obj.get_setting(SETTING_MODE, "preo_sprint") != "tempo"

    @staticmethod
    def wrong_answer_penalty_enabled(r: Optional[Race] = None) -> bool:
        obj = TrailoConfig._race(r)
        if TrailoConfig.alternate_course_enabled(obj):
            return TrailoConfig.main_course_enabled(obj) and bool(
                obj.get_setting(SETTING_MAIN_WRONG_ANSWER, False)
            )
        if bool(obj.get_setting(SETTING_LEGACY_CUSTOM_PENALTY, False)):
            return int(obj.get_setting(SETTING_WRONG_ANSWER_PENALTY, 0)) > 0
        return False

    @staticmethod
    def station_enabled(r: Optional[Race] = None) -> bool:
        obj = TrailoConfig._race(r)
        if TrailoConfig.alternate_course_enabled(obj):
            return bool(obj.get_setting(SETTING_STATION, True))
        mode = obj.get_setting(SETTING_MODE, "preo_sprint")
        return mode != "preo_sprint"

    @staticmethod
    def uses_passage_time(r: Optional[Race] = None) -> bool:
        return not TrailoConfig.station_enabled(r)

    @staticmethod
    def legacy_mode(r: Optional[Race] = None) -> str:
        return TrailoConfig._race(r).get_setting(SETTING_MODE, "preo_sprint")

    @staticmethod
    def score_penalty_interval_minutes(r: Optional[Race] = None) -> int:
        if TrailoConfig.alternate_course_enabled(r):
            return 5
        return 5 if TrailoConfig.legacy_mode(r) == "preo" else 1

    @staticmethod
    def station_penalty_sec(r: Optional[Race] = None) -> int:
        obj = TrailoConfig._race(r)
        if TrailoConfig.alternate_course_enabled(obj):
            if not TrailoConfig.station_enabled(obj):
                return 0
            return int(obj.get_setting(SETTING_STATION_PENALTY, 0))
        if TrailoConfig.legacy_custom_penalty_enabled(obj):
            return int(obj.get_setting(SETTING_STATION_PENALTY, 0))
        mode = TrailoConfig.legacy_mode(obj)
        if mode == "preo":
            return 60
        if mode == "tempo":
            return 30
        return 0

    @staticmethod
    def wrong_answer_penalty_sec(r: Optional[Race] = None) -> int:
        obj = TrailoConfig._race(r)
        if not TrailoConfig.wrong_answer_penalty_enabled(obj):
            return 0
        return int(obj.get_setting(SETTING_WRONG_ANSWER_PENALTY, 0))

    @staticmethod
    def place_comparison_key(res: Result, r: Optional[Race] = None) -> Tuple:
        if TrailoConfig.points_enabled(r):
            return (res.trailo_score, res.get_trailo_time().to_msec())
        return (res.get_trailo_time().to_msec(),)

    @staticmethod
    def relay_team_place_key(team, r: Optional[Race] = None) -> Tuple:
        if TrailoConfig.points_enabled(r):
            return (team.get_trailo_score(), team.get_trailo_time().to_msec())
        return (team.get_trailo_time().to_msec(),)

    @staticmethod
    def show_points_in_result(r: Optional[Race] = None) -> bool:
        return TrailoConfig.points_enabled(r)

    @staticmethod
    def show_time_as_seconds(r: Optional[Race] = None) -> bool:
        obj = TrailoConfig._race(r)
        if TrailoConfig.alternate_course_enabled(obj):
            return TrailoConfig.station_enabled(obj)
        return TrailoConfig.legacy_mode(obj) != "preo_sprint"

    @staticmethod
    def show_elapsed_time_on_split_printout(r: Optional[Race] = None) -> bool:
        obj = TrailoConfig._race(r)
        if TrailoConfig.alternate_course_enabled(obj):
            return TrailoConfig.points_enabled(obj) or TrailoConfig.uses_passage_time(
                obj
            )
        return TrailoConfig.legacy_mode(obj) != "tempo"
