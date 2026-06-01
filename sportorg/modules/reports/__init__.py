"""Report generation helpers used from the GUI."""

from sportorg.modules.reports.excel_script import (
    resolve_excel_script_path,
    run_excel_export_script,
)
from sportorg.modules.reports.trailo_protocol import TrailoProtocolOptions
from sportorg.modules.reports.trailo_protocol_excel import (
    default_excel_filename,
    default_excel_protocol_options,
    save_trailo_protocol_excel,
)

TRAILO_EXCEL_TEMPLATE = "/reports/1_results_trailo.xlsx"

__all__ = [
    "TRAILO_EXCEL_TEMPLATE",
    "TrailoProtocolOptions",
    "default_excel_filename",
    "default_excel_protocol_options",
    "resolve_excel_script_path",
    "run_excel_export_script",
    "save_trailo_protocol_excel",
]
