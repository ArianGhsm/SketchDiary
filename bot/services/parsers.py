from __future__ import annotations

import re
from typing import List, Tuple

from text_utils import normalize_numeric_input
from bot.services.policies import normalize_student_number


def parse_grade_line(line: str) -> Tuple[str, str]:
    normalized = normalize_numeric_input(line)
    normalized = normalized.replace("،", ",").replace("؛", ",").replace(";", ",")
    parts = [p.strip() for p in normalized.split(",", 1)]

    if len(parts) == 2 and parts[0] and parts[1]:
        student_number = normalize_student_number(parts[0])
        grade_value = normalize_numeric_input(parts[1])
    else:
        tokens = normalized.split()
        if len(tokens) < 2:
            raise ValueError("invalid format")
        student_number = normalize_student_number(tokens[0])
        grade_value = normalize_numeric_input(" ".join(tokens[1:]))

    if not student_number or not grade_value:
        raise ValueError("missing values")
    if not re.fullmatch(r"\d+", student_number):
        raise ValueError("student number must be numeric")

    return student_number, grade_value


def parse_grade_list_text(text: str) -> Tuple[List[Tuple[str, str]], List[str]]:
    grade_entries: List[Tuple[str, str]] = []
    invalid_lines: List[str] = []

    for index, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            grade_entries.append(parse_grade_line(line))
        except ValueError:
            invalid_lines.append(f"{index}: {line}")

    return grade_entries, invalid_lines


def parse_id_from_callback(data: str, prefix: str) -> int | None:
    if not data.startswith(prefix):
        return None
    raw = data[len(prefix) :]
    if not raw.isdigit():
        return None
    return int(raw)
