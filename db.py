import sqlite3
import json
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from config import DB_PATH, DEFAULT_STUDENTS_CSV
from text_utils import normalize_numeric_input


def get_connection() -> sqlite3.Connection:
    db_file = Path(DB_PATH)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                student_number TEXT PRIMARY KEY,
                full_name TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS telegram_students (
                telegram_user_id INTEGER PRIMARY KEY,
                student_number TEXT NOT NULL,
                full_name TEXT NOT NULL,
                profile_text TEXT NOT NULL,
                registered_at TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY(student_number) REFERENCES students(student_number)
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_active_student_number
            ON telegram_students(student_number)
            WHERE is_active = 1
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS student_grades (
                student_number TEXT PRIMARY KEY,
                grades_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(student_number) REFERENCES students(student_number)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rep_forms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_by_tg_id INTEGER NOT NULL,
                created_by_student_number TEXT NOT NULL,
                created_at TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rep_form_entries (
                form_id INTEGER NOT NULL,
                telegram_user_id INTEGER NOT NULL,
                student_number TEXT NOT NULL,
                full_name TEXT NOT NULL,
                joined_at TEXT NOT NULL,
                PRIMARY KEY (form_id, telegram_user_id),
                FOREIGN KEY(form_id) REFERENCES rep_forms(id)
            )
            """
        )


def _normalize_spaces(text: str) -> str:
    return " ".join(str(text).strip().split())


def _compose_full_name(row: dict, name_col: str | None, first_col: str | None, last_col: str | None) -> str:
    if name_col:
        return _normalize_spaces(row.get(name_col, ""))
    first_name = _normalize_spaces(row.get(first_col or "", ""))
    last_name = _normalize_spaces(row.get(last_col or "", ""))
    return _normalize_spaces(f"{first_name} {last_name}")


def init_students_table() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                student_number TEXT PRIMARY KEY,
                full_name TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS student_grades (
                student_number TEXT PRIMARY KEY,
                grades_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(student_number) REFERENCES students(student_number)
            )
            """
        )


def ensure_students_seeded_from_default_csv() -> Dict[str, str | int]:
    """
    Seed students table from default CSV only when students table is empty.
    This prevents 'student number not found' on fresh runs.
    """
    with get_connection() as conn:
        count_row = conn.execute("SELECT COUNT(*) AS cnt FROM students").fetchone()
        if count_row and count_row["cnt"] > 0:
            return {"status": "skipped", "reason": "students_table_not_empty", "count": count_row["cnt"]}

    csv_path = Path(DEFAULT_STUDENTS_CSV)
    if not csv_path.exists():
        return {"status": "skipped", "reason": "default_csv_not_found", "count": 0}

    records: Dict[str, Dict[str, str]] = {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            return {"status": "skipped", "reason": "csv_header_not_found", "count": 0}

        header_map = {h.strip().lower(): h for h in reader.fieldnames if h}
        student_id_col = header_map.get("studentid")
        name_col = header_map.get("name")
        first_name_col = header_map.get("firstname")
        last_name_col = header_map.get("lastname")

        if not student_id_col:
            return {"status": "skipped", "reason": "studentid_column_missing", "count": 0}
        if not name_col and not (first_name_col and last_name_col):
            return {"status": "skipped", "reason": "name_columns_missing", "count": 0}

        for row in reader:
            student_id = normalize_numeric_input(row.get(student_id_col, ""))
            full_name = _compose_full_name(row, name_col, first_name_col, last_name_col)
            if not student_id or not full_name:
                continue

            grade_fields = {}
            for col in reader.fieldnames:
                if not col:
                    continue
                normalized_col = col.strip().lower()
                if normalized_col in {"studentid", "name", "firstname", "lastname", "password"}:
                    continue
                value = _normalize_spaces(row.get(col, ""))
                if value:
                    grade_fields[col.strip()] = value

            records[student_id] = {
                "full_name": full_name,
                "grades_json": json.dumps(grade_fields, ensure_ascii=False),
            }

    if not records:
        return {"status": "skipped", "reason": "no_valid_rows", "count": 0}

    inserted = upsert_student_records(records, replace_all=False)
    return {"status": "seeded", "reason": "ok", "count": inserted}


def find_student(student_number: str):
    with get_connection() as conn:
        return conn.execute(
            "SELECT student_number, full_name FROM students WHERE student_number = ?",
            (student_number,),
        ).fetchone()


def get_active_registration_by_tg_id(telegram_user_id: int):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT telegram_user_id, student_number, full_name, profile_text, registered_at
            FROM telegram_students
            WHERE telegram_user_id = ? AND is_active = 1
            """,
            (telegram_user_id,),
        ).fetchone()


def get_active_registration_by_student_number(student_number: str):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT telegram_user_id, student_number, full_name, profile_text, registered_at
            FROM telegram_students
            WHERE student_number = ? AND is_active = 1
            """,
            (student_number,),
        ).fetchone()


def upsert_registration(
    telegram_user_id: int,
    student_number: str,
    full_name: str,
    profile_text: str,
) -> None:
    now_iso = datetime.utcnow().isoformat(timespec="seconds")
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE telegram_students
            SET is_active = 0
            WHERE student_number = ? OR telegram_user_id = ?
            """,
            (student_number, telegram_user_id),
        )
        conn.execute(
            """
            INSERT INTO telegram_students (
                telegram_user_id, student_number, full_name, profile_text, registered_at, is_active
            )
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (telegram_user_id, student_number, full_name, profile_text, now_iso),
        )


