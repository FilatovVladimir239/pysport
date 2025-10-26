import logging
from typing import Optional

from sportorg.models.memory import Course, Group, Qualification, ResultStatus, Split
from sportorg.models.result.result_calculation import ResultCalculation
from sportorg.utils.time import get_speed_min_per_km


class PersonSplits:
    def __init__(self, r, result):
        self.race = r
        self.result = result
        self._course = None
        self.last_correct_index = 0

        self.assigned_rank = self._get_assigned_rank()
        self.relay_leg = self.result.person.bib // 1000 if self.result.person else 0

    def _get_assigned_rank(self):
        """Получение назначенного разряда"""
        if (hasattr(self.result, "assigned_rank") and
                self.result.assigned_rank != Qualification.NOT_QUALIFIED):
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
            "default": self._generate_standard_splits
        }

        handler = mode_handlers.get(processing_mode, mode_handlers["default"])
        handler()

        return self

    def _generate_trailo_splits(self):
        self.result.splits = [
            s for s in self.result.splits if s.code[-1] != 'X'
        ]
        self.result.splits.sort(key=lambda s: (int(s.code[:-1]), s.time))

        for split in self.result.splits:
            split.course_index = -1
            split.is_correct = False

        for control in self.course.controls:
            self._process_trailo_control(control)

        self.result.splits.sort(key=lambda s: (int(s.code[:-1]), s.time))

    def _process_trailo_control(self, control):
        control_detected = False

        for split in self.result.splits:
            if split.code[:-1] == control.code[:-1]:
                control_detected = True
                self._update_trailo_split(split, control)
                break

        if not control_detected:
            self._add_missing_trailo_control(control)

    def _update_trailo_split(self, split, control):
        if control.code[:-1] == "T":
            split.leg_time = split.time
        else:
            split.course_index = int(control.code[:-1])
            split.is_correct = (split.code[-1] == control.code[-1])

    def _add_missing_trailo_control(self, control):
        new_split = Split()
        if control.code[:-1] != "T":
            new_split.code = control.code[:-1] + "X"
            new_split.is_correct = False
            new_split.course_index = int(control.code[:-1])
        else:
            new_split.code = control.code
            new_split.is_correct = False
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

        while (split_index < len(self.result.splits) and
               course_index < len(self.course.controls)):

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
        return next((split for split in self.result.splits
                     if split.course_index == index), None)

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
    def __init__(self, r, group):
        self.race = r
        self.group = group
        self.cp_count = len(self.group.course.controls) if self.group.course else 0
        self.person_splits = []
        self.leader = {}

    def generate(self, logged=False):
        if logged:
            logging.debug(f"Group splits generate for {self.group.name}")

        ResultCalculation(self.race).get_group_persons(self.group)
        finishes = ResultCalculation(self.race).get_group_finishes(self.group)

        self.person_splits = [
            PersonSplits(self.race, result).generate()
            for result in finishes
        ]

        self._set_places()
        self._sort_results()

        return self

    def _set_places(self):
        for i in range(self.cp_count):
            self._sort_by_leg(i)
            self._set_places_for_leg(i)
            self._set_leg_leader(i)

            self._sort_by_leg(i, relative=True)
            self._set_places_for_leg(i, relative=True)

    def _sort_by_leg(self, index, relative=False):
        self.person_splits.sort(
            key=lambda item: (
                item.get_leg_relative_time(index) is None if relative else item.get_leg_time(index) is None,
                item.get_leg_relative_time(index) if relative and item.get_leg_relative_time(index) is not None else
                item.get_leg_time(index) if not relative and item.get_leg_time(index) is not None else
                float('inf')
            )
        )

    def _sort_results(self):
        if self.group.is_relay():
            self._sort_by_place()
        else:
            self._sort_by_result()

    def _sort_by_result(self):
        status_priority = [
            ResultStatus.OVERTIME.value,
            ResultStatus.MISSING_PUNCH.value,
            ResultStatus.DISQUALIFIED.value,
            ResultStatus.DID_NOT_FINISH.value,
            ResultStatus.DID_NOT_START.value,
        ]

        def sort_key(item):
            priority = 0
            if item.result.status in status_priority:
                priority = status_priority.index(item.result.status) + 1
            return item.result is None, priority, item.result

        self.person_splits.sort(key=sort_key)

    def _sort_by_place(self):
        self.person_splits.sort(
            key=lambda item: (
                item.result.get_place() is None or item.result.get_place() == "",
                ("0000" + str(item.result.get_place()))[-4:],
                item.relay_leg,
            )
        )

    def _set_places_for_leg(self, index, relative=False):
        if not self.person_splits:
            return

        time_attr = 'relative_time' if relative else 'leg_time'
        place_attr = 'relative_place' if relative else 'leg_place'

        leader_time = getattr(self.person_splits[0].get_leg_by_course_index(index),
                              time_attr, None) if self.person_splits[0].get_leg_by_course_index(index) else None

        double_places_counter = 0
        prev_time = leader_time

        for i, person in enumerate(self.person_splits):
            leg = person.get_leg_by_course_index(index)
            if not leg:
                continue

            current_time = getattr(leg, time_attr)

            if i > 0 and prev_time == current_time:
                double_places_counter += 1
            else:
                double_places_counter = 0

            setattr(leg, place_attr, i + 1 - double_places_counter)

            if not relative:
                leg.leader_time = leader_time

            prev_time = current_time

    def _set_leg_leader(self, index):
        if self.person_splits:
            leader = self.person_splits[0]
            self.leader[str(index)] = (
                leader.person.name,
                leader.get_leg_time(index)
            )

    def get_leg_leader(self, index):
        return self.leader.get(str(index), ("", ""))

    def to_dict(self):
        return [ps.to_dict() for ps in self.person_splits]


class RaceSplits:
    def __init__(self, r):
        self.race = r

    def generate(self, group: Optional[Group] = None):
        groups = [group] if group else self.race.groups

        for grp in groups:
            GroupSplits(self.race, grp).generate()

        return self
