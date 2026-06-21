from trailo_protocols.text_utils import (
    parse_json_line,
    repair_text,
    safe_json_dumps,
    sanitize_text,
    sanitize_value,
)

PETROV = "\u041f\u0435\u0442\u0440\u043e\u0432"
SIDOROV = "\u0421\u0438\u0434\u043e\u0440\u043e\u0432"
IVANOV = "\u0418\u0432\u0430\u043d\u043e\u0432"


def _has_surrogates(value: str) -> bool:
    return any(0xD800 <= ord(char) <= 0xDFFF for char in value)


def test_sanitize_text_preserves_cyrillic():
    text = "{} \u0418\u0432\u0430\u043d \u2014 \u041c21".format(IVANOV)
    assert sanitize_text(text) == text


def test_repair_utf8_mojibake_read_as_cp1251():
    broken = PETROV.encode("utf-8").decode("cp1251")
    assert repair_text(broken) == PETROV


def test_repair_cp1251_mojibake_read_as_latin1():
    broken = SIDOROV.encode("cp1251").decode("latin-1")
    assert repair_text(broken) == SIDOROV


def test_sanitize_text_recovers_legacy_bytes_as_surrogateescape():
    broken = SIDOROV.encode("cp1251").decode("utf-8", errors="surrogateescape")
    if _has_surrogates(broken):
        assert sanitize_text(broken) == SIDOROV
    else:
        assert repair_text(broken) == SIDOROV


def test_safe_json_dumps_with_surrogates_in_dict():
    payload = {"message": "fail\uDC98"}
    text = safe_json_dumps(payload)
    assert "\udc98" not in text
    assert "fail" in text


def test_parse_json_line_utf8_cyrillic():
    payload = safe_json_dumps({"name": IVANOV})
    parsed = parse_json_line(payload.encode("utf-8"))
    assert parsed["name"] == IVANOV


def test_sanitize_value_leaves_ints():
    assert sanitize_value(42) == 42
