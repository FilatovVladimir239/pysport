from types import SimpleNamespace

from types import SimpleNamespace

from sportorg.models.memory import Course, CourseControl
from sportorg.modules.trailo.codes import (
    parse_trailo_code,
    trailo_correctness_mark,
    trailo_course_expanded_control_codes,
    trailo_expected_answer_letter_for_split,
    trailo_main_control_display_code,
    trailo_sort_key,
)


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


def test_trailo_main_control_display_code_repeat_same_cp() -> None:
    p12a = parse_trailo_code("12A")
    p12b = parse_trailo_code("12B")
    assert trailo_main_control_display_code(p12a, None) == "12A"
    assert trailo_main_control_display_code(p12b, 12) == "--B"
    p13c = parse_trailo_code("13C")
    assert trailo_main_control_display_code(p13c, 12) == "13C"


def test_trailo_correctness_mark() -> None:
    assert trailo_correctness_mark(True, None) == "(+)"
    assert trailo_correctness_mark(False, "A") == "(A)"
    assert trailo_correctness_mark(False, None) == "(?)"


def test_trailo_expected_answer_letter_for_main() -> None:
    course = Course()
    cc = CourseControl()
    cc.code = "12A"
    course.controls = [cc]
    expanded = trailo_course_expanded_control_codes(course)
    split = SimpleNamespace(course_index=0, code="12B")
    assert trailo_expected_answer_letter_for_split(split, expanded) == "A"


def test_trailo_expected_answer_fallback_by_punched_code() -> None:
    course = Course()
    cc = CourseControl()
    cc.code = "5C"
    course.controls = [cc]
    expanded = trailo_course_expanded_control_codes(course)
    split = SimpleNamespace(course_index=-1, code="5X")
    assert trailo_expected_answer_letter_for_split(split, expanded) == "C"

