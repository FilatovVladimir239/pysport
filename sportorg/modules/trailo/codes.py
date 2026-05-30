from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Literal, Optional


TrailoKind = Literal["main", "tc_time", "tc_answer", "unknown"]


@dataclass(frozen=True)
class ParsedTrailoCode:
    kind: TrailoKind
    raw: str
    # main control: e.g. "31A"
    main_num: Optional[int] = None
    main_answer: Optional[str] = None
    # time-control: e.g. "1TT", "1T2A"
    tc_idx: Optional[int] = None
    tc_task: Optional[int] = None
    tc_answer: Optional[str] = None


_RE_MAIN = re.compile(r"^(?P<num>\d+)(?P<ans>[A-Za-z])$")
# Important: legacy codes like 110TT must NOT match this "new" pattern.
# So new format is restricted to 1-2 digits of tc index.
_RE_TC_TIME_NEW = re.compile(r"^(?P<idx>\d{1,2})TT$")
_RE_TC_ANSWER_NEW = re.compile(r"^(?P<idx>\d{1,2})T(?P<task>\d+)(?P<ans>[A-Za-z])$")

# Legacy encoding used in project right now:
# 110TT (time for first time control), 111TA (answer for task 1 of time control 1)
_RE_TC_TIME_LEGACY = re.compile(r"^(?P<code>\d{3})TT$")
_RE_TC_ANSWER_LEGACY = re.compile(r"^(?P<code>\d{3})T(?P<ans>[A-Za-z])$")


