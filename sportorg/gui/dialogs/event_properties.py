import logging

try:
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import (
        QDateTimeEdit,
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QTextEdit,
        QWidget,
    )
except ModuleNotFoundError:
    from PySide2.QtGui import QIcon
    from PySide2.QtWidgets import (
        QDateTimeEdit,
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QTextEdit,
        QWidget,
    )

from sportorg import config
from sportorg.common.signature_images import (
    signature_image_filter_text,
    store_signature_image,
)
from sportorg.gui.dialogs.file_dialog import get_open_file_name
from sportorg.gui.global_access import GlobalAccess
from sportorg.gui.utils.custom_controls import AdvComboBox, AdvSpinBox
from sportorg.language import translate
from sportorg.models.memory import RaceType, race
from sportorg.models.result.result_tools import recalculate_results


class EventPropertiesDialog(QDialog):
    def __init__(self):
        super().__init__(GlobalAccess().get_main_window())

    def exec_(self):
        self.init_ui()
        return super().exec_()

    def init_ui(self):
        self.setFixedWidth(500)
        self.setWindowTitle(translate("Event properties"))
        self.setWindowIcon(QIcon(config.ICON))
        self.setSizeGripEnabled(False)
        self.setModal(True)

        self.layout = QFormLayout(self)

        self.label_main_title = QLabel(translate("Main title") + " 🛈")
        self.label_main_title.setToolTip(
            translate(
                "Main event name. This will be used in the printout\nsplit header and in some printed protocols."
            )
        )
        self.item_main_title = QLineEdit()
        self.layout.addRow(self.label_main_title, self.item_main_title)

        self.label_sub_title = QLabel(translate("Sub title") + " 🛈")
        self.label_sub_title.setToolTip(
            translate(
                "The sub title of the event. It will be used\nin the header of the printed protocol."
            )
        )
        self.item_sub_title = QTextEdit()
        self.item_sub_title.setMaximumHeight(100)
        self.item_sub_title.setTabChangesFocus(True)
        self.layout.addRow(self.label_sub_title, self.item_sub_title)

        self.label_short_title = QLabel(translate("Short title") + " 🛈")
        self.label_short_title.setToolTip(
            translate(
                "Brief operator-only label. Shown in the window\ntitle and event list, not printed in protocols."
            )
        )
        self.item_short_title = QLineEdit()
        self.layout.addRow(self.label_short_title, self.item_short_title)

        self.label_start_date = QLabel(translate("Start date"))
        self.item_start_date = QDateTimeEdit()
        self.item_start_date.setDisplayFormat("yyyy.MM.dd HH:mm:ss")
        self.layout.addRow(self.label_start_date, self.item_start_date)

        self.label_end_date = QLabel(translate("End date"))
        # self.item_end_date = QCalendarWidget()
        self.item_end_date = QDateTimeEdit()
        self.item_end_date.setDisplayFormat("yyyy.MM.dd HH:mm:ss")
        self.layout.addRow(self.label_end_date, self.item_end_date)

        self.label_location = QLabel(translate("Location"))
        self.item_location = QLineEdit()
        self.layout.addRow(self.label_location, self.item_location)

        self.label_type = QLabel(translate("Event type"))
        self.item_type = AdvComboBox()
        self.item_type.addItems(RaceType.get_titles())
        self.layout.addRow(self.label_type, self.item_type)

        self.label_relay_legs = QLabel(translate("Relay legs"))
        self.item_relay_legs = AdvSpinBox(minimum=1, maximum=20, value=3)
        self.layout.addRow(self.label_relay_legs, self.item_relay_legs)

        self.item_type.currentTextChanged.connect(self.change_type)

        self.label_refery = QLabel(translate("Chief referee"))
        self.item_refery = QLineEdit()
        self.button_chief_signature = QPushButton(translate("Signature"))
        self.button_chief_signature.setFixedWidth(90)
        self.button_clear_chief_signature = QPushButton("×")
        self.button_clear_chief_signature.setFixedWidth(28)
        chief_row = QWidget()
        chief_layout = QHBoxLayout(chief_row)
        chief_layout.setContentsMargins(0, 0, 0, 0)
        chief_layout.addWidget(self.item_refery)
        chief_layout.addWidget(self.button_chief_signature)
        chief_layout.addWidget(self.button_clear_chief_signature)
        self.layout.addRow(self.label_refery, chief_row)
        self.button_chief_signature.clicked.connect(self._pick_chief_signature)
        self.button_clear_chief_signature.clicked.connect(self._clear_chief_signature)

        self.label_secretary = QLabel(translate("Secretary"))
        self.item_secretary = QLineEdit()
        self.button_secretary_signature = QPushButton(translate("Signature"))
        self.button_secretary_signature.setFixedWidth(90)
        self.button_clear_secretary_signature = QPushButton("×")
        self.button_clear_secretary_signature.setFixedWidth(28)
        secretary_row = QWidget()
        secretary_layout = QHBoxLayout(secretary_row)
        secretary_layout.setContentsMargins(0, 0, 0, 0)
        secretary_layout.addWidget(self.item_secretary)
        secretary_layout.addWidget(self.button_secretary_signature)
        secretary_layout.addWidget(self.button_clear_secretary_signature)
        self.layout.addRow(self.label_secretary, secretary_row)
        self.button_secretary_signature.clicked.connect(self._pick_secretary_signature)
        self.button_clear_secretary_signature.clicked.connect(
            self._clear_secretary_signature
        )

        self._chief_signature_path = ""
        self._secretary_signature_path = ""

        self.label_url = QLabel(translate("URL"))
        self.item_url = QLineEdit()
        self.layout.addRow(self.label_url, self.item_url)

        def cancel_changes():
            self.close()

        def apply_changes():
            try:
                self.apply_changes_impl()
            except Exception as e:
                logging.error(str(e))
            self.close()

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_ok = button_box.button(QDialogButtonBox.Ok)
        self.button_ok.setText(translate("OK"))
        self.button_ok.clicked.connect(apply_changes)
        self.button_cancel = button_box.button(QDialogButtonBox.Cancel)
        self.button_cancel.setText(translate("Cancel"))
        self.button_cancel.clicked.connect(cancel_changes)
        self.layout.addRow(button_box)

        self.set_values_from_model()

        self.show()

    def change_type(self):
        flag = self.item_type.currentText() == RaceType.RELAY.get_title()
        self.label_relay_legs.setVisible(flag)
        self.item_relay_legs.setVisible(flag)

    def set_values_from_model(self):
        obj = race()
        self.item_main_title.setText(str(obj.data.title))
        self.item_sub_title.setText(str(obj.data.description))
        self.item_short_title.setText(str(obj.data.short_title))
        self.item_short_title.setPlaceholderText(
            obj.data.get_start_datetime().strftime("%Y-%m-%d")
        )
        self.item_location.setText(str(obj.data.location))
        self.item_url.setText(str(obj.data.url))
        self.item_refery.setText(str(obj.data.chief_referee))
        self.item_secretary.setText(str(obj.data.secretary))
        self._chief_signature_path = str(obj.data.chief_referee_signature_path or "")
        self._secretary_signature_path = str(obj.data.secretary_signature_path or "")
        self._update_signature_buttons()
        self.item_start_date.setDateTime(obj.data.get_start_datetime())
        self.item_end_date.setDateTime(obj.data.get_end_datetime())
        self.item_type.setCurrentText(obj.data.race_type.get_title())
        self.item_relay_legs.setValue(obj.data.relay_leg_count)
        self.change_type()

    def apply_changes_impl(self):
        obj = race()

        start_date = self.item_start_date.dateTime().toPython()
        end_date = self.item_end_date.dateTime().toPython()

        obj.data.title = self.item_main_title.text()
        obj.data.description = self.item_sub_title.toPlainText()
        obj.data.short_title = self.item_short_title.text()
        obj.data.description = obj.data.description.replace("\n", "<br>\n")
        obj.data.location = self.item_location.text()
        obj.data.url = self.item_url.text()
        obj.data.chief_referee = self.item_refery.text()
        obj.data.secretary = self.item_secretary.text()
        obj.data.chief_referee_signature_path = self._chief_signature_path
        obj.data.secretary_signature_path = self._secretary_signature_path
        obj.data.start_datetime = start_date
        obj.data.end_datetime = end_date

        old_race_type = obj.data.race_type
        new_race_type = RaceType.get_by_name(self.item_type.currentText())
        if new_race_type and new_race_type != old_race_type:
            obj.data.race_type = new_race_type
            for group in obj.groups:
                group.race_type = new_race_type

        obj.data.relay_leg_count = self.item_relay_legs.value()

        obj.set_setting("system_zero_time", (start_date.hour, start_date.minute, 0))

        recalculate_results()
        GlobalAccess().get_main_window().set_title()
        GlobalAccess().get_main_window().refresh()

    def _update_signature_buttons(self) -> None:
        chief_path = self._chief_signature_path.strip()
        secretary_path = self._secretary_signature_path.strip()
        self.button_chief_signature.setToolTip(chief_path or translate("Choose signature image"))
        self.button_secretary_signature.setToolTip(
            secretary_path or translate("Choose signature image")
        )
        self.button_clear_chief_signature.setEnabled(bool(chief_path))
        self.button_clear_secretary_signature.setEnabled(bool(secretary_path))

    def _pick_chief_signature(self) -> None:
        self._pick_signature("chief_referee", "_chief_signature_path")

    def _pick_secretary_signature(self) -> None:
        self._pick_signature("secretary", "_secretary_signature_path")

    def _pick_signature(self, role: str, attr_name: str) -> None:
        file_name = get_open_file_name(
            translate("Choose signature image"),
            signature_image_filter_text(),
        )
        if not file_name:
            return
        try:
            saved_path = store_signature_image(file_name, role)
        except OSError as error:
            logging.error("Cannot save signature image: %s", error)
            return
        setattr(self, attr_name, saved_path)
        self._update_signature_buttons()

    def _clear_chief_signature(self) -> None:
        self._chief_signature_path = ""
        self._update_signature_buttons()

    def _clear_secretary_signature(self) -> None:
        self._secretary_signature_path = ""
        self._update_signature_buttons()
