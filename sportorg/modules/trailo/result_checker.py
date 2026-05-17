from typing import Callable

from sportorg.common.otime import OTime
from sportorg.models.memory import Result, race
from sportorg.modules.trailo.codes import parse_trailo_code

class TrailoResultChecker:
    """Проверка и расчёт полей TrailO (очки, время, штрафы по тайм‑КП)."""

    @staticmethod
    def process(
        result: Result,
        calculate_rogaine_penalty: Callable[[Result, int, int], int],
    ) -> None:
        trailo_mode = race().get_setting("trailo_mode", "preo_sprint")

        if trailo_mode != "tempo":
            scores = TrailoResultChecker.calculate_scores_trailo(result)
            penalty_interval_minutes = 5 if trailo_mode == "preo" else 1
            penalty = calculate_rogaine_penalty(
                result, scores, 1, penalty_interval_minutes
            )
            trailo_score_penalty = penalty
            trailo_score = scores - penalty
        else:
            trailo_score_penalty = 0
            trailo_score = 0

        result.trailo_score_penalty = trailo_score_penalty
        result.trailo_score = trailo_score

        if trailo_mode != "preo_sprint":
            time = TrailoResultChecker.calculate_time_trailo(result)
            time_penalty = TrailoResultChecker.calculate_time_penalty(result)
            trailo_time_msec = time.to_msec() + time_penalty.to_msec()
            if result.is_trailo_preo_relay_leg():
                main_errors = TrailoResultChecker.count_main_course_errors(result)
                wrong_answer_penalty = (
                    TrailoResultChecker.get_wrong_answer_penalty_for_mode()
                )
                trailo_time_msec += wrong_answer_penalty.to_msec() * main_errors
            result.trailo_time = OTime(msec=trailo_time_msec)
        else:
            result.trailo_time = result.get_result_otime()

    @staticmethod
    def count_main_course_errors(result: Result) -> int:
        course = race().find_course(result)
        if not course:
            return 0
        error_count = 0
        for control_point in course.controls:
            cp = parse_trailo_code(str(control_point.code))
            if cp.kind != "main" or cp.main_num is None or not cp.main_answer:
                continue
            matched = False
            for cur_split in result.splits:
                sp = parse_trailo_code(str(cur_split.code))
                if sp.kind != "main" or sp.main_num is None:
                    continue
                if sp.main_num == cp.main_num and cur_split.is_correct:
                    matched = True
                    break
            if not matched:
                error_count += 1
        return error_count

    @staticmethod
    def calculate_time_penalty(result: Result) -> OTime:
        if not result.person or not result.person.group:
            return OTime()
        course = race().find_course(result)
        if not course:
            return OTime()
        return TrailoResultChecker.penalty_time_calculation_trailo(
            result.splits, course.controls
        )

    @staticmethod
    def _custom_penalty_enabled() -> bool:
        return race().get_setting("trailo_custom_penalty_time_enabled", False)

    @staticmethod
    def get_default_station_penalty_sec() -> int:
        trailo_mode = race().get_setting("trailo_mode", "preo_sprint")
        if trailo_mode == "preo":
            return 60
        if trailo_mode == "preo_sprint":
            return 0
        if trailo_mode == "tempo":
            return 30
        return 0

    @staticmethod
    def get_penalty_time_for_mode() -> OTime:
        if not TrailoResultChecker._custom_penalty_enabled():
            return OTime(sec=TrailoResultChecker.get_default_station_penalty_sec())
        return OTime(sec=race().get_setting("trailo_time_penalty", 0))

    @staticmethod
    def get_wrong_answer_penalty_for_mode() -> OTime:
        if not TrailoResultChecker._custom_penalty_enabled():
            return OTime()
        return OTime(sec=race().get_setting("trailo_wrong_answer_penalty", 0))

    @staticmethod
    def penalty_time_calculation_trailo(splits, controls) -> OTime:
        res = OTime()
        penalty_time = TrailoResultChecker.get_penalty_time_for_mode()

        for control_point in controls:
            cp = parse_trailo_code(str(control_point.code))
            if cp.kind != "tc_answer" or cp.tc_idx is None or cp.tc_task is None:
                continue
            for cur_split in splits:
                sp = parse_trailo_code(str(cur_split.code))
                if sp.kind != "tc_answer":
                    continue
                if (
                    sp.tc_idx == cp.tc_idx
                    and sp.tc_task == cp.tc_task
                    and sp.tc_answer
                    and cp.tc_answer
                    and sp.tc_answer != cp.tc_answer
                ):
                    res += penalty_time
                    break
        return res

    @staticmethod
    def calculate_scores_trailo(result: Result) -> int:
        course = race().find_course(result)
        if not course:
            return 0
        ret = 0
        for control_point in course.controls:
            cp = parse_trailo_code(str(control_point.code))
            if cp.kind != "main" or cp.main_num is None or not cp.main_answer:
                continue
            for cur_split in result.splits:
                sp = parse_trailo_code(str(cur_split.code))
                if sp.kind != "main" or sp.main_num is None or not sp.main_answer:
                    continue
                if (
                    sp.main_num == cp.main_num
                    and sp.main_answer == cp.main_answer
                    and cur_split.course_index != -1
                ):
                    ret += 1
                    break
        return ret

    @staticmethod
    def calculate_time_trailo(result: Result) -> OTime:
        ret = 0
        for cur_split in result.splits:
            sp = parse_trailo_code(str(cur_split.code))
            if sp.kind == "tc_time":
                ret += cur_split.time.to_msec()
        return OTime(msec=ret)
