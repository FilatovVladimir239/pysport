import gzip
import json
import tempfile
import uuid

import orjson
import pytest

from trailo_protocols.loader import _load_json_data, load_event_file


def _minimal_event_dict():
    race_id = str(uuid.uuid4())
    return {
        "version": "1.0.0",
        "current_race": 0,
        "races": [
            {
                "object": "Race",
                "id": race_id,
                "data": {"title": "Test", "description": "Описание кириллица"},
                "settings": {"result_processing_mode": "trailo", "trailo_mode": "preo"},
                "organizations": [],
                "courses": [],
                "groups": [],
                "persons": [],
                "results": [],
            }
        ],
    }


def test_load_json_data_utf8():
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump(_minimal_event_dict(), handle, ensure_ascii=False)
        path = handle.name
    data = _load_json_data(path)
    assert data["races"][0]["data"]["description"] == "Описание кириллица"


def test_load_json_data_cp1251():
    payload = orjson.dumps(_minimal_event_dict())
    text_cp1251 = payload.decode("utf-8").encode("cp1251")
    with tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False) as handle:
        handle.write(text_cp1251)
        path = handle.name
    data = _load_json_data(path)
    assert "кириллица" in data["races"][0]["data"]["description"]


def test_load_json_data_gzip_without_gz_extension():
    payload = orjson.dumps(_minimal_event_dict())
    compressed = gzip.compress(payload)
    with tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False) as handle:
        handle.write(compressed)
        path = handle.name
    data = _load_json_data(path)
    assert len(data["races"]) == 1


def test_load_event_file_returns_race_dicts():
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "tests" / "data" / "test.json"
    if not path.is_file():
        pytest.skip("sportorg tests/data/test.json not available")
    race_dicts, current = load_event_file(str(path))
    assert current >= 0
    assert len(race_dicts) >= 1