def parse_trailo_code(code: str | None) -> ParsedTrailoCode:
    raw = str(code or "")

    m = _RE_TC_TIME_NEW.match(raw)
    if m:
        return ParsedTrailoCode(kind="tc_time", raw=raw, tc_idx=int(m.group("idx")))

    m = _RE_TC_ANSWER_NEW.match(raw)
    if m:
        return ParsedTrailoCode(
            kind="tc_answer",
            raw=raw,
            tc_idx=int(m.group("idx")),
            tc_task=int(m.group("task")),
            tc_answer=m.group("ans").upper(),
        )

    m = _RE_TC_TIME_LEGACY.match(raw)
    if m:
        n = int(m.group("code"))
        # 110 -> tc 1, 120 -> tc 2 ...
        tc_idx = (n // 10) - 10
        return ParsedTrailoCode(kind="tc_time", raw=raw, tc_idx=tc_idx)

    m = _RE_TC_ANSWER_LEGACY.match(raw)
    if m:
        n = int(m.group("code"))
        tc_idx = (n // 10) - 10
        tc_task = n % 10
        return ParsedTrailoCode(
            kind="tc_answer",
            raw=raw,
            tc_idx=tc_idx,
            tc_task=tc_task,
            tc_answer=m.group("ans").upper(),
        )

    m = _RE_MAIN.match(raw)
    if m:
        return ParsedTrailoCode(
            kind="main",
            raw=raw,
            main_num=int(m.group("num")),
            main_answer=m.group("ans").upper(),
        )

    return ParsedTrailoCode(kind="unknown", raw=raw)


def implicit_tc_time_code_for_tc_answer(parsed: ParsedTrailoCode) -> Optional[str]:
    """
    Если в дистанции заданы только ответы тайм‑КП (1T1A, …) без строки отметки времени
    (1TT / 110TT), возвращает код неявной отметки времени для того же номера ТК.
    """
    if parsed.kind != "tc_answer" or parsed.tc_idx is None:
        return None
    raw = parsed.raw
    if _RE_TC_ANSWER_NEW.match(raw):
        return f"{parsed.tc_idx}TT"
    if _RE_TC_ANSWER_LEGACY.match(raw):
        return f"{(10 + parsed.tc_idx) * 10}TT"
    return None


def expand_trailo_control_code_strings(control_codes: List[str]) -> List[str]:
    """
    Вставляет перед первым ответом каждого тайм‑КП неявный код отметки времени (NTT),
    если для этого tc_idx в списке ещё нет tc_time. Исходный список в файле не меняется —
    используется только при расчёте сплитов и отчётах.
    """
    if not control_codes:
        return list(control_codes)
    parsed_list = [parse_trailo_code(c) for c in control_codes]
    have_time_idx = {
        p.tc_idx
        for p in parsed_list
        if p.kind == "tc_time" and p.tc_idx is not None
    }
    out: List[str] = []
    inserted: set[int] = set()
    for raw, p in zip(control_codes, parsed_list):
        if p.kind == "tc_answer" and p.tc_idx is not None:
            idx = p.tc_idx
            if idx not in have_time_idx and idx not in inserted:
                tt = implicit_tc_time_code_for_tc_answer(p)
                if tt:
                    out.append(tt)
                    inserted.add(idx)
                    have_time_idx.add(idx)
        out.append(raw)
    return out


def trailo_course_expanded_control_codes(course) -> List[str]:
    if course is None:
        return []
    controls = getattr(course, "controls", None) or []
    if not controls:
        return []
    return expand_trailo_control_code_strings([str(c.code) for c in controls])


def trailo_expected_answer_letter_for_split(
    split, expanded_codes: List[str]
) -> Optional[str]:
    """
    Ожидаемая буква ответа с дистанции для сплита (основной КП или задача тайм‑КП).
    """
    idx = int(getattr(split, "course_index", -1) or -1)
    if expanded_codes and 0 <= idx < len(expanded_codes):
        p_ctrl = parse_trailo_code(expanded_codes[idx])
        if p_ctrl.kind == "main" and p_ctrl.main_answer:
            return str(p_ctrl.main_answer).upper()
        if p_ctrl.kind == "tc_answer" and p_ctrl.tc_answer:
            return str(p_ctrl.tc_answer).upper()
    parsed = parse_trailo_code(getattr(split, "code", None))
    if parsed.kind == "main" and parsed.main_num is not None:
        for raw in expanded_codes:
            pc = parse_trailo_code(raw)
            if pc.kind == "main" and pc.main_num == parsed.main_num and pc.main_answer:
                return str(pc.main_answer).upper()
    if (
        parsed.kind == "tc_answer"
        and parsed.tc_idx is not None
        and parsed.tc_task is not None
    ):
        for raw in expanded_codes:
            pc = parse_trailo_code(raw)
            if (
                pc.kind == "tc_answer"
                and pc.tc_idx == parsed.tc_idx
                and pc.tc_task == parsed.tc_task
                and pc.tc_answer
            ):
                return str(pc.tc_answer).upper()
    return None


def trailo_correctness_mark(is_correct: bool, expected_letter: Optional[str]) -> str:
    if is_correct:
        return "(+)"
    if expected_letter:
        return f"({str(expected_letter).upper()})"
    return "(?)"


def trailo_main_control_display_code(
    parsed: ParsedTrailoCode, prev_main_num: Optional[int]
) -> str:
    """
    Main-control label in a split sequence: same CP number as previous punch
    (another answer) -> '--B'; otherwise full code '12A'.
    """
    if parsed.kind != "main":
        return parsed.raw
    ans = (parsed.main_answer or "").upper()
    if prev_main_num is not None and parsed.main_num == prev_main_num:
        return f"--{ans}"
    num = parsed.main_num if parsed.main_num is not None else 0
    return f"{num:02d}{ans}"


def trailo_sort_key(split) -> tuple:
    """
    Sort order:
    - main controls first (1A, 2B, ...) by CP number, then punch time on same CP
    - then time controls grouped by tc_idx:
      1TT, 1T1A, 1T2B, ... 2TT, 2T1A, ...
    """
    code = getattr(split, "code", None)
    parsed = parse_trailo_code(code)
    t_msec = trailo_split_time_msec(split)

    if parsed.kind == "main":
        return (0, parsed.main_num or 10**9, t_msec, parsed.raw)
    if parsed.kind == "tc_time":
        return (1, parsed.tc_idx or 10**9, 0, 0, "", parsed.raw, t_msec)
    if parsed.kind == "tc_answer":
        return (
            1,
            parsed.tc_idx or 10**9,
            1,
            parsed.tc_task or 10**9,
            parsed.tc_answer or "",
            parsed.raw,
            t_msec,
        )
    return (2, 10**9, parsed.raw, t_msec)


def trailo_split_time_msec(split) -> int:
    t = getattr(split, "time", None)
    if t is None:
        return 2**62
    if hasattr(t, "to_msec"):
        return int(t.to_msec())
    return int(t)


def trailo_splits_matching_control(splits, control_code: str) -> List:
    """All athlete punches that belong to the same TrailO control."""
    cp = parse_trailo_code(control_code)
    matching = []
    for split in splits:
        sp = parse_trailo_code(getattr(split, "code", None))
        if cp.kind == "main" and sp.kind == "main":
            if sp.main_num == cp.main_num:
                matching.append(split)
        elif cp.kind == "tc_time" and sp.kind == "tc_time":
            if sp.tc_idx == cp.tc_idx:
                matching.append(split)
        elif cp.kind == "tc_answer" and sp.kind == "tc_answer":
            if sp.tc_idx == cp.tc_idx and sp.tc_task == cp.tc_task:
                matching.append(split)
        else:
            code = str(control_code or "")
            raw = str(getattr(split, "code", "") or "")
            if code and raw and raw[:-1] == code[:-1]:
                matching.append(split)
    return matching


def trailo_first_split_for_control(splits, control_code: str):
    """Earliest punch for a control; later re-punches on the same CP are ignored."""
    matching = trailo_splits_matching_control(splits, control_code)
    if not matching:
        return None
    return min(matching, key=trailo_split_time_msec)
