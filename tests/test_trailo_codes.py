from types import SimpleNamespace

from sportorg.modules.trailo.codes import parse_trailo_code, trailo_sort_key


def test_parse_trailo_codes_new_and_legacy() -> None:
    assert parse_trailo_code("1TT").kind == "tc_time"
    assert parse_trailo_code("1TT").tc_idx == 1

    p = parse_trailo_code("1T2B")
    assert p.kind == "tc_answer"
    assert p.tc_idx == 1
    assert p.tc_task == 2
    assert p.tc_answer == "B"

    # legacy
    assert parse_trailo_code("110TT").kind == "tc_time"
    assert parse_trailo_code("110TT").tc_idx == 1

    p = parse_trailo_code("112TA")
    assert p.kind == "tc_answer"
    assert p.tc_idx == 1
    assert p.tc_task == 2
    assert p.tc_answer == "A"

    p = parse_trailo_code("31A")
    assert p.kind == "main"
    assert p.main_num == 31
    assert p.main_answer == "A"


def test_trailo_sort_key_main_then_time_controls() -> None:
    splits = [
        SimpleNamespace(code="2B", time=5),
        SimpleNamespace(code="1TT", time=100),
        SimpleNamespace(code="1T2B", time=0),
        SimpleNamespace(code="1T1A", time=0),
        SimpleNamespace(code="2TT", time=200),
        SimpleNamespace(code="1A", time=1),
    ]

    sorted_codes = [s.code for s in sorted(splits, key=trailo_sort_key)]
    assert sorted_codes == ["1A", "2B", "1TT", "1T1A", "1T2B", "2TT"]

