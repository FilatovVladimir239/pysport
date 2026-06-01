"""Desktop window for TrailO Excel protocol export."""
from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, List, Optional

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QDialogButtonBox,
        QFileDialog,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )
except ModuleNotFoundError:
    from PySide2.QtCore import Qt
    from PySide2.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QDialogButtonBox,
        QFileDialog,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

from sportorg.modules.reports.trailo_protocol import TrailoProtocolOptions

from trailo_protocols.excel import default_excel_filename, save_trailo_protocol_excel
from trailo_protocols.excel_script import resolve_excel_script_path, run_excel_export_script
from trailo_protocols.loader import load_event_file, race_label

logger = logging.getLogger(__name__)

_SETTINGS: Dict[str, Any] = {
    "last_event_file": "",
    "last_output_dir": "",
    "show_answers": False,
    "open_after_save": True,
    "use_custom_script": False,
    "custom_script": "",
}


def _is_trailo_race(race_dict: Dict[str, Any]) -> bool:
    settings = race_dict.get("settings") or {}
    return settings.get("result_processing_mode") == "trailo"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._race_dicts: List[Dict[str, Any]] = []
        self._build_ui()

    def _build_ui(self) -> None:
        self.setWindowTitle("TrailO — протокол Excel")
        self.resize(640, 220)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        form = QFormLayout()

        event_row = QHBoxLayout()
        self.event_path = QLineEdit()
        self.event_path.setReadOnly(True)
        self.event_path.setPlaceholderText("Файл базы SportOrg (.json)")
        if _SETTINGS["last_event_file"]:
            self.event_path.setText(_SETTINGS["last_event_file"])
        browse_event = QPushButton("Обзор…")
        browse_event.clicked.connect(self._browse_event_file)
        event_row.addWidget(self.event_path)
        event_row.addWidget(browse_event)
        form.addRow("База SportOrg:", event_row)

        self.race_combo = QComboBox()
        self.race_combo.setEnabled(False)
        form.addRow("Заезд:", self.race_combo)

        self.show_answers = QCheckBox("Включить ответы")
        self.show_answers.setChecked(_SETTINGS["show_answers"])
        form.addRow(self.show_answers)

        self.open_after_save = QCheckBox("Открыть файл после сохранения")
        self.open_after_save.setChecked(_SETTINGS["open_after_save"])
        form.addRow(self.open_after_save)

        script_row = QHBoxLayout()
        self.use_custom_script = QCheckBox("Скрипт экспорта (.py)")
        self.use_custom_script.setChecked(_SETTINGS["use_custom_script"])
        self.use_custom_script.toggled.connect(self._toggle_custom_script)
        self.custom_script = QLineEdit()
        self.custom_script.setReadOnly(True)
        self.custom_script.setEnabled(_SETTINGS["use_custom_script"])
        if _SETTINGS["custom_script"]:
            self.custom_script.setText(_SETTINGS["custom_script"])
        browse_script = QPushButton("Обзор…")
        browse_script.clicked.connect(self._browse_script)
        script_row.addWidget(self.use_custom_script)
        script_row.addWidget(self.custom_script, 1)
        script_row.addWidget(browse_script)
        form.addRow(script_row)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.Ok).setText("Сохранить Excel…")
        buttons.button(QDialogButtonBox.Cancel).setText("Выход")
        buttons.accepted.connect(self._export)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

        if self.event_path.text():
            self._load_event(self.event_path.text())

    def _toggle_custom_script(self, enabled: bool) -> None:
        self.custom_script.setEnabled(enabled)

    def _browse_event_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Открыть базу SportOrg",
            _SETTINGS["last_event_file"] or os.path.expanduser("~"),
            "SportOrg (*.json *.json.gz);;JSON (*.json);;All (*.*)",
        )
        if path:
            self.event_path.setText(path)
            self._load_event(path)

    def _browse_script(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Скрипт экспорта Excel",
            _SETTINGS["custom_script"] or os.path.expanduser("~"),
            "Python (*.py);;All (*.*)",
        )
        if path:
            self.custom_script.setText(path)
            self.use_custom_script.setChecked(True)

    def _load_event(self, path: str) -> None:
        try:
            race_dicts, current = load_event_file(path)
        except Exception as exc:
            logger.exception("Failed to load %s", path)
            QMessageBox.critical(
                self,
                "Ошибка",
                "Не удалось открыть файл:\n{}".format(exc),
            )
            return

        _SETTINGS["last_event_file"] = path
        self._race_dicts = race_dicts
        self.race_combo.clear()
        for index, race_dict in enumerate(race_dicts):
            label = race_label(race_dict, index)
            if not _is_trailo_race(race_dict):
                label += " (не TrailO)"
            self.race_combo.addItem(label, index)
        self.race_combo.setEnabled(bool(race_dicts))
        if race_dicts:
            self.race_combo.setCurrentIndex(min(current, len(race_dicts) - 1))

    def _export(self) -> None:
        if not self._race_dicts:
            QMessageBox.warning(self, "Нет данных", "Сначала откройте файл базы SportOrg.")
            return

        index = self.race_combo.currentData()
        if index is None:
            index = self.race_combo.currentIndex()
        race_dict = self._race_dicts[int(index)]

        if not _is_trailo_race(race_dict):
            answer = QMessageBox.question(
                self,
                "Режим заезда",
                "В этом заезде не включён режим TrailO. Всё равно сформировать протокол?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        default_name = default_excel_filename(race_dict)
        start_dir = _SETTINGS["last_output_dir"] or os.path.dirname(
            self.event_path.text() or ""
        )
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить протокол Excel",
            os.path.join(start_dir, default_name + ".xlsx"),
            "Excel (*.xlsx)",
        )
        if not file_name:
            return
        if not file_name.lower().endswith(".xlsx"):
            file_name = file_name + ".xlsx"

        show_answers = self.show_answers.isChecked()
        _SETTINGS["show_answers"] = show_answers
        _SETTINGS["open_after_save"] = self.open_after_save.isChecked()
        _SETTINGS["use_custom_script"] = self.use_custom_script.isChecked()
        _SETTINGS["custom_script"] = self.custom_script.text()
        _SETTINGS["last_output_dir"] = os.path.dirname(os.path.abspath(file_name))

        try:
            if self.use_custom_script.isChecked():
                script_path = resolve_excel_script_path(
                    self.custom_script.text(), os.getcwd()
                )
                run_excel_export_script(
                    script_path,
                    race_dict,
                    file_name,
                    show_answers=show_answers,
                )
            else:
                save_trailo_protocol_excel(
                    race_dict,
                    file_name,
                    options=TrailoProtocolOptions(show_answers=show_answers),
                )
        except Exception as exc:
            logger.exception("Export failed")
            QMessageBox.critical(
                self,
                "Ошибка",
                "Не удалось сохранить протокол:\n{}".format(exc),
            )
            return

        if self.open_after_save.isChecked():
            try:
                os.startfile(file_name)
            except OSError:
                pass


def run() -> int:
    logging.basicConfig(level=logging.INFO)
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    window = MainWindow()
    window.show()
    return app.exec_()
