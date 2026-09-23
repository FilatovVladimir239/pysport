import logging
from typing import Optional
from typing import Optional

from sportorg.models.memory import (
    Course,
    CourseControl,
    Group,
    Qualification,
    ResultStatus,
    Split,
)
from sportorg.models.result.result_calculation import ResultCalculation
from sportorg.modules.trailo.codes import (
    expand_trailo_control_code_strings,
    parse_trailo_code,
    trailo_first_split_for_control,
    trailo_sort_key,
)
from sportorg.utils.time import get_speed_min_per_km


class PersonSplits:
    def __init__(self, r, result):
        self.race = r
        self.result = result
        self._course = None
        self.last_correct_index = 0
        self._legs = []

        self.assigned_rank = self._get_assigned_rank()
        self.relay_leg = self.result.person.bib // 1000 if self.result.person else 0

    def _get_assigned_rank(self):
        """Получение назначенного разряда"""
        if (
            hasattr(self.result, "assigned_rank")
            and self.result.assigned_rank != Qualification.NOT_QUALIFIED
        ):
            return self.result.assigned_rank.get_title()
        return ""

    @property
    def person(self):
        return self.result.person

    @property
    def course(self):
        if self._course is None:
            self._course = self.race.find_course(self.result) or Course()
        return self._course

    def generate(self):
        processing_mode = self.race.get_setting("result_processing_mode", "time")

        mode_handlers = {
            "trailo": self._generate_trailo_splits,
            "default": self._generate_standard_splits,
        }

        handler = mode_handlers.get(processing_mode, mode_handlers["default"])
        handler()
        self._legs = [None] * (self.last_correct_index + 1)
        for split in self.result.splits:
            index = split.course_index
            if 0 <= index < len(self._legs) and self._legs[index] is None:
                self._legs[index] = split

        return self

    def _generate_trailo_splits(self):
        self.result.splits = [s for s in self.result.splits if s.code[-1] != "X"]
        self.result.splits.sort(key=trailo_sort_key)

        for split in self.result.splits:
            split.course_index = -1
            split.is_correct = False

        codes_expanded = expand_trailo_control_code_strings(
            [str(c.code) for c in self.course.controls]
        )
        orig_by_code = {str(c.code): c for c in self.course.controls}
        expanded_controls = []
        for code in codes_expanded:
            if code in orig_by_code:
                expanded_controls.append(orig_by_code[code])
            else:
                cc = CourseControl()
                cc.code = code
                cc.length = 0
                expanded_controls.append(cc)

        for course_index, control in enumerate(expanded_controls):
            self._process_trailo_control(control, course_index)

        self.result.splits.sort(key=trailo_sort_key)

    def _process_trailo_control(self, control, course_index: int):
        code = str(control.code)
        split = trailo_first_split_for_control(self.result.splits, code)
        if split is not None:
            self._update_trailo_split(split, control, course_index)
        else:
            self._add_missing_trailo_control(control, course_index)

    def _trailo_control_is_time_punch(self, control) -> bool:
        code = str(control.code)
        if not code:
            return False
        parsed = parse_trailo_code(code)
        if parsed.kind == "tc_time":
            return True
        return code[-1] == "T"

    def _update_trailo_split(self, split, control, course_index: int):
        split.course_index = course_index
        if self._trailo_control_is_time_punch(control):
            split.leg_time = split.time
        else:
            split.is_correct = split.code[-1] == control.code[-1]

    def _add_missing_trailo_control(self, control, course_index: int):
        code = str(control.code)
        new_split = Split()
        new_split.code = code[:-1] + "X" if code else "X"
        new_split.is_correct = False
        new_split.course_index = course_index
        self.result.splits.append(new_split)

    def _generate_standard_splits(self):
        if self.course.length:
            self.result.speed = get_speed_min_per_km(
                self.result.get_result_otime(), self.course.length
            )

        start_time = self.result.get_start_time()
        for split in self.result.splits:
            split.relative_time = split.time - start_time

        if not self.course.controls:
            self._process_splits_without_controls(start_time)
            self.last_correct_index = -1
        else:
            self._process_splits_with_controls(start_time)

    def _process_splits_without_controls(self, start_time):
        prev_time = start_time
        for i, split in enumerate(self.result.splits):
            split.index = i
            split.course_index = i
            split.leg_time = split.time - prev_time
            prev_time = split.time

    def _process_splits_with_controls(self, start_time):
        split_index = 0
        course_index = 0
        leg_start_time = start_time

        while split_index < len(self.result.splits) and course_index < len(
            self.course.controls
        ):
            current_split = self.result.splits[split_index]
            current_split.index = split_index

            if current_split.is_correct:
                self._update_correct_split(current_split, course_index, leg_start_time)
                leg_start_time = current_split.time
                course_index += 1

            split_index += 1

        self.last_correct_index = course_index - 1

    def _update_correct_split(self, split, course_index, leg_start_time):
        split.leg_time = split.time - leg_start_time
        split.course_index = course_index

        control = self.course.controls[course_index]
        split.length_leg = control.length
        if split.length_leg:
            split.speed = get_speed_min_per_km(split.leg_time, split.length_leg)

        split.leg_place = 0

    def get_last_correct_index(self):
        return self.last_correct_index

    def get_leg_by_course_index(self, index):
        if index > self.last_correct_index:
            return None
        if 0 <= index < len(self._legs):
            return self._legs[index]
        return None

    def get_leg_time(self, index):
        leg = self.get_leg_by_course_index(index)
        return leg.leg_time if leg else None

    def get_leg_relative_time(self, index):
        leg = self.get_leg_by_course_index(index)
        return leg.relative_time if leg else None

    def to_dict(self):
        return {
            "person": self.person.to_dict(),
            "result": self.result.to_dict(),
            "course": self.course.to_dict(),
        }


