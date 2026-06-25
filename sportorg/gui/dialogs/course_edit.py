import logging
from typing import List

from sportorg.gui.dialogs.dialog import BaseDialog, LineField, NumberField, TextField
from sportorg.gui.global_access import GlobalAccess
from sportorg.language import translate
from sportorg.models.memory import CourseControl, race
from sportorg.models.result.course_control_rules import (
    format_control_chain_bonuses,
    format_control_start_delay_minutes,
    format_rogaine_course_control_codes,
    parse_control_chain_bonuses,
    parse_control_start_delay_minutes,
    parse_rogaine_course_control_codes,
)
from sportorg.models.result.result_tools import recalculate_results
from sportorg.modules.teamwork.teamwork import Teamwork


class CourseEditDialog(BaseDialog):
    def __init__(self, course, is_new=False):
        super().__init__(GlobalAccess().get_main_window())
        self.current_object = course
        self.is_new = is_new
        self.is_rogaine = race().get_setting("result_processing_mode", "time") == "scores"
        self.title = translate("Course properties")
        self.size = (400, 480 if self.is_rogaine else 420)
        self.form = [
            LineField(
                title=translate("Name"),
                object=course,
                key="name",
                id="name",
                select_all=True,
            ),
            NumberField(
                title=translate("Length(m)"),
                object=course,
                key="length",
                maximum=100000,
                single_step=100,
            ),
            NumberField(
                id="climb",
                title=translate("Climb"),
                object=course,
                key="climb",
                maximum=10000,
                single_step=10,
            ),
            NumberField(
                title=translate("Point count"),
                maximum=1000,
                is_disabled=True,
                id="point_count",
            ),
            TextField(
                title=self._controls_field_title(),
                tooltip=self._controls_field_tooltip(),
                object=course,
                key="controls",
                id="controls",
            ),
        ]
        if self.is_rogaine:
            self.form.extend(
                [
                    TextField(
                        title=translate("CP restrictions after start"),
                        tooltip=translate(
                            "Format: code minutes, e.g. '45 60' = CP 45 only after 60 min from start."
                        ),
                        object=course,
                        key="control_start_delay_minutes",
                        id="control_start_delay_minutes",
                    ),
                    TextField(
                        title=translate("Consecutive control chain bonus"),
                        tooltip=translate(
                            "Format: code code ... bonus, e.g. '45 67 32 5' = +5 if 45,67,32 taken in a row."
                        ),
                        object=course,
                        key="control_chain_bonuses",
                        id="control_chain_bonuses",
                    ),
                ]
            )

    def _controls_field_title(self) -> str:
        if self.is_rogaine:
            return "{}\n\n31\n32\n33\n...\n90".format(translate("Controls"))
        return "{}\n\n31 150\n32 200\n33\n34 500\n...\n90 150".format(
            translate("Controls")
        )

    def _controls_field_tooltip(self) -> str:
        if self.is_rogaine:
            return translate(
                "One code per line. Empty = all punched controls count toward the score."
            )
        return ""

    def before_showing(self) -> None:
        self.on_controls_changed()

    def convert_controls(self, controls) -> List[str]:
        if self.is_rogaine:
            allowed = getattr(self.current_object, "allowed_control_codes", None) or []
            return format_rogaine_course_control_codes(controls, allowed)
        result: List[str] = []
        for i in controls:
            result.append("{} {}".format(i.code, i.length if i.length else ""))
        return result

    def parse_controls(self, text: str):
        if self.is_rogaine:
            codes = parse_rogaine_course_control_codes(text)
            self.current_object.allowed_control_codes = list(codes)
            return [self._make_control(code) for code in codes]

        controls = []
        for i in text.split("\n"):
            control = CourseControl()
            if i is None or len(i) == 0:
                continue
            control.code = i.split()[0]
            if len(i.split()) > 1:
                try:
                    control.length = int(i.split()[1])
                except Exception as e:
                    logging.error(str(e))
                    control.length = 0
            controls.append(control)
        return controls

    @staticmethod
    def _make_control(code: str) -> CourseControl:
        control = CourseControl()
        control.code = code
        return control

    def convert_control_start_delay_minutes(self, rules):
        return format_control_start_delay_minutes(rules or {})

    def parse_control_start_delay_minutes(self, text: str):
        return parse_control_start_delay_minutes(text)

    def convert_control_chain_bonuses(self, chains):
        return format_control_chain_bonuses(chains or [])

    def parse_control_chain_bonuses(self, text: str):
        return parse_control_chain_bonuses(text)

    def on_controls_changed(self):
        text = self.fields["controls"].q_item.toPlainText()
        if self.is_rogaine:
            self.fields["point_count"].q_item.setValue(
                len(parse_rogaine_course_control_codes(text))
            )
            return
        self.fields["point_count"].q_item.setValue(len(self.parse_controls(text)))

    def on_name_changed(self):
        name = self.fields["name"].q_item.text()
        self.button_ok.setDisabled(False)
        if name and name != self.current_object.name:
            if name in race().course_index_name:
                self.button_ok.setDisabled(True)

    def apply(self):
        obj = race()
        self.current_object.index_name()
        if self.is_new:
            obj.courses.insert(0, self.current_object)
        recalculate_results()
        Teamwork().send(self.current_object.to_dict())
