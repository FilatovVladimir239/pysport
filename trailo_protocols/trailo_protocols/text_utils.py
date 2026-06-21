"""Text helpers for export and JSON-RPC (SportOrg / Windows legacy encodings)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import orjson


def _has_surrogates(value: str) -> bool:
    return any(0xD800 <= ord(char) <= 0xDFFF for char in value)


def _cyrillic_count(value: str) -> int:
    return sum(1 for char in value if 0x0400 <= ord(char) <= 0x04FF)


def _strip_lone_surrogates(value: str) -> str:
    return "".join(
        "\ufffd" if 0xD800 <= ord(char) <= 0xDFFF else char for char in value
    )


def _text_quality_score(value: str) -> int:
    score = 0
    for char in value:
        code = ord(char)
        if 0x0400 <= code <= 0x04FF:
            score += 4
        elif char.isascii() and (char.isalnum() or char in " -–—.,()"):
            score += 1
        elif code == 0xFFFD:
            score -= 8
        elif 0x0080 <= code <= 0x00FF:
            score -= 2
    return score


def _try_recode(value: str, source_encoding: str, target_encoding: str) -> Optional[str]:
    try:
        if source_encoding == "utf-8":
            raw = value.encode("utf-8", errors="surrogateescape")
        else:
            raw = value.encode(source_encoding)
        return raw.decode(target_encoding)
    except UnicodeError:
        return None


def repair_text(value: str) -> str:
    """Pick the best decoding for display/export (Cyrillic-aware heuristic)."""
    if not value:
        return value

    utf8_fix = _try_recode(value, "cp1251", "utf-8")
    if (
        utf8_fix
        and utf8_fix != value
        and _cyrillic_count(utf8_fix) >= 2
        and len(utf8_fix) < len(value)
    ):
        return utf8_fix

    latin_cp1251 = _try_recode(value, "latin-1", "cp1251")
    if latin_cp1251 and _text_quality_score(latin_cp1251) > _text_quality_score(value):
        return latin_cp1251

    if _has_surrogates(value):
        surrogate_fix = _try_recode(value, "utf-8", "cp1251")
        if surrogate_fix and _text_quality_score(surrogate_fix) > _text_quality_score(
            value
        ):
            return surrogate_fix

    best = value
    best_score = _text_quality_score(value)
    for candidate in (
        _try_recode(value, "latin-1", "utf-8"),
        _try_recode(value, "cp1252", "utf-8"),
    ):
        if not candidate:
            continue
        score = _text_quality_score(candidate)
        if score > best_score:
            best = candidate
            best_score = score

    if _has_surrogates(best):
        return _strip_lone_surrogates(best)
    return best


def sanitize_text(value: str) -> str:
    if not value:
        return value
    return repair_text(value)


def sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, dict):
        return {
            sanitize_value(key): sanitize_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_value(item) for item in value)
    return value


def normalize_race_dict(race: Dict[str, Any]) -> Dict[str, Any]:
    return orjson.loads(orjson.dumps(race))


def safe_json_dumps(data: Any) -> str:
    return orjson.dumps(sanitize_value(data)).decode("utf-8")


def parse_json_line(line: bytes) -> Any:
    return orjson.loads(line)
