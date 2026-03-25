from types import SimpleNamespace

from sportorg.modules.printing.printout_split import (
    _is_trailo_time_control_code,
    _trailo_sort_key,
)


def test_is_trailo_time_control_code() -> None:
    assert _is_trailo_time_control_code("31T1") is True
    assert _is_trailo_time_control_code("31T") is False
    assert _is_trailo_time_control_code("31A") is False
    assert _is_trailo_time_control_code("T") is False
    assert _is_trailo_time_control_code("") is False
    assert _is_trailo_time_control_code(None) is False  # type: ignore[arg-type]


def test_trailo_sort_key_handles_weird_codes() -> None:
    splits = [
        SimpleNamespace(code="", time=3),
        SimpleNamespace(code=None, time=2),
        SimpleNamespace(code="A", time=1),
        SimpleNamespace(code="9A", time=5),
        SimpleNamespace(code="10B", time=4),
        SimpleNamespace(code="31T1", time=0),
    ]

    # Главное: не падает и возвращает сравнимые ключи
    keys = [_trailo_sort_key(s) for s in splits]
    assert all(isinstance(k, tuple) and len(k) == 3 for k in keys)

    # И сортировка работает
    sorted_splits = sorted(splits, key=_trailo_sort_key)
    assert sorted_splits[0].code == "9A"
