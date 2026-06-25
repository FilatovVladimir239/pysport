"""Per-course control lists and earliest-punch rules for rogaine scoring."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sportorg.models.memory import Course, Result, Split


def parse_allowed_control_codes(text: str) -> List[str]:
    """Parse allowed CP codes from comma/newline/space separated text."""
    if not text or not str(text).strip():
        return []
    codes: List[str] = []
    for token in re.split(r"[\s,;]+", str(text).strip()):
        token = token.strip()
        if token and token not in codes:
            codes.append(token)
    return codes


def format_allowed_control_codes(codes: List[str]) -> str:
    if not codes:
        return ""
    return ", ".join(str(code) for code in codes)


def parse_rogaine_course_control_codes(text: str) -> List[str]:
    """Parse one CP code per line (first token only; leg length is ignored)."""
    codes: List[str] = []
    if not text or not str(text).strip():
        return codes
    for line in str(text).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        code = line.split()[0]
        if code and code not in codes:
            codes.append(code)
    return codes


def format_rogaine_course_control_codes(controls, allowed_codes=None) -> str:
    codes: List[str] = []
    if controls:
        codes = [str(control.code).strip() for control in controls if str(control.code).strip()]
    if not codes and allowed_codes:
        codes = [str(code).strip() for code in allowed_codes if str(code).strip()]
    return "\n".join(codes)


def parse_control_start_delay_minutes(text: str) -> Dict[str, int]:
    """Parse lines like '45 60' or '45=60' (minutes after personal start)."""
    rules: Dict[str, int] = {}
    if not text or not str(text).strip():
        return rules
    for line in str(text).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            code_part, minutes_part = line.split("=", 1)
        else:
            parts = line.split()
            if len(parts) < 2:
                continue
            code_part, minutes_part = parts[0], parts[1]
        code = str(code_part).strip()
        if not code:
            continue
        try:
            minutes = int(str(minutes_part).strip())
        except ValueError:
            continue
        if minutes < 0:
            continue
        rules[code] = minutes
    return rules


def format_control_start_delay_minutes(rules: Dict[str, int]) -> str:
    if not rules:
        return ""
    lines = []
    for code in sorted(rules, key=lambda item: (len(item), item)):
        lines.append("{} {}".format(code, rules[code]))
    return "\n".join(lines)


def parse_control_chain_bonuses(text: str) -> List[Dict[str, Any]]:
    """Parse lines like '45 67 32 5' or '45,67,32=5' (consecutive CP chain bonus)."""
    chains: List[Dict[str, Any]] = []
    if not text or not str(text).strip():
        return chains
    for line in str(text).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            codes_part, bonus_part = line.split("=", 1)
            code_tokens = re.split(r"[\s,;]+", codes_part.strip())
        else:
            parts = re.split(r"[\s,;]+", line)
            if len(parts) < 2:
                continue
            bonus_part = parts[-1]
            code_tokens = parts[:-1]
        codes = [str(code).strip() for code in code_tokens if str(code).strip()]
        if len(codes) < 2:
            continue
        try:
            bonus = int(str(bonus_part).strip())
        except ValueError:
            continue
        if bonus <= 0:
            continue
        chains.append({"codes": codes, "bonus": bonus})
    return chains


def format_control_chain_bonuses(chains: List[Dict[str, Any]]) -> str:
    if not chains:
        return ""
    lines = []
    for chain in chains:
        codes = chain.get("codes") or []
        bonus = chain.get("bonus")
        if len(codes) < 2 or not bonus:
            continue
        lines.append("{} {}".format(" ".join(str(code) for code in codes), bonus))
    return "\n".join(lines)


def calculate_control_chain_bonus(
    punch_codes: List[str], chains: List[Dict[str, Any]]
) -> int:
    """Sum bonuses for each non-overlapping consecutive chain match on the card."""
    if not punch_codes or not chains:
        return 0
    sequence = [str(code).strip() for code in punch_codes if str(code).strip()]
    total = 0
    for chain in chains:
        pattern = [str(code).strip() for code in (chain.get("codes") or [])]
        bonus = int(chain.get("bonus") or 0)
        if len(pattern) < 2 or bonus <= 0:
            continue
        index = 0
        while index <= len(sequence) - len(pattern):
            if sequence[index : index + len(pattern)] == pattern:
                total += bonus
                index += len(pattern)
            else:
                index += 1
    return total


def resolve_scoring_course(result: "Result") -> Optional["Course"]:
    """Course assigned to the group, or matched by bib/name."""
    from sportorg.models.memory import race

    if result.person and result.person.group and result.person.group.course:
        return result.person.group.course
    return race().find_course(result)


def split_counts_for_course_score(
    result: "Result", split: "Split", course: Optional["Course"]
) -> bool:
    """Return True if this punch may contribute to rogaine score for the course."""
    if course is None:
        return True

    code = str(split.code).strip()
    if not code:
        return False

    allowed = getattr(course, "allowed_control_codes", None) or []
    if allowed and code not in allowed:
        return False

    delays = getattr(course, "control_start_delay_minutes", None) or {}
    min_minutes = delays.get(code)
    if not min_minutes:
        return True

    start_time = result.get_start_time()
    punch_time = split.time
    if start_time.to_msec() <= 0 or punch_time.to_msec() <= 0:
        return True

    elapsed_msec = punch_time.to_msec() - start_time.to_msec()
    return elapsed_msec >= min_minutes * 60 * 1000


def rogaine_split_skip_reason(
    result: "Result", split: "Split", course: Optional["Course"]
) -> str:
    """Return skip reason code for a split that does not count toward rogaine score."""
    if course is None:
        return ""

    code = str(split.code).strip()
    if not code:
        return "empty"

    allowed = getattr(course, "allowed_control_codes", None) or []
    if allowed and code not in allowed:
        return "not_allowed"

    delays = getattr(course, "control_start_delay_minutes", None) or {}
    min_minutes = delays.get(code)
    if not min_minutes:
        return ""

    start_time = result.get_start_time()
    punch_time = split.time
    if start_time.to_msec() <= 0 or punch_time.to_msec() <= 0:
        return ""

    elapsed_msec = punch_time.to_msec() - start_time.to_msec()
    if elapsed_msec < min_minutes * 60 * 1000:
        return "early"
    return ""


def build_rogaine_score_breakdown(result: "Result") -> Dict[str, Any]:
    """Build per-split rogaine points and bonus summary for display."""
    from sportorg.models.memory import race
    from sportorg.models.result.result_checker import ResultChecker

    allow_duplicates = race().get_setting(
        "result_processing_scores_allow_duplicates", False
    )
    course = resolve_scoring_course(result)
    splits_info: List[Dict[str, Any]] = []
    counted_codes: List[str] = []
    cp_score = 0

    for split in result.splits:
        code = str(split.code).strip()
        entry: Dict[str, Any] = {
            "code": code,
            "counts": False,
            "points": 0,
            "skip_reason": "",
        }
        if not split_counts_for_course_score(result, split, course):
            entry["skip_reason"] = rogaine_split_skip_reason(result, split, course)
        elif code in counted_codes and not allow_duplicates:
            entry["skip_reason"] = "duplicate"
        else:
            points = ResultChecker.get_control_score(code)
            entry["counts"] = True
            entry["points"] = points
            cp_score += points
            counted_codes.append(code)
        splits_info.append(entry)

    punch_codes = [str(split.code) for split in result.splits]
    chains = getattr(course, "control_chain_bonuses", None) or [] if course else []
    chain_bonus = calculate_control_chain_bonus(punch_codes, chains)

    return {
        "splits": splits_info,
        "cp_score": cp_score,
        "chain_bonus": chain_bonus,
        "gross_score": cp_score + chain_bonus,
    }
