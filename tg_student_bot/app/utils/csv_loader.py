from __future__ import annotations
import csv
from pathlib import Path
from typing import Iterable

REGISTRY_PATH = Path("data/registry/students.csv")
GRADES_DIR = Path("data/grades")


def iter_registry_rows() -> Iterable[dict[str, str]]:
    if not REGISTRY_PATH.exists():
        return []
    with REGISTRY_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield {k.strip(): (v or "").strip() for k, v in row.items()}


def list_courses() -> list[str]:
    if not GRADES_DIR.exists():
        return []
    out = [p.stem for p in GRADES_DIR.glob("*.csv")]
    out.sort()
    return out


def get_grade(course: str, student_id: str) -> str | None:
    path = GRADES_DIR / f"{course}.csv"
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sid = (row.get("student_id") or "").strip()
            if sid == student_id:
                g = (row.get("grade") or row.get("score") or "").strip()
                return g or None
    return None
