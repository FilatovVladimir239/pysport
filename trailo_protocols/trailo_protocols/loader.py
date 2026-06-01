"""Load a SportOrg event file and produce race dicts ready for protocol export."""
from __future__ import annotations

import gzip
import io
from pathlib import Path
from typing import Any, Dict, List, Tuple

import orjson

from sportorg.models.memory import Race, new_event
from sportorg.models.result.result_tools import recalculate_results
from sportorg.modules.backup.file import is_gzip_file
from sportorg.modules.backup.json import get_races_from_file


def _is_utf8_decode_error(exc: BaseException) -> bool:
    message = str(exc).casefold()
    return "utf" in message or "surrogate" in message


def _load_json_data(path: str) -> Any:
    """
    Parse JSON like SportOrg ``File.open()``: gzip, UTF-8, or Windows-1251.
    """
    raw = Path(path).read_bytes()
    if not raw:
        raise ValueError("Файл пустой")

    if is_gzip_file(path) or (len(raw) >= 2 and raw[:2] == b"\x1f\x8b"):
        raw = gzip.decompress(raw)

    try:
        return orjson.loads(raw)
    except orjson.JSONDecodeError as first_error:
        if not _is_utf8_decode_error(first_error):
            raise

    for encoding in ("cp1251", "latin-1"):
        try:
            return orjson.loads(raw.decode(encoding))
        except UnicodeDecodeError:
            continue
        except orjson.JSONDecodeError:
            continue

    raise ValueError(
        "Не удалось прочитать файл базы: ожидается JSON в UTF-8 или Windows-1251. "
        "В SportOrg можно включить «Сохранять файлы в UTF-8» и пересохранить событие."
    ) from first_error


def load_event_file(path: str) -> Tuple[List[Dict[str, Any]], int]:
    """
    Parse a SportOrg JSON (plain, UTF-8/CP1251, or gzip) file.

    Returns a list of race dicts (``Race.to_dict()``) and the index of the
    active race stored in the file.
    """
    data = _load_json_data(path)
    payload = orjson.dumps(data)
    new_event([Race()])
    event, current_race = get_races_from_file(io.BytesIO(payload), compress=False)
    race_dicts: List[Dict[str, Any]] = []
    for obj in event:
        obj.rebuild_indexes(True, True)
        recalculate_results(race_object=obj)
        race_dict = obj.to_dict()
        if race_dict and "settings" in race_dict:
            race_dict["settings"].pop("live_urls", None)
        race_dicts.append(race_dict)
    return race_dicts, current_race


def race_label(race_dict: Dict[str, Any], index: int) -> str:
    data = race_dict.get("data") or {}
    title = str(data.get("title") or "").strip()
    description = str(data.get("description") or "").strip()
    if title and description and title != description:
        return f"{index + 1}. {title} — {description}"
    if title:
        return f"{index + 1}. {title}"
    if description:
        return f"{index + 1}. {description}"
    return f"{index + 1}. {race_dict.get('id', 'race')}"
