import logging

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtWidgets import QAbstractItemView, QTextEdit
except ModuleNotFoundError:
    from PySide2 import QtCore, QtGui, QtWidgets
    from PySide2.QtWidgets import QAbstractItemView, QTextEdit

from sportorg.common.otime import OTime
from sportorg.gui.dialogs.result_edit import ResultEditDialog
from sportorg.gui.global_access import GlobalAccess
from sportorg.gui.tabs.memory_model import ResultMemoryModel
from sportorg.gui.tabs.table import TableView
from sportorg.language import translate
from sportorg.models.memory import Result, race
from sportorg.utils.time import time_to_hhmmss


class ResultsTable(TableView):
    def __init__(self, parent, obj):
        super().__init__(obj)

        self.parent_widget = parent
        self.setObjectName("ResultTable")

        self.setModel(ResultMemoryModel())
        self.setSortingEnabled(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.clicked.connect(self.entry_single_clicked)
        self.activated.connect(self.double_clicked)

        self.popup_items = []

    def update_splits(self):
        if -1 < self.currentIndex().row() < len(race().results):
            self.parent_widget.show_splits(self.currentIndex())

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        try:
            if event.key() in (QtCore.Qt.Key_Up, QtCore.Qt.Key_Down):
                self.entry_single_clicked(self.currentIndex())
        except Exception as e:
            logging.error(str(e))

    def entry_single_clicked(self, index):
        try:
            if -1 < index.row() < len(race().results):
                self.parent_widget.show_splits(index)
        except Exception as e:
            logging.error(str(e))

    def double_clicked(self, index):
        try:
            logging.debug("Clicked on %s", str(index.row()))
            if index.row() < len(race().results):
                dialog = ResultEditDialog(race().results[index.row()])
                dialog.exec_()
                GlobalAccess().get_main_window().refresh()
        except Exception as e:
            logging.error(str(e))


class Widget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.result_card_form = QtWidgets.QFormLayout()
        self.result_course_form = QtWidgets.QFormLayout()
        self.grid_layout = QtWidgets.QGridLayout(self)
        self.result_splitter = QtWidgets.QSplitter(self)
        self.result_course_group_box = QtWidgets.QGroupBox(self.result_splitter)
        self.result_card_group_box = QtWidgets.QGroupBox(self.result_splitter)
        self.result_table = ResultsTable(self, self.result_splitter)
        self.result_card_details = QtWidgets.QTextBrowser(self.result_card_group_box)
        self.result_card_finish_edit = QtWidgets.QLineEdit(self.result_card_group_box)
        self.result_card_finish_label = QtWidgets.QLabel(self.result_card_group_box)
        self.result_card_start_edit = QtWidgets.QLineEdit(self.result_card_group_box)
        self.result_card_start_label = QtWidgets.QLabel(self.result_card_group_box)
        self.vertical_layout_card = QtWidgets.QVBoxLayout(self.result_card_group_box)
        self.result_course_details = QtWidgets.QTextBrowser(
            self.result_course_group_box
        )
        self.result_course_length_edit = QtWidgets.QLineEdit(
            self.result_course_group_box
        )
        self.result_course_length_label = QtWidgets.QLabel(self.result_course_group_box)
        self.result_course_name_edit = QtWidgets.QLineEdit(self.result_course_group_box)
        self.result_course_name_label = QtWidgets.QLabel(self.result_course_group_box)
        self.vertical_layout_course = QtWidgets.QVBoxLayout(
            self.result_course_group_box
        )
        self.setup_ui()

    def setup_ui(self):
        self.result_splitter.setOrientation(QtCore.Qt.Horizontal)
        self.result_course_name_edit.setAlignment(QtCore.Qt.AlignLeft)
        self.result_course_name_edit.setMinimumWidth(46)
        self.result_course_length_edit.setMinimumWidth(46)
        self.result_splitter.setStretchFactor(2, 100)
        self.result_splitter.setSizes([100, 195, self.result_table.maximumWidth()])

        self.vertical_layout_course.setContentsMargins(0, 0, 0, 0)
        self.vertical_layout_course.setSpacing(0)
        self.result_course_form.setWidget(
            0, QtWidgets.QFormLayout.LabelRole, self.result_course_name_label
        )
        self.result_course_name_edit.setReadOnly(True)
        self.result_course_form.setWidget(
            0, QtWidgets.QFormLayout.FieldRole, self.result_course_name_edit
        )
        self.result_course_form.setWidget(
            1, QtWidgets.QFormLayout.LabelRole, self.result_course_length_label
        )
        self.result_course_length_edit.setReadOnly(True)
        self.result_course_form.setWidget(
            1, QtWidgets.QFormLayout.FieldRole, self.result_course_length_edit
        )
        self.vertical_layout_course.addLayout(self.result_course_form)

        font = QtGui.QFont()
        font.setFamily("Courier New")
        self.result_course_details.setFont(font)
        self.vertical_layout_course.addWidget(self.result_course_details)
        self.vertical_layout_card.setContentsMargins(0, 0, 0, 0)
        self.vertical_layout_card.setSpacing(0)
        self.result_card_form.setWidget(
            0, QtWidgets.QFormLayout.LabelRole, self.result_card_start_label
        )
        self.result_card_start_edit.setReadOnly(True)
        self.result_card_form.setWidget(
            0, QtWidgets.QFormLayout.FieldRole, self.result_card_start_edit
        )
        self.result_card_form.setWidget(
            1, QtWidgets.QFormLayout.LabelRole, self.result_card_finish_label
        )
        self.result_card_finish_edit.setReadOnly(True)
        self.result_card_form.setWidget(
            1, QtWidgets.QFormLayout.FieldRole, self.result_card_finish_edit
        )
        self.vertical_layout_card.addLayout(self.result_card_form)
        self.result_card_details.setLineWrapMode(QTextEdit.NoWrap)
        font = QtGui.QFont()
        font.setFamily("Courier New")
        self.result_card_details.setFont(font)
        self.vertical_layout_card.addWidget(self.result_card_details)

        self.grid_layout.addWidget(self.result_splitter)
        self.result_course_group_box.setTitle(translate("Course"))
        self.result_course_name_label.setText(translate("Name"))
        self.result_course_length_label.setText(translate("Length"))
        self.result_card_group_box.setTitle(translate("Chip"))
        self.result_card_start_label.setText(translate("Start"))
        self.result_card_finish_label.setText(translate("Finish"))

        self.result_course_group_box.setMinimumHeight(150)
        self.result_card_group_box.setMinimumHeight(150)

    def show_splits(self, index):
        result: Result = race().results[index.row()]
        is_trailo = race().get_setting("result_processing_mode", "time") == "trailo"

        self._clear_display_fields()

        if result.is_manual():
            return

        course = race().find_course(result) if result.person else None
        control_codes = self._get_control_codes(course) if course else []

        time_accuracy = race().get_setting("time_accuracy", 0)

        self._display_start_time(result, time_accuracy)

        if is_trailo:
            self._display_trailo_splits(result, time_accuracy)
        else:
            is_highlight = not course.is_unknown() if course else False
            self._display_standard_splits(result, time_accuracy, is_highlight, control_codes)

        self._display_finish_time(result, time_accuracy)

        self.result_card_finish_edit.setText(time_to_hhmmss(result.get_finish_time()))
        self.result_card_start_edit.setText(time_to_hhmmss(result.get_start_time()))

        self._display_course_info(course, result)

    def _clear_display_fields(self):
        fields = [
            self.result_card_details,
            self.result_card_finish_edit,
            self.result_card_start_edit,
            self.result_course_details,
            self.result_course_name_edit,
            self.result_course_length_edit
        ]
        for field in fields:
            if hasattr(field, 'clear'):
                field.clear()
            elif hasattr(field, 'setText'):
                field.setText("")

    def _get_control_codes(self, course):
        return [str(control.code) for control in course.controls] if course else []

    def _display_start_time(self, result, time_accuracy):
        start_time = result.get_start_time()
        start_str = "{name:<8} {time}".format(
            name=translate("Start"),
            time=start_time.to_str(time_accuracy)
        )
        self.result_card_details.append(start_str)

    def _display_finish_time(self, result, time_accuracy):
        finish_time = result.get_finish_time()
        finish_str = "{name:<8} {time}".format(
            name=translate("Finish"),
            time=finish_time.to_str(time_accuracy),
        )
        self.result_card_details.append(finish_str)

    def _display_trailo_splits(self, result, time_accuracy):
        str_fmt_correct = "{code} {answer} {time}"
        str_fmt_incorrect = "--   {answer} {time}"

        result.splits = sorted(result.splits, key=lambda s: (int(s.code[:-1]), s.time))

        for split in result.splits:
            str_fmt = str_fmt_incorrect if split.course_index == -1 else str_fmt_correct
            s = str_fmt.format(
                code="(" + "{:0>2}".format(str(split.code[:-1])) + ")",
                answer=split.code[-1],
                time=split.time.to_str(time_accuracy)
            )
            self.result_card_details.append(s)

    def _display_standard_splits(self, result, time_accuracy, is_highlight, control_codes):
        code = ""
        last_correct_time = OTime()
        str_fmt_correct = "{index:02d} {code} {time} {diff}"
        str_fmt_incorrect = "-- {code} {time}"
        index = 1
        for split in result.splits:
            str_fmt = str_fmt_incorrect if not split.is_correct else str_fmt_correct
            s = str_fmt.format(
                index=index,
                code=("(" + str(split.code) + ")   ")[:5],
                time=split.time.to_str(time_accuracy),
                diff=split.leg_time.to_str(time_accuracy),
                leg_place=split.leg_place,
                speed=split.speed,
            )
            if split.is_correct:
                index += 1
                last_correct_time = split.time

            s = self._highlight_problem_splits(s, split, code, is_highlight, control_codes)

            self.result_card_details.append(s)
            code = split.code

        finish_time = result.get_finish_time()
        finish_leg = finish_time - last_correct_time
        finish_str = "{name:<8} {time} {diff}".format(
            name=translate("Finish"),
            time=finish_time.to_str(time_accuracy),
            diff=finish_leg.to_str(time_accuracy),
        )
        self.result_card_details.append(finish_str)

    def _highlight_problem_splits(self, s, split, last_code, is_highlight, control_codes):
        if split.code == last_code:
            s = '<span style="background: red">{}</span>'.format(s)
        elif is_highlight and control_codes and split.code not in control_codes:
            s = '<span style="background: yellow">{}</span>'.format(s)
        return s

    def _display_course_info(self, course, result):
        split_codes = [split.code for split in result.splits]

        self.result_course_details.append(translate("Start"))

        if course:
            for i, control in enumerate(course.controls, 1):
                s = "{index:02d} ({code}) {length}".format(
                    index=i,
                    code=control.code,
                    length=control.length if control.length else "",
                )
                if not course.is_unknown() and str(control.code) not in split_codes:
                    s = '<span style="background: yellow">{}</span>'.format(s)
                self.result_course_details.append(s)

            self.result_course_name_edit.setText(course.name)
            self.result_course_name_edit.setCursorPosition(0)
            self.result_course_length_edit.setText(str(course.length))

        self.result_course_details.append(translate("Finish"))