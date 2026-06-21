"""Integration test for the SportOrg TrailO Excel plugin process."""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

import pytest

from sportorg.modules.plugins.manager import PluginConfig, PluginProcess

from fixtures_preo import setup_preo_group

PLUGIN_ID = "sportorg.trailo.excel_protocol"


class PluginCallbacks:
    def __init__(self, output_dir: str) -> None:
        self.output_dir = output_dir
        self.initialized = False
        self.plugin_id = ""
        self.notifications = []

    def get_plugin_settings(self, plugin_id: str):
        if plugin_id == PLUGIN_ID:
            return {"output_dir": self.output_dir, "open_after_save": False}
        return {}

    def plugin_initialized(
        self,
        config_index,
        plugin_id,
        plugin_name,
        plugin_version,
        returned_settings,
    ) -> None:
        self.initialized = True
        self.plugin_id = plugin_id

    def plugin_settings_updated(self, plugin_id, plugin_settings) -> None:
        pass

    def plugin_notification(self, level: str, message: str) -> None:
        self.notifications.append({"level": level, "message": message})

    def plugin_entity_update(self, process, request_id, method, params) -> None:
        pass

    def plugin_menu_updated(self) -> None:
        pass


def _wait_until(condition, timeout: float = 8.0) -> None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return
        time.sleep(0.05)
    raise TimeoutError("condition not met")


def test_plugin_exports_excel_from_current_race() -> None:
    setup_preo_group()

    with tempfile.TemporaryDirectory() as tmp_dir:
        callbacks = PluginCallbacks(tmp_dir)
        process = PluginProcess(
            PluginConfig(
                index=0,
                executable_path=sys.executable,
                arguments="-m trailo_protocols.plugin_main",
                enabled=True,
                plugin_id=PLUGIN_ID,
            ),
            callbacks,
        )

        try:
            process.start()
            _wait_until(lambda: callbacks.initialized)
            _wait_until(lambda: bool(process.get_menu_entries()))

            assert callbacks.plugin_id == PLUGIN_ID
            menu_ids = {item["id"] for item in process.get_menu_entries()}
            assert "export_without_answers" in menu_ids
            assert "export_with_answers" in menu_ids

            response = process.send_request(
                "plugin.menu.execute",
                {
                    "id": "export_without_answers",
                    "language": "en_US",
                    "context": {},
                },
                timeout=60,
            )
            assert "error" not in response

            xlsx_files = list(Path(tmp_dir).glob("*.xlsx"))
            assert xlsx_files, "expected an .xlsx file in {}".format(tmp_dir)
        finally:
            process.stop()
