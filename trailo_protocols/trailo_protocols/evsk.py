"""EVSK (sport for persons with ODA) title and rank assignment for TrailO Excel protocols."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sportorg.modules.reports.trailo_protocol import TrailoMode

# Qualification points per EVSK orienteering conditions (sheet «нормы», п. 1).
EVSK_QUAL_POINTS: Dict[str, int] = {
    "МС": 100,
    "КМС": 50,
    "I": 25,
    "II": 12,
    "III": 6,
    "IIIю": 3,
    "IIю": 2,
    "Iю": 1,
    "б/р": 0,
    "": 0,
}

# Plugin setting keys → substring matched in EVSK «МС-КМС» competition status column.
COMPETITION_STATUS_KEYS: Dict[str, str] = {
    "world_youth": "Первенство мира",
    "europe_youth": "Первенство Европы",
    "international_other": "Другие международные спортивные соревнования",
    "championship_russia": "Чемпионат России",
    "cup_russia": "Кубок России",
    "first_russia": "Первенство России",
    "all_russian_other": "Другие всероссийские спортивные соревнования",
    "district_championship": "Чемпионат федерального округа",
    "district_first": "Первенство федерального округа",
}

DEFAULT_COMPETITION_STATUS = "championship_russia"

MIN_FINISHERS_INDIVIDUAL = 8
MIN_FINISHERS_RELAY = 4

_DATA_PATH = os.path.join(os.path.dirname(__file__), "evsk_data.json")
_CACHED_DATA: Optional[Dict[str, Any]] = None


def _load_data() -> Dict[str, Any]:
    global _CACHED_DATA
    if _CACHED_DATA is None:
        with open(_DATA_PATH, encoding="utf-8") as handle:
            _CACHED_DATA = json.load(handle)
    return _CACHED_DATA


@dataclass
class TitleAssignment:
    title: str
    name: str
    place: int


@dataclass
class RankAssignment:
    name: str
    place: int
    assigned_rank: str
    detail: str = ""


@dataclass
class GroupAssignments:
    competition_status: str = ""
    discipline_label: str = ""
    kus: int = 0
    kus_note: str = ""
    titles_ms: List[TitleAssignment] = field(default_factory=list)
    titles_kms: List[TitleAssignment] = field(default_factory=list)
    ranks: List[RankAssignment] = field(default_factory=list)
    summary_lines: List[str] = field(default_factory=list)
    skipped_reason: str = ""


def _format_place_range(places: Optional[Sequence[int]]) -> str:
    if not places:
        return ""
    ordered = sorted(int(place) for place in places)
    if len(ordered) == 1:
        return f"{ordered[0]} место"
    return f"{ordered[0]}–{ordered[-1]} место"


def _format_rank_compact(
    requirement: Dict[str, Any],
    *,
    use_score: bool,
    leader_score: int,
    leader_time_msec: int,
) -> str:
    """Absolute thresholds as «очки/сек» (e.g. 20/124)."""
    score_part = ""
    time_part = ""
    score_min = requirement.get("score_min")
    if use_score and score_min is not None and leader_score > 0:
        score_part = str(
            max(1, int(round(leader_score * float(score_min) / 100.0)))
        )
    time_max = requirement.get("time_max")
    if time_max is not None and leader_time_msec > 0:
        time_part = str(
            max(0, int(round(leader_time_msec * float(time_max) / 100.0 / 1000)))
        )
    if score_part and time_part:
        return f"{score_part}/{time_part}"
    if time_part:
        return time_part
    if score_part:
        return score_part
    return ""


def _build_summary_lines(
    *,
    title_rule: Optional[Dict[str, Any]],
    kus: int,
    rank_norms: Dict[str, Dict[str, Any]],
    use_score: bool,
    leader_score: int,
    leader_time_msec: int,
) -> List[str]:
    lines: List[str] = []
    criteria_parts: List[str] = []
    if title_rule:
        ms_places = title_rule.get("ms_places")
        if ms_places:
            criteria_parts.append(f"МС — {_format_place_range(ms_places)}")
        kms_places = title_rule.get("kms_places")
        if kms_places:
            criteria_parts.append(f"КМС — {_format_place_range(kms_places)}")
    for rank_key in ("I", "II", "III"):
        requirement = rank_norms.get(rank_key)
        if not requirement:
            continue
        compact = _format_rank_compact(
            requirement,
            use_score=use_score,
            leader_score=leader_score,
            leader_time_msec=leader_time_msec,
        )
        if compact:
            criteria_parts.append(f"{rank_key} р. — {compact}")

    if kus > 0:
        lines.append(f"Квалификационный уровень — {kus}")
    if criteria_parts:
        lines.append(", ".join(criteria_parts))
    return lines


def evsk_discipline_label(mode: TrailoMode, *, is_relay: bool) -> str:
    if is_relay:
        return "командные соревнования"
    if mode.is_preo:
        return "точное ориентирование"
    if mode.is_tempo:
        return "спринт"
    return "спринт"


def _competition_status_text(settings: Optional[Dict[str, Any]]) -> str:
    settings = settings or {}
    if settings.get("evsk_competition_status_text"):
        return str(settings["evsk_competition_status_text"]).strip()
    key = str(settings.get("evsk_competition_status") or DEFAULT_COMPETITION_STATUS)
    return COMPETITION_STATUS_KEYS.get(key, key)


def _find_title_rule(
    status_text: str,
    *,
    is_relay: bool,
    sex_age_hint: str = "",
) -> Optional[Dict[str, Any]]:
    rules = _load_data().get("title_rules") or []
    needle = status_text.lower()
    candidates = [
        rule
        for rule in rules
        if bool(rule.get("relay")) == is_relay
        and needle in str(rule.get("status") or "").lower()
    ]
    if not candidates:
        return None
    if sex_age_hint:
        hint = sex_age_hint.lower()
        filtered = [
            rule
            for rule in candidates
            if str(rule.get("sex_age") or "").strip()
            and hint in str(rule.get("sex_age") or "").lower()
        ]
        if filtered:
            candidates = filtered
        else:
            candidates = [rule for rule in candidates if not str(rule.get("sex_age") or "").strip()]
    else:
        candidates = [rule for rule in candidates if not str(rule.get("sex_age") or "").strip()] or candidates
    return candidates[0]


def _qual_points(qual_title: str) -> int:
    title = str(qual_title or "").strip()
    if title in EVSK_QUAL_POINTS:
        return EVSK_QUAL_POINTS[title]
    for key, value in EVSK_QUAL_POINTS.items():
        if key and title.upper() == key.upper():
            return value
    return 0


def _ok_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ret: List[Dict[str, Any]] = []
    for row in rows:
        if row.get("is_out_of_competition"):
            continue
        if int(row.get("status") or 0) != 1:
            continue
        ret.append(row)
    return ret


def _row_place(row: Dict[str, Any]) -> int:
    place = int(row.get("place") or 0)
    if place > 0:
        return place
    shown = str(row.get("place_show") or "").strip()
    if shown.isdigit():
        return int(shown)
    return 0


def _dedupe_relay_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    teams: List[Dict[str, Any]] = []
    for row in sorted(rows, key=lambda item: (_row_place(item) or 9999, str(item.get("name") or ""))):
        bib_raw = int(row.get("bib_raw") or row.get("bib") or 0)
        team_key = bib_raw % 1000 if bib_raw > 1000 else bib_raw
        if team_key in seen:
            continue
        seen.add(team_key)
        teams.append(row)
    return teams


def _result_metrics(row: Dict[str, Any]) -> Tuple[int, int]:
    data = row.get("data") or {}
    score = data.get("trailo_score")
    if score in ("", None):
        score = row.get("trailo_score")
    time_msec = data.get("trailo_time")
    if time_msec in ("", None):
        time_msec = 0
    try:
        score_val = int(score)
    except (TypeError, ValueError):
        score_val = 0
    try:
        time_val = int(time_msec)
    except (TypeError, ValueError):
        time_val = 0
    return score_val, time_val


def calculate_kus(rows: Sequence[Dict[str, Any]], *, is_relay: bool) -> int:
    ok = _ok_rows(rows)
    if is_relay:
        ok = _dedupe_relay_rows(ok)
    top = sorted(
        [_qual_points(row.get("qual") or "") for row in ok],
        reverse=True,
    )[:8]
    if not top:
        return 0
    if is_relay:
        return int(round(sum(top) / len(top)))
    return int(sum(top))


def _select_norm_row(kus: int, norms: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if kus <= 0:
        return None
    for entry in norms:
        if kus >= int(entry.get("kus") or 0):
            return entry
    return norms[-1] if norms else None


def _norm_table(mode: TrailoMode, *, is_relay: bool) -> List[Dict[str, Any]]:
    data = _load_data()
    if mode.is_tempo and not is_relay:
        return data.get("tempo_norms") or []
    return data.get("preo_norms") or []


def _meets_rank_threshold(
    *,
    score_pct: float,
    time_pct: float,
    requirement: Dict[str, Any],
    use_score: bool,
) -> bool:
    if use_score:
        if score_pct < float(requirement.get("score_min") or 0):
            return False
    if time_pct > float(requirement.get("time_max") or 9999):
        return False
    return True


def _assign_rank(
    score_pct: float,
    time_pct: float,
    rank_norms: Dict[str, Dict[str, Any]],
    *,
    use_score: bool,
) -> str:
    for rank_name in ("I", "II", "III"):
        requirement = rank_norms.get(rank_name)
        if not requirement:
            continue
        if _meets_rank_threshold(
            score_pct=score_pct,
            time_pct=time_pct,
            requirement=requirement,
            use_score=use_score,
        ):
            return rank_name
    return ""


def compute_group_assignments(
    rows: Sequence[Dict[str, Any]],
    mode: TrailoMode,
    *,
    is_relay: bool,
    plugin_settings: Optional[Dict[str, Any]] = None,
    group: Optional[Dict[str, Any]] = None,
) -> GroupAssignments:
    settings = plugin_settings or {}
    if not settings.get("evsk_assignments_enabled", True):
        return GroupAssignments(skipped_reason="отключено в настройках плагина")

    status_text = _competition_status_text(settings)
    sex_age_hint = str((group or {}).get("long_name") or (group or {}).get("name") or "")
    discipline = evsk_discipline_label(mode, is_relay=is_relay)
    result = GroupAssignments(
        competition_status=status_text,
        discipline_label=discipline,
    )

    ok = _ok_rows(rows)
    title_rows = _dedupe_relay_rows(ok) if is_relay else ok
    min_finishers = MIN_FINISHERS_RELAY if is_relay else MIN_FINISHERS_INDIVIDUAL
    if len(title_rows) < min_finishers:
        result.skipped_reason = (
            f"недостаточно участников с результатом (нужно не менее {min_finishers})"
        )
        return result

    title_rule = _find_title_rule(status_text, is_relay=is_relay, sex_age_hint=sex_age_hint)
    if title_rule:
        ms_places = set(title_rule.get("ms_places") or [])
        kms_places = set(title_rule.get("kms_places") or [])
        for row in title_rows:
            place = _row_place(row)
            if place <= 0:
                continue
            name = str(row.get("name") or "").strip()
            if place in ms_places:
                result.titles_ms.append(TitleAssignment("МС", name, place))
            elif place in kms_places:
                result.titles_kms.append(TitleAssignment("КМС", name, place))

    kus = calculate_kus(rows, is_relay=is_relay)
    result.kus = kus
    norms = _norm_table(mode, is_relay=is_relay)
    if not norms:
        result.kus_note = "КУС не определён"
        return result
    norm_row = _select_norm_row(kus, norms)
    if not norm_row:
        result.kus_note = "КУС не определён"
        return result
    rank_norms = dict(norm_row.get("ranks") or {})
    result.kus_note = f"КУС {kus}"

    leaders = [row for row in ok if _row_place(row) == 1]
    if not leaders:
        leaders = sorted(ok, key=_row_place)
        leaders = leaders[:1]
    if not leaders:
        return result
    leader = leaders[0]
    leader_score, leader_time = _result_metrics(leader)
    if leader_time <= 0 and not mode.is_preo:
        result.skipped_reason = "нет времени победителя"
        return result
    use_score = mode.is_preo or is_relay

    result.summary_lines = _build_summary_lines(
        title_rule=title_rule,
        kus=kus,
        rank_norms=rank_norms,
        use_score=use_score,
        leader_score=leader_score,
        leader_time_msec=leader_time,
    )

    rank_rows = ok if not is_relay else [row for row in ok if int(row.get("bib_raw") or 0) > 1000]
    for row in sorted(rank_rows, key=lambda item: (_row_place(item) or 9999, str(item.get("name") or ""))):
        score, time_msec = _result_metrics(row)
        if leader_time > 0:
            time_pct = 100.0 * time_msec / leader_time
        else:
            time_pct = 0.0
        if use_score and leader_score > 0:
            score_pct = 100.0 * score / leader_score
        else:
            score_pct = 100.0 if score > 0 else 0.0
        assigned = _assign_rank(score_pct, time_pct, rank_norms, use_score=use_score)
        if not assigned:
            continue
        detail_parts = []
        if use_score:
            detail_parts.append(f"очки {score_pct:.0f}%")
        if leader_time > 0:
            detail_parts.append(f"время {time_pct:.0f}%")
        result.ranks.append(
            RankAssignment(
                name=str(row.get("name") or ""),
                place=_row_place(row),
                assigned_rank=assigned,
                detail=", ".join(detail_parts),
            )
        )
    return result
