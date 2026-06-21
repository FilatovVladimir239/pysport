"""Tests for EVSK title and rank assignment."""

from sportorg.modules.reports.trailo_protocol import TrailoMode

from trailo_protocols.evsk import (
    _build_summary_lines,
    _find_title_rule,
    _format_place_range,
    _format_rank_compact,
    _select_norm_row,
    calculate_kus,
    compute_group_assignments,
    evsk_discipline_label,
)


def _row(
    *,
    name: str,
    place: int,
    qual: str = "III",
    score: int = 10,
    time_msec: int = 60_000,
    status: int = 1,
    bib: int = 101,
):
    return {
        "name": name,
        "qual": qual,
        "place": place,
        "place_show": str(place),
        "status": status,
        "bib": bib,
        "bib_raw": bib,
        "data": {"trailo_score": score, "trailo_time": time_msec, "status": status},
    }


def _preo_mode() -> TrailoMode:
    return TrailoMode(
        {
            "settings": {
                "result_processing_mode": "trailo",
                "trailo_mode": "preo",
            }
        }
    )


def _tempo_mode() -> TrailoMode:
    return TrailoMode(
        {
            "settings": {
                "result_processing_mode": "trailo",
                "trailo_mode": "tempo",
            }
        }
    )


def test_evsk_discipline_labels():
    assert evsk_discipline_label(_preo_mode(), is_relay=False) == "точное ориентирование"
    assert evsk_discipline_label(_tempo_mode(), is_relay=False) == "спринт"
    assert evsk_discipline_label(_preo_mode(), is_relay=True) == "командные соревнования"


def test_calculate_kus_top_eight():
    rows = [
        _row(name=f"P{i}", place=i, qual="III", bib=100 + i)
        for i in range(1, 11)
    ]
    assert calculate_kus(rows, is_relay=False) == 6 * 8


def test_format_place_range():
    assert _format_place_range([1, 2, 3]) == "1–3 место"
    assert _format_place_range([4, 5, 6]) == "4–6 место"
    assert _format_place_range([1]) == "1 место"


def test_format_rank_compact_preo():
    text = _format_rank_compact(
        {"score_min": 72.0, "time_max": 148.0},
        use_score=True,
        leader_score=20,
        leader_time_msec=50_000,
    )
    assert text == "14/74"


def test_high_kus_norm_row_only_includes_first_rank():
    from trailo_protocols.evsk import _load_data

    norms = _load_data()["preo_norms"]
    row = _select_norm_row(600, norms)
    assert row is not None
    assert list((row.get("ranks") or {}).keys()) == ["I"]


def test_title_ms_kms_by_place_championship_russia():
    rows = [_row(name=f"P{i}", place=i, qual="III", bib=100 + i) for i in range(1, 9)]
    mode = _preo_mode()
    result = compute_group_assignments(
        rows,
        mode,
        is_relay=False,
        plugin_settings={"evsk_competition_status": "championship_russia"},
        group={"name": "M21", "long_name": "Мужчины"},
    )
    assert not result.skipped_reason
    assert any(item.title == "МС" and item.place == 1 for item in result.titles_ms)
    assert any(item.title == "КМС" and item.place == 4 for item in result.titles_kms)
    assert result.summary_lines[0].startswith("Квалификационный уровень —")
    criteria_line = result.summary_lines[-1]
    assert "МС — 1–3 место" in criteria_line
    assert "КМС — 4–6 место" in criteria_line
    rank_chunks = [part.strip() for part in criteria_line.split(",")]
    assert not any(chunk.startswith("I р.") for chunk in rank_chunks)
    assert any(chunk.startswith("II р.") for chunk in rank_chunks)
    assert "≥" not in criteria_line


def test_relay_title_places_championship_russia():
    rule = _find_title_rule("Чемпионат России", is_relay=True)
    assert rule is not None
    assert rule.get("ms_places") == [1]
    assert rule.get("kms_places") == [2, 3]
    lines = _build_summary_lines(
        title_rule=rule,
        kus=600,
        rank_norms={"I": {"score_min": 72.0, "time_max": 148.0}},
        use_score=True,
        leader_score=10,
        leader_time_msec=50_000,
    )
    assert lines[0] == "Квалификационный уровень — 600"
    assert "МС — 1 место" in lines[1]
    assert "КМС — 2–3 место" in lines[1]


def test_summary_high_kus_ms_field_only_first_rank():
    rows = [_row(name=f"P{i}", place=i, qual="МС", bib=100 + i) for i in range(1, 9)]
    result = compute_group_assignments(rows, _preo_mode(), is_relay=False)
    assert result.kus == 800
    ranks_line = result.summary_lines[-1]
    assert "I р." in ranks_line
    assert "II р." not in ranks_line
    assert "III р." not in ranks_line
    assert "/" in ranks_line


def test_summary_medium_kus_includes_three_ranks():
    rows = [
        _row(name="A", place=1, qual="I", score=20, time_msec=50_000, bib=101),
        _row(name="B", place=2, qual="I", score=18, time_msec=55_000, bib=102),
    ]
    rows.extend(
        _row(name=f"P{i}", place=i, qual="I", bib=100 + i)
        for i in range(3, 9)
    )
    result = compute_group_assignments(rows, _preo_mode(), is_relay=False)
    assert result.kus == 200
    ranks_line = result.summary_lines[-1]
    assert "I р." in ranks_line
    assert "II р." in ranks_line
    assert "III р." in ranks_line


def test_rank_assignment_preo_leader_gets_highest_norm():
    rows = [
        _row(name="Winner", place=1, score=20, time_msec=50_000, qual="I"),
        _row(name="Runner", place=2, score=18, time_msec=60_000, qual="III"),
    ]
    rows.extend(
        _row(name=f"P{i}", place=i, qual="III", bib=200 + i)
        for i in range(3, 9)
    )
    mode = _preo_mode()
    result = compute_group_assignments(rows, mode, is_relay=False)
    assert result.kus > 0
    assert any(item.name == "Winner" and item.assigned_rank for item in result.ranks)


def test_skipped_when_not_enough_finishers():
    rows = [_row(name="Only", place=1)]
    result = compute_group_assignments(rows, _preo_mode(), is_relay=False)
    assert "недостаточно участников" in result.skipped_reason
