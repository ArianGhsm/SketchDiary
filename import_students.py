import argparse
import csv
import json
from typing import Dict, Tuple

from config import DEFAULT_STUDENTS_CSV
from db import init_students_table, upsert_student_records
from text_utils import normalize_numeric_input


def normalize_spaces(text: str) -> str:
    return " ".join(text.strip().split())


def combine_name(
    row: dict,
    name_col: str | None,
    first_name_col: str | None,
    last_name_col: str | None,
) -> str:
    if name_col:
        return normalize_spaces((row.get(name_col) or ""))
    first_name = normalize_spaces((row.get(first_name_col or "") or ""))
    last_name = normalize_spaces((row.get(last_name_col or "") or ""))
    return normalize_spaces(f"{first_name} {last_name}")


def parse_csv_rows(csv_path: str) -> Tuple[Dict[str, Dict], dict]:
    stats = {
        "total_rows": 0,
        "invalid_rows": 0,
        "duplicate_ids": 0,
    }
    records: Dict[str, Dict] = {}

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV header not found.")

        # Normalize header names for robust lookup.
        header_map = {h.strip().lower(): h for h in reader.fieldnames if h}
        student_id_col = header_map.get("studentid")
        name_col = header_map.get("name")
        first_name_col = header_map.get("firstname")
        last_name_col = header_map.get("lastname")
        if not student_id_col:
            raise ValueError(
                "CSV must contain 'StudentID' column."
            )
        if not name_col and not (first_name_col and last_name_col):
            raise ValueError(
                "CSV must contain either 'Name' column OR both 'FirstName' and 'LastName'."
            )

        for row in reader:
            stats["total_rows"] += 1
            student_id = normalize_numeric_input(row.get(student_id_col) or "")
            full_name = combine_name(row, name_col, first_name_col, last_name_col)

            if not student_id or not full_name:
                stats["invalid_rows"] += 1
                continue

            if student_id in records:
                stats["duplicate_ids"] += 1
            grade_fields = {}
            for col in reader.fieldnames:
                if not col:
                    continue
                normalized_col = col.strip().lower()
                if normalized_col in {"studentid", "name", "password"}:
                    continue
                value = normalize_spaces((row.get(col) or ""))
                if value:
                    grade_fields[col.strip()] = value

            records[student_id] = {
                "full_name": full_name,
                "grades_json": json.dumps(grade_fields, ensure_ascii=False),
            }

    return records, stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Import students into SQLite table 'students'. "
            "StudentID and Name (or FirstName+LastName) are imported, "
            "Password is ignored, and grade columns are saved."
        )
    )
    parser.add_argument(
        "csv_path",
        nargs="?",
        default=DEFAULT_STUDENTS_CSV,
        help="Path to source CSV file (default: config.DEFAULT_STUDENTS_CSV)",
    )
    parser.add_argument(
        "--replace-all",
        action="store_true",
        help="Delete all existing students before import",
    )
    args = parser.parse_args()

    init_students_table()
    records, stats = parse_csv_rows(args.csv_path)
    imported_count = upsert_student_records(records, replace_all=args.replace_all)

    print("Import completed.")
    print(f"Total rows read: {stats['total_rows']}")
    print(f"Invalid rows skipped: {stats['invalid_rows']}")
    print(f"Duplicate StudentID rows: {stats['duplicate_ids']}")
    print(f"Students saved (unique StudentID): {imported_count}")
    print("Password column ignored: yes")
    if args.replace_all:
        print("Mode: replace-all")
    else:
        print("Mode: upsert")


if __name__ == "__main__":
    main()
