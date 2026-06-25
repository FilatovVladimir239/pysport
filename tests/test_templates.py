from sportorg.common.template import get_text_from_file
from sportorg.models.constant import RentCards
from sportorg.models.memory import get_current_race_index, races
from sportorg.modules.backup.file import File


def test_generate_report():
    File("tests/data/test.json").open()
    races_dict = [r.to_dict() for r in races()]

    result = get_text_from_file(
        "reports/1_results.html",
        race=races_dict[get_current_race_index()],
        races=races_dict,
        rent_cards=list(RentCards().get()),
        current_race=get_current_race_index(),
        selected={"persons": []},
    )

    assert result


def test_generate_report_from_absolute_path():
    from sportorg import settings

    File("tests/data/test.json").open()
    races_dict = [r.to_dict() for r in races()]
    template_path = settings.template_dir("reports", "1_results.html")

    result = get_text_from_file(
        template_path,
        race=races_dict[get_current_race_index()],
        races=races_dict,
        rent_cards=list(RentCards().get()),
        current_race=get_current_race_index(),
        selected={"persons": []},
    )

    assert result
    assert "RESULT LIST" in result
