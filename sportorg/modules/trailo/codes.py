from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Optional


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


def trailo_sort_key(split) -> tuple:
    """
    Sort order:
    - main controls first (1A, 2B, ...)
    - then time controls grouped by tc_idx:
      1TT, 1T1A, 1T2B, ... 2TT, 2T1A, ...
    """
    code = getattr(split, "code", None)
    parsed = parse_trailo_code(code)
    t = getattr(split, "time", 0)

    if parsed.kind == "main":
        return (0, parsed.main_num or 10**9, parsed.main_answer or "", parsed.raw, t)
    if parsed.kind == "tc_time":
        return (1, parsed.tc_idx or 10**9, 0, 0, "", parsed.raw, t)
    if parsed.kind == "tc_answer":
        return (
            1,
            parsed.tc_idx or 10**9,
            1,
            parsed.tc_task or 10**9,
            parsed.tc_answer or "",
            parsed.raw,
            t,
        )
    return (2, 10**9, parsed.raw, t)