def deactivate_student(student_number: str) -> int:
    with get_connection() as conn:
        result = conn.execute(
            """
            UPDATE telegram_students
            SET is_active = 0
            WHERE student_number = ? AND is_active = 1
            """,
            (student_number,),
        )
    return result.rowcount


def upsert_students(students: Dict[str, str], replace_all: bool) -> int:
    with get_connection() as conn:
        if replace_all:
            conn.execute("DELETE FROM students")

        conn.executemany(
            """
            INSERT INTO students (student_number, full_name)
            VALUES (?, ?)
            ON CONFLICT(student_number) DO UPDATE SET full_name = excluded.full_name
            """,
            [(student_id, full_name) for student_id, full_name in students.items()],
        )
    return len(students)


def upsert_student_records(records: Dict[str, Dict], replace_all: bool) -> int:
    now_iso = datetime.utcnow().isoformat(timespec="seconds")
    with get_connection() as conn:
        if replace_all:
            conn.execute("DELETE FROM student_grades")
            conn.execute("DELETE FROM students")

        conn.executemany(
            """
            INSERT INTO students (student_number, full_name)
            VALUES (?, ?)
            ON CONFLICT(student_number) DO UPDATE SET full_name = excluded.full_name
            """,
            [
                (student_id, row_data["full_name"])
                for student_id, row_data in records.items()
            ],
        )
        conn.executemany(
            """
            INSERT INTO student_grades (student_number, grades_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(student_number) DO UPDATE SET
                grades_json = excluded.grades_json,
                updated_at = excluded.updated_at
            """,
            [
                (student_id, row_data["grades_json"], now_iso)
                for student_id, row_data in records.items()
            ],
        )
    return len(records)


def get_student_grades(student_number: str):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT student_number, grades_json, updated_at
            FROM student_grades
            WHERE student_number = ?
            """,
            (student_number,),
        ).fetchone()


def list_students_with_grades():
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT s.student_number, s.full_name, g.grades_json, g.updated_at
            FROM students s
            JOIN student_grades g ON g.student_number = s.student_number
            """
        ).fetchall()


def bulk_upsert_course_grades(
    course_title: str, grade_entries: Iterable[Tuple[str, str]]
) -> Dict[str, List[str] | int]:
    now_iso = datetime.utcnow().isoformat(timespec="seconds")
    result = {
        "updated_count": 0,
        "missing_students": [],
    }

    with get_connection() as conn:
        for student_number, grade_value in grade_entries:
            student = conn.execute(
                "SELECT student_number FROM students WHERE student_number = ?",
                (student_number,),
            ).fetchone()
            if not student:
                result["missing_students"].append(student_number)
                continue

            grade_row = conn.execute(
                "SELECT grades_json FROM student_grades WHERE student_number = ?",
                (student_number,),
            ).fetchone()

            grades = {}
            if grade_row and grade_row["grades_json"]:
                try:
                    grades = json.loads(grade_row["grades_json"])
                except json.JSONDecodeError:
                    grades = {}

            grades[course_title] = grade_value
            conn.execute(
                """
                INSERT INTO student_grades (student_number, grades_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(student_number) DO UPDATE SET
                    grades_json = excluded.grades_json,
                    updated_at = excluded.updated_at
                """,
                (student_number, json.dumps(grades, ensure_ascii=False), now_iso),
            )
            result["updated_count"] += 1

    return result


def list_active_registered_users():
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT telegram_user_id, student_number, full_name
            FROM telegram_students
            WHERE is_active = 1
            """
        ).fetchall()


def create_rep_form(
    title: str,
    created_by_tg_id: int,
    created_by_student_number: str,
) -> int:
    now_iso = datetime.utcnow().isoformat(timespec="seconds")
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO rep_forms (title, created_by_tg_id, created_by_student_number, created_at, is_active)
            VALUES (?, ?, ?, ?, 1)
            """,
            (title, created_by_tg_id, created_by_student_number, now_iso),
        )
    return int(cursor.lastrowid)


def get_rep_form_by_id(form_id: int):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, title, created_by_tg_id, created_by_student_number, created_at, is_active
            FROM rep_forms
            WHERE id = ?
            """,
            (form_id,),
        ).fetchone()


def list_rep_forms_by_creator(created_by_tg_id: int):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, title, created_at, is_active
            FROM rep_forms
            WHERE created_by_tg_id = ?
            ORDER BY id DESC
            """,
            (created_by_tg_id,),
        ).fetchall()


def get_rep_form_entry(form_id: int, telegram_user_id: int):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT form_id, telegram_user_id, student_number, full_name, joined_at
            FROM rep_form_entries
            WHERE form_id = ? AND telegram_user_id = ?
            """,
            (form_id, telegram_user_id),
        ).fetchone()


def add_rep_form_entry(
    form_id: int,
    telegram_user_id: int,
    student_number: str,
    full_name: str,
) -> str:
    form_row = get_rep_form_by_id(form_id)
    if not form_row or form_row["is_active"] != 1:
        return "closed"

    if get_rep_form_entry(form_id, telegram_user_id):
        return "already_joined"

    now_iso = datetime.utcnow().isoformat(timespec="seconds")
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO rep_form_entries (form_id, telegram_user_id, student_number, full_name, joined_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (form_id, telegram_user_id, student_number, full_name, now_iso),
        )
    return "joined"


def list_rep_form_entries(form_id: int):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT form_id, telegram_user_id, student_number, full_name, joined_at
            FROM rep_form_entries
            WHERE form_id = ?
            ORDER BY joined_at ASC
            """,
            (form_id,),
        ).fetchall()
