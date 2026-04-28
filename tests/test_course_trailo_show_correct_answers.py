import uuid

from sportorg.models.memory import Course


def test_course_trailo_show_correct_answers_defaults_true() -> None:
    c = Course()
    assert c.trailo_show_correct_answers is True


def test_course_update_data_omitted_key_keeps_default_true() -> None:
    c = Course()
    c.update_data(
        {
            "object": "Course",
            "id": str(uuid.uuid4()),
            "name": "A",
            "bib": 0,
            "length": 0,
            "climb": 0,
            "corridor": 0,
            "controls": [],
        }
    )
    assert c.trailo_show_correct_answers is True


def test_course_update_data_false_roundtrip_in_to_dict() -> None:
    c = Course()
    cid = str(uuid.uuid4())
    c.update_data(
        {
            "object": "Course",
            "id": cid,
            "name": "B",
            "bib": 0,
            "length": 0,
            "climb": 0,
            "corridor": 0,
            "controls": [],
            "trailo_show_correct_answers": False,
        }
    )
    assert c.trailo_show_correct_answers is False
    d = c.to_dict()
    assert d["trailo_show_correct_answers"] is False