class GroupSplits:
    def __init__(self, r, group, calculation: Optional[ResultCalculation] = None):
        self.race = r
        self.group = group
        self.cp_count = len(self.group.course.controls) if self.group.course else 0

        self.person_splits = []

        self.leader = {}

        if calculation is None:
            calculation = ResultCalculation(r)
        self._calculation = calculation

    def generate(self, logged=False):
        if logged:
            logging.debug("Group splits generate for " + self.group.name)
        # to have group count
        self._calculation.get_group_persons(self.group)

        for i in self._calculation.get_group_finishes(self.group):
            self.person_splits.append(PersonSplits(self.race, i).generate())

        self.set_places()
        if self.group.is_relay():
            self.sort_by_place()
        else:
            self.sort_by_result()
        return self

    def set_places(self):
        for index in range(self.cp_count):
            entries = []
            missing = []
            for person_split in self.person_splits:
                leg = person_split.get_leg_by_course_index(index)
                if leg is not None:
                    entries.append((person_split, leg))
                else:
                    missing.append(person_split)

            if not entries:
                continue

            entries.sort(key=lambda entry: entry[1].leg_time)
            self._assign_places(entries, "leg_time", "leg_place")
            self.set_leg_leader(index, entries[0][0])
            self.person_splits = [entry[0] for entry in entries] + missing

            entries.sort(key=lambda entry: entry[1].relative_time)
            self._assign_places(entries, "relative_time", "relative_place")
            self.person_splits = [entry[0] for entry in entries] + missing

    @staticmethod
    def _assign_places(entries, time_attr, place_attr):
        # competition ranking: equal times share a place, next place skips
        leader_time = getattr(entries[0][1], time_attr)
        double_places_counter = 0
        prev_time = leader_time
        for i, entry in enumerate(entries):
            leg = entry[1]
            leg_time = getattr(leg, time_attr)
            if i != 0 and prev_time == leg_time:
                double_places_counter += 1
            else:
                double_places_counter = 0

            setattr(leg, place_attr, i + 1 - double_places_counter)
            if place_attr == "leg_place":
                leg.leader_time = leader_time
            prev_time = leg_time

    def sort_by_result(self):
        status_priority = [
            ResultStatus.OVERTIME.value,
            ResultStatus.MISSING_PUNCH.value,
            ResultStatus.DISQUALIFIED.value,
            ResultStatus.DID_NOT_FINISH.value,
            ResultStatus.DID_NOT_START.value,
        ]

        def sort_func(item):
            priority = 0
            if item.result.status in status_priority:
                priority = status_priority.index(item.result.status) + 1
            return item.result is None, priority, item.result

        self.person_splits = sorted(self.person_splits, key=sort_func)

    def sort_by_place(self):
        self.person_splits = sorted(
            self.person_splits,
            key=lambda item: (
                item.result.get_place() is None or item.result.get_place() == "",
                ("0000" + str(item.result.get_place()))[-4:],
                int(item.relay_leg),
            ),
        )

    def set_leg_leader(self, index, person_split):
        self.leader[str(index)] = (
            person_split.person.name,
            person_split.get_leg_time(index),
        )

    def get_leg_leader(self, index):
        if str(index) in self.leader.keys():
            return self.leader[str(index)]
        return "", ""

    def to_dict(self):
        return [ps.to_dict() for ps in self.person_splits]


class RaceSplits:
    def __init__(self, r, calculation: Optional[ResultCalculation] = None):
        self.race = r
        if calculation is None:
            calculation = ResultCalculation(r)
        self._calculation = calculation

    def generate(self, group: Optional[Group] = None):
        if group is None:
            for group in self.race.groups:
                GroupSplits(self.race, group, self._calculation).generate()
        else:
            GroupSplits(self.race, group, self._calculation).generate()

        return self
