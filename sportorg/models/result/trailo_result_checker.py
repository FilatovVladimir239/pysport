from typing import Callable

from sportorg.common.otime import OTime
from sportorg.models.memory import Result, race


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
            penalty = calculate_rogaine_penalty(result, scores, 1)
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
            result.trailo_time = OTime(
                msec=time.to_msec() + time_penalty.to_msec()
            )
        else:
            result.trailo_time = result.get_result_otime()

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
    def penalty_time_calculation_trailo(splits, controls) -> OTime:
        res = OTime()
        penalty_time = OTime(sec=race().get_setting("trailo_time_penalty", 30))

        for control_point in controls:
            code_cp = str(control_point.code)
            if len(code_cp) < 2 or code_cp[-2] != "T":
                continue
            control_point_code = int(code_cp[:-2])
            for cur_split in splits:
                code_sp = str(cur_split.code)
                if len(code_sp) < 2 or code_sp[-2] != "T":
                    continue
                cur_code = int(code_sp[:-2])
                if (
                    cur_code == control_point_code
                    and code_cp[-1] != "T"
                    and code_sp[-1] != code_cp[-1]
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
            code_cp = str(control_point.code)
            if len(code_cp) >= 2 and code_cp[-2] == "T":
                continue
            for cur_split in result.splits:
                code_sp = str(cur_split.code)
                if len(code_sp) < 2 or code_sp[-2] == "T":
                    continue
                cur_code = int(code_sp[:-1])
                if (
                    cur_code == int(code_cp[:-1])
                    and code_sp[-1] == code_cp[-1]
                    and cur_split.course_index != -1
                ):
                    ret += 1
                    break
        return ret

    @staticmethod
    def calculate_time_trailo(result: Result) -> OTime:
        ret = 0
        for cur_split in result.splits:
            code = str(cur_split.code)
            if code.endswith("TT"):
                ret += cur_split.time.to_msec()
        return OTime(msec=ret)
