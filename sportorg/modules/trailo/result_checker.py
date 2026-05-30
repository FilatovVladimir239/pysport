from typing import Callable, Tuple

from sportorg.common.otime import OTime
from sportorg.models.memory import Person, Result, race
from sportorg.modules.trailo.codes import (
    expand_trailo_control_code_strings,
    parse_trailo_code,
    trailo_first_split_for_control,
)
from sportorg.modules.trailo.config import TrailoConfig


class TrailoResultChecker:
    """Проверка и расчёт полей TrailO (очки, время, штрафы по тайм‑КП)."""

    @staticmethod
    def process(
        result: Result,
        calculate_rogaine_penalty: Callable[[Result, int, int], int],
    ) -> None:
        if TrailoConfig.alternate_course_enabled():
            TrailoResultChecker._process_alternate_course(
                result, calculate_rogaine_penalty
            )
        else:
            TrailoResultChecker._process_legacy_mode(
                result, calculate_rogaine_penalty
            )

    @staticmethod
    def _process_legacy_mode(
        result: Result,
        calculate_rogaine_penalty: Callable[[Result, int, int], int],
    ) -> None:
        trailo_mode = TrailoConfig.legacy_mode()

        if trailo_mode != "tempo":
            scores = TrailoResultChecker.calculate_scores_trailo(result)
            if trailo_mode == "preo" and result.is_trailo_relay_leg():
                trailo_score_penalty = 0
                trailo_score = scores
            else:
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
            TrailoResultChecker._set_trailo_time_station_based(result, trailo_mode)
        else:
            TrailoResultChecker._set_trailo_time_passage(result)

    @staticmethod
    def _process_alternate_course(
        result: Result,
        calculate_rogaine_penalty: Callable[[Result, int, int], int],
    ) -> None:
        if TrailoConfig.points_enabled():
            scores = TrailoResultChecker.calculate_scores_trailo(result)
            penalty = calculate_rogaine_penalty(
                result,
                scores,
                1,
                TrailoConfig.score_penalty_interval_minutes(),
            )
            result.trailo_score_penalty = penalty
            result.trailo_score = scores - penalty
        else:
            result.trailo_score_penalty = 0
            result.trailo_score = 0

        if TrailoConfig.station_enabled():
            TrailoResultChecker._set_trailo_time_station_based(result, None)
        else:
            TrailoResultChecker._set_trailo_time_passage(result)

    @staticmethod
    def _set_trailo_time_station_based(result: Result, trailo_mode) -> None:
        time = TrailoResultChecker.calculate_time_trailo(result)
        time_penalty = TrailoResultChecker.calculate_time_penalty(result)
        trailo_time_msec = time.to_msec() + time_penalty.to_msec()
        apply_main_wrong_penalty = False
        if TrailoConfig.wrong_answer_penalty_enabled():
            if TrailoConfig.alternate_course_enabled():
                apply_main_wrong_penalty = True
            elif trailo_mode == "preo" and result.is_trailo_relay_leg():
                apply_main_wrong_penalty = True
        if apply_main_wrong_penalty:
            main_errors = TrailoResultChecker.count_main_course_errors(result)
            wrong_answer_penalty = (
                TrailoResultChecker.get_wrong_answer_penalty_for_mode()
            )
            trailo_time_msec += wrong_answer_penalty.to_msec() * main_errors
        result.trailo_time = OTime(msec=trailo_time_msec)

    @staticmethod
    def _set_trailo_time_passage(result: Result) -> None:
        if result.is_trailo_relay_leg():
            result.trailo_time = result.get_result_otime_current_day()
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
            cur_split = trailo_first_split_for_control(
                result.splits, str(control_point.code)
            )
            if cur_split is not None:
                sp = parse_trailo_code(str(cur_split.code))
                if (
                    sp.kind == "main"
                    and sp.main_num is not None
                    and sp.main_num == cp.main_num
                    and cur_split.is_correct
                ):
                    matched = True
            if not matched:
                error_count += 1
        return error_count

    @staticmethod
    def calculate_time_penalty(result: Result) -> OTime:
        if not TrailoConfig.station_enabled():
            return OTime()
        if not result.person or not result.person.group:
            return OTime()
        course = race().find_course(result)
        if not course:
            return OTime()
        return TrailoResultChecker.penalty_time_calculation_trailo(
            result.splits, course.controls
        )

    @staticmethod
    def get_penalty_time_for_mode() -> OTime:
        return OTime(sec=TrailoConfig.station_penalty_sec())

    @staticmethod
    def get_wrong_answer_penalty_for_mode() -> OTime:
        return OTime(sec=TrailoConfig.wrong_answer_penalty_sec())

    @staticmethod
    def penalty_time_calculation_trailo(splits, controls) -> OTime:
        res = OTime()
        penalty_time = TrailoResultChecker.get_penalty_time_for_mode()

        for control_point in controls:
            cp = parse_trailo_code(str(control_point.code))
            if cp.kind != "tc_answer" or cp.tc_idx is None or cp.tc_task is None:
                continue
            cur_split = trailo_first_split_for_control(
                splits, str(control_point.code)
            )
            if cur_split is None:
                continue
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
        return res

    @staticmethod
    def calculate_scores_trailo(result: Result) -> int:
        if not TrailoConfig.main_course_enabled():
            return 0
        course = race().find_course(result)
        if not course:
            return 0
        ret = 0
        for control_point in course.controls:
            cp = parse_trailo_code(str(control_point.code))
            if cp.kind != "main" or cp.main_num is None or not cp.main_answer:
                continue
            cur_split = trailo_first_split_for_control(
                result.splits, str(control_point.code)
            )
            if cur_split is None:
                continue
            sp = parse_trailo_code(str(cur_split.code))
            if sp.kind != "main" or sp.main_num is None or not sp.main_answer:
                continue
            if (
                sp.main_num == cp.main_num
                and sp.main_answer == cp.main_answer
                and cur_split.course_index != -1
            ):
                ret += 1
        return ret

    @staticmethod
    def calculate_time_trailo(result: Result) -> OTime:
        ret = 0
        for cur_split in result.splits:
            sp = parse_trailo_code(str(cur_split.code))
            if sp.kind == "tc_time":
                ret += cur_split.time.to_msec()
        return OTime(msec=ret)

    @staticmethod
    def _station_task_counts_by_idx(expanded_codes):
        tasks_by_idx = {}
        for code in expanded_codes:
            cp = parse_trailo_code(code)
            if cp.kind == "tc_answer" and cp.tc_idx is not None:
                tasks_by_idx[cp.tc_idx] = tasks_by_idx.get(cp.tc_idx, 0) + 1
        return tasks_by_idx

    @staticmethod
    def calculate_max_missing_relay_leg_trailo_time(course) -> OTime:
        """
        Worst-case TrailO time for a missing relay leg: per station max time on TT
        (station penalty * task count; TT is not an answer) plus the same penalty
        for all wrong task answers, plus main-course wrong-answer penalties.
        """
        if course is None:
            return OTime()
        station_penalty_msec = TrailoConfig.station_penalty_sec() * 1000
        wrong_penalty_msec = TrailoConfig.wrong_answer_penalty_sec() * 1000
        expanded_codes = expand_trailo_control_code_strings(
            [str(c.code) for c in course.controls]
        )
        msec = 0
        if TrailoConfig.station_enabled():
            tasks_by_idx = TrailoResultChecker._station_task_counts_by_idx(
                expanded_codes
            )
            for tasks in tasks_by_idx.values():
                if not tasks:
                    continue
                msec += station_penalty_msec * tasks
                msec += station_penalty_msec * tasks
        if TrailoConfig.wrong_answer_penalty_enabled():
            for code in expanded_codes:
                cp = parse_trailo_code(code)
                if cp.kind == "main" and cp.main_num is not None and cp.main_answer:
                    msec += wrong_penalty_msec
        return OTime(msec=msec)

    @staticmethod
    def calculate_max_penalty_time_for_course(course) -> OTime:
        return TrailoResultChecker.calculate_max_missing_relay_leg_trailo_time(course)

    @staticmethod
    def synthetic_missing_relay_leg_values(
        person: Person,
        calculate_rogaine_penalty: Callable[[Result, int, int], int],
    ) -> Tuple[int, OTime]:
        """
        TrailO score/time for relay leg 2+ with no valid result: all answers as X.
        """
        from sportorg.models.memory import ResultManual, ResultStatus
        from sportorg.models.result.split_calculation import PersonSplits

        result = ResultManual()
        result.person = person
        result.status = ResultStatus.OK
        result.splits = []
        result.start_time = OTime()
        result.finish_time = OTime()
        PersonSplits(race(), result).generate()
        TrailoResultChecker.process(result, calculate_rogaine_penalty)
        course = race().find_course(result)
        if course:
            floor = TrailoResultChecker.calculate_max_missing_relay_leg_trailo_time(
                course
            )
            if floor.to_msec() > result.get_trailo_time().to_msec():
                result.trailo_time = floor
        return result.trailo_score, result.get_trailo_time()
