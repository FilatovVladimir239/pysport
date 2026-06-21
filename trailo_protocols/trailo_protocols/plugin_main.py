"""SportOrg stdio plugin: TrailO Excel protocol export."""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

import orjson

from trailo_protocols.export_core import (
    build_output_path,
    default_plugin_settings,
    export_trailo_excel,
    is_trailo_race,
)
from trailo_protocols.race_sync import apply_entity_notification
from trailo_protocols.signature_images import migrate_signature_settings_from_race
from trailo_protocols.text_utils import (
    parse_json_line,
    safe_json_dumps,
    sanitize_value,
)
from trailo_protocols.selection import filter_race_by_context

PLUGIN_INFO = {
    "id": "sportorg.trailo.excel_protocol",
    "name": "TrailO Protocols (Excel)",
    "version": "0.2.0",
}

MENU_EXPORT_WITH_ANSWERS = "export_with_answers"
MENU_EXPORT_WITHOUT_ANSWERS = "export_without_answers"

CAPABILITIES = {
    "menu": True,
    "race_updates": True,
    "result_updates": True,
    "person_updates": True,
    "group_updates": True,
    "organization_updates": True,
    "course_updates": True,
    "settings": True,
}


class TrailoProtocolsPlugin:
    def __init__(self) -> None:
        self.settings: Dict[str, Any] = default_plugin_settings()
        self.race: Dict[str, Any] = {}
        self._request_id = 0

    def handle_request(self, message: Dict[str, Any]) -> None:
        method = str(message.get("method", ""))
        request_id = message.get("id")
        params = message.get("params", {})
        if not isinstance(params, dict):
            self.write_error(request_id, -32602, "Invalid params")
            return

        if method == "plugin.initialize":
            self._handle_initialize(request_id, params)
            return

        if method == "plugin.menu.get":
            self.write_result(request_id, {"items": self._menu_items()})
            return

        if method == "plugin.menu.execute":
            self._handle_menu_execute(request_id, params)
            return

        self.write_error(request_id, -32601, "Method not found")

    def handle_notification(self, message: Dict[str, Any]) -> None:
        method = str(message.get("method", ""))
        if method == "plugin.shutdown":
            raise SystemExit(0)

        params = message.get("params", {})
        if not isinstance(params, dict):
            return

        if method.endswith(".update") and method.startswith("sportorg."):
            self.race = apply_entity_notification(self.race, method, params)

    def _handle_initialize(self, request_id: Any, params: Dict[str, Any]) -> None:
        plugin_settings = params.get("settings", {})
        if isinstance(plugin_settings, dict):
            nested = plugin_settings.get("plugin", {})
            if isinstance(nested, dict):
                merged = default_plugin_settings()
                merged.update(nested)
                self.settings = merged

        race = params.get("race", {})
        if isinstance(race, dict):
            self.race = race
            if "settings" in self.race and isinstance(self.race["settings"], dict):
                self.race["settings"].pop("live_urls", None)
            self.settings = migrate_signature_settings_from_race(
                self.settings, self.race
            )

        self.write_result(
            request_id,
            {
                "plugin": PLUGIN_INFO,
                "capabilities": CAPABILITIES,
                "settings": self.settings,
            },
        )

    def _menu_items(self) -> List[Dict[str, Any]]:
        has_race = bool(self.race)
        return [
            {
                "id": MENU_EXPORT_WITH_ANSWERS,
                "label": "TrailO protocol Excel (with answers)",
                "tooltip": "Save .xlsx with answer columns to the output folder",
                "enabled": has_race,
                "visible": True,
                "group": "TrailO",
                "order": 100,
            },
            {
                "id": MENU_EXPORT_WITHOUT_ANSWERS,
                "label": "TrailO protocol Excel (no answers)",
                "tooltip": "Save .xlsx without answer columns to the output folder",
                "enabled": has_race,
                "visible": True,
                "group": "TrailO",
                "order": 110,
            },
            {
                "id": "open_output_folder",
                "label": "Open TrailO output folder",
                "tooltip": "Open the folder where protocols are saved",
                "enabled": True,
                "visible": True,
                "group": "TrailO",
                "order": 200,
            },
        ]

    def _handle_menu_execute(self, request_id: Any, params: Dict[str, Any]) -> None:
        action_id = str(params.get("id", ""))
        context = params.get("context")

        if action_id == "open_output_folder":
            self._open_output_folder()
            self.write_result(
                request_id,
                {"status": "ok", "message": "Output folder opened"},
            )
            return

        if action_id in (MENU_EXPORT_WITH_ANSWERS, MENU_EXPORT_WITHOUT_ANSWERS):
            show_answers = action_id == MENU_EXPORT_WITH_ANSWERS
            try:
                message = self._export_excel(show_answers=show_answers, context=context)
            except Exception as exc:
                error_text = sanitize_value(str(exc))
                self.show_notification(
                    "error", "TrailO Excel export failed: {}".format(error_text)
                )
                self.write_error(request_id, -32000, error_text)
                return
        else:
            self.write_error(request_id, -32601, "Unknown menu action")
            return

        self.show_notification("info", message)
        self.write_result(
            request_id,
            {
                "status": "ok",
                "message": message,
                "settings": self.settings,
            },
        )

    def _check_trailo_race(self) -> None:
        if not self.race:
            raise RuntimeError("No race data from SportOrg")
        if not is_trailo_race(self.race):
            self.show_notification(
                "warning",
                "Current race is not in TrailO mode; exporting anyway.",
            )

    def _export_excel(self, *, show_answers: bool, context: Any = None) -> str:
        self._check_trailo_race()
        race = filter_race_by_context(self.race, context if isinstance(context, dict) else None)
        race = sanitize_value(race)
        file_name = build_output_path(race, self.settings)
        export_trailo_excel(
            race,
            file_name,
            show_answers=show_answers,
            plugin_settings=self.settings,
            use_custom_script=bool(self.settings.get("use_custom_script")),
            custom_script=str(self.settings.get("custom_script") or ""),
        )
        self._open_file_if_configured(file_name)
        return "Saved: {}".format(file_name)

    def _open_file_if_configured(self, file_name: str) -> None:
        if bool(self.settings.get("open_after_save", True)):
            try:
                os.startfile(file_name)
            except (OSError, AttributeError):
                pass

    def _open_output_folder(self) -> None:
        from trailo_protocols.export_core import resolve_output_dir

        directory = resolve_output_dir(self.settings)
        os.makedirs(directory, exist_ok=True)
        try:
            os.startfile(directory)
        except (OSError, AttributeError):
            pass

    def show_notification(self, level: str, message: str) -> None:
        self._request_id += 1
        self.write_message(
            {
                "jsonrpc": "2.0",
                "id": "trailo-protocols-{}".format(self._request_id),
                "method": "sportorg.notification.show",
                "params": {"level": level, "message": message},
            }
        )

    def write_result(self, request_id: Any, result: Dict[str, Any]) -> None:
        self.write_message({"jsonrpc": "2.0", "id": request_id, "result": result})

    def write_error(self, request_id: Any, code: int, message: str) -> None:
        self.write_message(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": code, "message": message},
            }
        )

    def write_message(self, message: Dict[str, Any]) -> None:
        line = safe_json_dumps(message).encode("utf-8") + b"\n"
        sys.stdout.buffer.write(line)
        sys.stdout.buffer.flush()


# Backward-compatible alias for tests and docs
TrailoExcelProtocolPlugin = TrailoProtocolsPlugin


def main() -> None:
    plugin = TrailoProtocolsPlugin()
    for raw_line in sys.stdin.buffer:
        line = raw_line.strip()
        if not line:
            continue

        try:
            message = parse_json_line(line)
        except orjson.JSONDecodeError as exc:
            sys.stderr.write("Invalid JSON: {}\n".format(exc))
            sys.stderr.flush()
            continue

        if not isinstance(message, dict):
            continue

        if "id" in message and "method" in message:
            plugin.handle_request(message)
        elif "method" in message:
            plugin.handle_notification(message)


if __name__ == "__main__":
    main()
