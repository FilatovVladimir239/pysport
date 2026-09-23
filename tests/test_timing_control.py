import pytest

from sportorg.common.otime import OTime
from sportorg.models.memory import Race, ResultSFR, Split, new_event, race
from sportorg.models.result.result_tools import recalculate_results
from sportorg.modules.trailo.sfr_card import TrailoSfrCardProcessor


@pytest.mark.parametrize("answer", range(7))
def test_timing_control_after_sfr_trailo_readout_and_recheck(answer):
    new_event([Race()])
    race().set_setting("result_processing_mode", "trailo")
    race().set_setting("system_start_source", "cp")
    race().set_setting("system_finish_source", "cp")
    result = ResultSFR()
    race().results.append(result)
    TrailoSfrCardProcessor.append_splits(
        result,
        [
            (1, OTime(sec=10)),
            (2, OTime(sec=20)),
            (3, OTime(sec=30)),
            (2, OTime(sec=40)),
        ],
        answer,
    )

    for number, start, finish in [(0, 10, 40), (1, 10, 10), (2, 20, 40), (3, 30, 30)]:
        race().set_setting("system_start_cp_number", number)
        race().set_setting("system_finish_cp_number", number)
        recalculate_results()
        assert result.get_start_time() == OTime(sec=start)
        assert result.get_finish_time() == OTime(sec=finish)


@pytest.mark.parametrize("mode", ["time", "trailo"])
@pytest.mark.parametrize(
    "code,expected",
    [
        (2, True),
        ("2", True),
        ("2A", None),
        ("12A", False),
        ("2TT", False),
        ("2T1A", False),
        ("112TA", False),
    ],
)
def test_timing_control_matches_only_station_number(mode, code, expected):
    new_event([Race()])
    race().set_setting("result_processing_mode", mode)
    race().set_setting("system_start_source", "cp")
    race().set_setting("system_start_cp_number", 2)
    race().set_setting("system_finish_source", "cp")
    race().set_setting("system_finish_cp_number", 2)
    result = ResultSFR()
    split = Split()
    split.code = code
    split.time = OTime(sec=20)
    result.splits = [split]
    matches = mode == "trailo" if expected is None else expected
    expected_time = split.time if matches else OTime()
    assert result.get_start_time() == expected_time
    assert result.get_finish_time() == expected_time
