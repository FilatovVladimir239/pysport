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


def test_generate_trailo_report_templates():
    File("tests/data/test.json").open()
    races_dict = [r.to_dict() for r in races()]
    kwargs = {
        "race": races_dict[get_current_race_index()],
        "races": races_dict,
        "rent_cards": list(RentCards().get()),
        "current_race": get_current_race_index(),
        "selected": {"persons": []},
    }
    html = get_text_from_file("reports/1_results_trailo.html", **kwargs)
    excel = get_text_from_file("reports/1_results_trailo_excel.html", **kwargs)
    assert "trailo_results_protocol.inc.html" not in html
    assert "exportResultsToExcel" in html
    assert "SPORTORG_TRAILO_PROTOCOL" in excel
    assert "excelMode: true" in excel
    assert "exportResultsToExcel" in excel
