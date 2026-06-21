"""Shared TrailO Excel export helpers (standalone app and SportOrg plugin)."""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from sportorg.modules.reports.trailo_protocol import TrailoProtocolOptions

from trailo_protocols.excel import default_excel_filename, save_trailo_protocol_excel
from trailo_protocols.excel_script import resolve_excel_script_path, run_excel_export_script
from trailo_protocols.text_utils import normalize_race_dict, sanitize_value

DEFAULT_OUTPUT_SUBDIR = os.path.join("Documents", "TrailOProtocols")


def default_plugin_settings() -> Dict[str, Any]:
    return {
        "output_dir": "",
        "open_after_save": True,
        "use_custom_script": False,
        "custom_script": "",
        "chief_referee_signature_path": "",
        "secretary_signature_path": "",
        "federation_stamp_path": "",
        "evsk_assignments_enabled": True,
        "evsk_competition_status": "championship_russia",
        "evsk_competition_status_text": "",
    }


def is_trailo_race(race_dict: Dict[str, Any]) -> bool:
    settings = race_dict.get("settings") or {}
    return settings.get("result_processing_mode") == "trailo"


def resolve_output_dir(settings: Dict[str, Any]) -> str:
    directory = str(settings.get("output_dir") or "").strip()
    if directory:
        return os.path.abspath(directory)
    return os.path.join(os.path.expanduser("~"), DEFAULT_OUTPUT_SUBDIR)


def build_output_path(
    race_dict: Dict[str, Any],
    settings: Dict[str, Any],
    *,
    extension: str = ".xlsx",
) -> str:
    directory = resolve_output_dir(settings)
    os.makedirs(directory, exist_ok=True)
    file_name = default_excel_filename(race_dict) + extension
    return os.path.join(directory, file_name)


def export_trailo_excel(
    race_dict: Dict[str, Any],
    file_name: str,
    *,
    show_answers: bool,
    plugin_settings: Optional[Dict[str, Any]] = None,
    use_custom_script: bool = False,
    custom_script: str = "",
    working_directory: Optional[str] = None,
) -> None:
    race_dict = sanitize_value(normalize_race_dict(race_dict))
    if use_custom_script:
        script_path = resolve_excel_script_path(
            custom_script, working_directory or os.getcwd()
        )
        run_excel_export_script(
            script_path,
            race_dict,
            file_name,
            show_answers=show_answers,
        )
        return

    save_trailo_protocol_excel(
        race_dict,
        file_name,
        options=TrailoProtocolOptions(show_answers=show_answers),
        plugin_settings=plugin_settings or default_plugin_settings(),
    )
