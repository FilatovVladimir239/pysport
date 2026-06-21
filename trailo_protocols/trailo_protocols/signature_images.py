"""Store official signature scans for TrailO protocol export."""
from __future__ import annotations

import os
import shutil
import uuid
from typing import Any, Dict

from trailo_protocols.export_core import resolve_output_dir

_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}


def signatures_dir(settings: Dict[str, Any]) -> str:
    directory = os.path.join(resolve_output_dir(settings), "signatures")
    os.makedirs(directory, exist_ok=True)
    return directory


def store_signature_image(
    source_path: str, role: str, settings: Dict[str, Any]
) -> str:
    """Copy an image into the plugin output folder and return the saved path."""
    if not source_path or not os.path.isfile(source_path):
        raise FileNotFoundError(source_path)
    extension = os.path.splitext(source_path)[1].lower()
    if extension not in _ALLOWED_EXTENSIONS:
        extension = ".png"
    safe_role = "".join(char if char.isalnum() else "_" for char in role)[:32] or "official"
    destination = os.path.join(
        signatures_dir(settings),
        "{}_{}{}".format(safe_role, uuid.uuid4().hex[:10], extension),
    )
    shutil.copy2(source_path, destination)
    return os.path.abspath(destination)


def signature_image_filter_text() -> str:
    return (
        "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp);;"
        "PNG (*.png);;JPEG (*.jpg *.jpeg)"
    )


def migrate_signature_settings_from_race(
    plugin_settings: Dict[str, Any], race: Dict[str, Any]
) -> Dict[str, Any]:
    """Copy legacy SportOrg race.data signature paths into plugin settings once."""
    data = race.get("data") or {}
    if not isinstance(data, dict):
        return plugin_settings
    updated = dict(plugin_settings)
    changed = False
    for key in ("chief_referee_signature_path", "secretary_signature_path"):
        if str(updated.get(key) or "").strip():
            continue
        legacy = str(data.get(key) or "").strip()
        if legacy:
            updated[key] = legacy
            changed = True
    if changed:
        updated["_signatures_migrated_from_race"] = True
    return updated
