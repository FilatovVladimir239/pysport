"""Load optional user Excel export scripts from the templates directory."""
import importlib.util
import inspect
import logging
import os
from types import ModuleType
from typing import Any, Callable, Dict

from sportorg.modules.reports.trailo_protocol import TrailoProtocolOptions

logger = logging.getLogger(__name__)

_EXPORT_NAMES = (
    "save_trailo_protocol_excel",
    "export",
    "save_protocol_excel",
)


def _is_host_absolute_path(template_path: str) -> bool:
    if template_path.startswith("\\\\"):
        return True
    return len(template_path) > 1 and template_path[1] == ":"


def resolve_excel_script_path(template_path: str, templates_root: str) -> str:
    """Return absolute path to a report template script."""
    if os.path.isfile(template_path):
        return os.path.abspath(template_path)
    if _is_host_absolute_path(template_path):
        return template_path
    relative = template_path.replace("\\", "/").lstrip("/")
    return os.path.normpath(
        os.path.join(templates_root, relative.replace("/", os.sep))
    )


def _load_module(script_path: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "sportorg_excel_export_script",
        script_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load Excel export script: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _find_exporter(module: ModuleType) -> Callable[..., None]:
    for name in _EXPORT_NAMES:
        candidate = getattr(module, name, None)
        if callable(candidate):
            return candidate
    raise AttributeError(
        "Excel export script must define one of: "
        + ", ".join(_EXPORT_NAMES)
    )


def run_excel_export_script(
    script_path: str,
    race: Dict[str, Any],
    file_name: str,
    *,
    show_answers: bool = False,
) -> None:
    """
    Execute a user-provided Python export script.

    Place ``my_protocol.py`` in your templates ``reports`` folder (see
  settings → templates path) and select it in Reports like other templates.

    The script must define ``export(race, file_name, ...)`` or
    ``save_trailo_protocol_excel(race, file_name, ...)``. Supported keyword
    arguments: ``show_answers`` (bool) and/or ``options`` (TrailoProtocolOptions).
    """
    exporter = _find_exporter(_load_module(script_path))
    options = TrailoProtocolOptions(show_answers=show_answers)
    kwargs: Dict[str, Any] = {"show_answers": show_answers, "options": options}
    try:
        exporter(race, file_name, **kwargs)
        return
    except TypeError as first_error:
        signature = inspect.signature(exporter)
        params = signature.parameters.values()
        accepts_kwargs = any(
            param.kind == inspect.Parameter.VAR_KEYWORD for param in params
        )
        if accepts_kwargs:
            raise
        filtered = {
            key: value
            for key, value in kwargs.items()
            if key in signature.parameters
        }
        try:
            exporter(race, file_name, **filtered)
            return
        except TypeError:
            if len(params) <= 2:
                exporter(race, file_name)
                return
            raise first_error from None
