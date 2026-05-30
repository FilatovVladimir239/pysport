from types import SimpleNamespace

from sportorg.modules.printing.printout_split import (
    parse_trailo_code,
    trailo_sort_key,
)


def test_is_trailo_time_control_code() -> None:
    assert parse_trailo_code("1TT").kind == "tc_time"
    assert parse_trailo_code("1T2A").kind == "tc_answer"
    assert parse_trailo_code("110TT").kind == "tc_time"  # legacy
    assert parse_trailo_code("112TA").kind == "tc_answer"  # legacy
    assert parse_trailo_code("31A").kind == "main"
    assert parse_trailo_code("").kind == "unknown"
    assert parse_trailo_code(None).kind == "unknown"  # type: ignore[arg-type]


def test_trailo_sort_key_handles_weird_codes() -> None:
    splits = [
        SimpleNamespace(code="", time=3),
        SimpleNamespace(code=None, time=2),
        SimpleNamespace(code="A", time=1),
        SimpleNamespace(code="9A", time=5),
        SimpleNamespace(code="10B", time=4),
        SimpleNamespace(code="1T1A", time=0),
    ]

    # Главное: не падает и возвращает сравнимые ключи
    keys = [trailo_sort_key(s) for s in splits]
    assert all(isinstance(k, tuple) and len(k) >= 3 for k in keys)

    # И сортировка работает
    sorted_splits = sorted(splits, key=trailo_sort_key)
    assert [s.code for s in sorted_splits[:2]] == ["9A", "10B"]
