import json
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from text_utils import normalize_numeric_input


@dataclass(frozen=True)
class RankingItem:
    student_number: str
    full_name: str
    average: float
    numeric_count: int


@dataclass(frozen=True)
class GradeInsights:
    personal_average: Optional[float]
    rank_position: Optional[int]
    rank_total: int
    class_average: Optional[float]
    delta_from_class_average: Optional[float]
    top_student_name: Optional[str]
    top_student_average: Optional[float]


def parse_numeric_grade(value: str) -> Optional[float]:
    if value is None:
        return None
    text = normalize_numeric_input(value)
    text = text.replace("٫", ".").replace("٬", "").replace(",", ".")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def extract_numeric_items(grades: Dict[str, str]) -> List[Tuple[str, float]]:
    numeric_items: List[Tuple[str, float]] = []
    for key, value in grades.items():
        parsed = parse_numeric_grade(str(value))
        if parsed is not None:
            numeric_items.append((key, parsed))
    return numeric_items


def build_class_ranking(students_with_grades: Iterable) -> List[RankingItem]:
    ranking: List[RankingItem] = []
    for row in students_with_grades:
        try:
            grades = json.loads(row["grades_json"])
        except json.JSONDecodeError:
            continue
        numeric_items = extract_numeric_items(grades)
        if not numeric_items:
            continue
        average = sum(item[1] for item in numeric_items) / len(numeric_items)
        ranking.append(
            RankingItem(
                student_number=row["student_number"],
                full_name=row["full_name"],
                average=average,
                numeric_count=len(numeric_items),
            )
        )
    ranking.sort(key=lambda x: x.average, reverse=True)
    return ranking


def build_grade_insights(
    student_number: str,
    grade_items: List[Tuple[str, float]],
    class_ranking: List[RankingItem],
) -> GradeInsights:
    if not grade_items:
        return GradeInsights(
            personal_average=None,
            rank_position=None,
            rank_total=len(class_ranking),
            class_average=None,
            delta_from_class_average=None,
            top_student_name=None,
            top_student_average=None,
        )

    personal_average = sum(item[1] for item in grade_items) / len(grade_items)

    rank_position = None
    for index, item in enumerate(class_ranking, start=1):
        if item.student_number == student_number:
            rank_position = index
            break

    if not class_ranking:
        return GradeInsights(
            personal_average=personal_average,
            rank_position=rank_position,
            rank_total=0,
            class_average=None,
            delta_from_class_average=None,
            top_student_name=None,
            top_student_average=None,
        )

    class_average = sum(item.average for item in class_ranking) / len(class_ranking)
    top_student = class_ranking[0]

    return GradeInsights(
        personal_average=personal_average,
        rank_position=rank_position,
        rank_total=len(class_ranking),
        class_average=class_average,
        delta_from_class_average=personal_average - class_average,
        top_student_name=top_student.full_name,
        top_student_average=top_student.average,
    )
