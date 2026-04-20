from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from bot.services.datetime_fa import utc_now_iso
from config import DB_PATH, DEFAULT_STUDENTS_CSV
from text_utils import normalize_numeric_input


PENDING_STATUS = "pending"
APPROVED_STATUS = "approved"
REJECTED_STATUS = "rejected"


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
                username TEXT,
                profile_text TEXT NOT NULL,
                approved_at TEXT NOT NULL,
                approved_by_tg_id INTEGER,
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
            CREATE TABLE IF NOT EXISTS verification_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id INTEGER NOT NULL,
                student_number TEXT NOT NULL,
                full_name TEXT NOT NULL,
                username TEXT,
                profile_text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                requested_at TEXT NOT NULL,
                reviewed_at TEXT,
                reviewed_by_tg_id INTEGER,
                reviewer_note TEXT,
                rep_message_refs_json TEXT NOT NULL DEFAULT '[]'
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_verification_student_number
            ON verification_requests(student_number, status)
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
                description TEXT NOT NULL DEFAULT '',
                deadline_at TEXT,
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
                username TEXT,
                joined_at TEXT NOT NULL,
                PRIMARY KEY (form_id, telegram_user_id),
                FOREIGN KEY(form_id) REFERENCES rep_forms(id)
            )
            """
        )

        _ensure_column(conn, "telegram_students", "username", "TEXT")
        _ensure_column(conn, "telegram_students", "approved_at", "TEXT")
        _ensure_column(conn, "telegram_students", "approved_by_tg_id", "INTEGER")
        _ensure_column(conn, "verification_requests", "username", "TEXT")
        _ensure_column(conn, "verification_requests", "reviewer_note", "TEXT")
        _ensure_column(conn, "verification_requests", "rep_message_refs_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(conn, "rep_forms", "description", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "rep_forms", "deadline_at", "TEXT")
        _ensure_column(conn, "rep_form_entries", "username", "TEXT")

        telegram_student_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(telegram_students)").fetchall()
        }
        if "registered_at" in telegram_student_columns:
            conn.execute(
                """
                UPDATE telegram_students
                SET approved_at = COALESCE(approved_at, registered_at)
                WHERE approved_at IS NULL
                """
            )


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, column_sql: str) -> None:
    columns = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_sql}")


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
            SELECT telegram_user_id, student_number, full_name, username, profile_text, approved_at, approved_by_tg_id
            FROM telegram_students
            WHERE telegram_user_id = ? AND is_active = 1
            """,
            (telegram_user_id,),
        ).fetchone()


def get_active_registration_by_student_number(student_number: str):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT telegram_user_id, student_number, full_name, username, profile_text, approved_at, approved_by_tg_id
            FROM telegram_students
            WHERE student_number = ? AND is_active = 1
            """,
            (student_number,),
        ).fetchone()


def list_recent_registrations(limit: int = 8):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT telegram_user_id, student_number, full_name, username, profile_text, approved_at
            FROM telegram_students
            WHERE is_active = 1
            ORDER BY approved_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def create_verification_request(
    telegram_user_id: int,
    student_number: str,
    full_name: str,
    username: str | None,
    profile_text: str,
) -> int:
    now_iso = utc_now_iso()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE verification_requests
            SET status = ?, reviewed_at = ?, reviewer_note = ?
            WHERE telegram_user_id = ? AND status = ?
            """,
            ("superseded", now_iso, "new_request_created", telegram_user_id, PENDING_STATUS),
        )
        cursor = conn.execute(
            """
            INSERT INTO verification_requests (
                telegram_user_id, student_number, full_name, username, profile_text, status, requested_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (telegram_user_id, student_number, full_name, username, profile_text, PENDING_STATUS, now_iso),
        )
    return int(cursor.lastrowid)


def get_verification_request(request_id: int):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, telegram_user_id, student_number, full_name, username, profile_text, status,
                   requested_at, reviewed_at, reviewed_by_tg_id, reviewer_note, rep_message_refs_json
            FROM verification_requests
            WHERE id = ?
            """,
            (request_id,),
        ).fetchone()


def get_pending_request_by_user_id(telegram_user_id: int):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, telegram_user_id, student_number, full_name, username, profile_text, status,
                   requested_at, reviewed_at, reviewed_by_tg_id, reviewer_note, rep_message_refs_json
            FROM verification_requests
            WHERE telegram_user_id = ? AND status = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (telegram_user_id, PENDING_STATUS),
        ).fetchone()


def list_pending_verification_requests(limit: int = 20):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, telegram_user_id, student_number, full_name, username, profile_text, requested_at
            FROM verification_requests
            WHERE status = ?
            ORDER BY requested_at ASC
            LIMIT ?
            """,
            (PENDING_STATUS, limit),
        ).fetchall()


def attach_rep_message_refs(request_id: int, refs: list[dict]) -> None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT rep_message_refs_json FROM verification_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
        existing = []
        if row and row["rep_message_refs_json"]:
            try:
                existing = json.loads(row["rep_message_refs_json"])
            except json.JSONDecodeError:
                existing = []
        existing.extend(refs)
        conn.execute(
            """
            UPDATE verification_requests
            SET rep_message_refs_json = ?
            WHERE id = ?
            """,
            (json.dumps(existing, ensure_ascii=False), request_id),
        )


def upsert_registration(
    telegram_user_id: int,
    student_number: str,
    full_name: str,
    username: str | None,
    profile_text: str,
    approved_by_tg_id: int | None,
) -> None:
    now_iso = utc_now_iso()
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
                telegram_user_id, student_number, full_name, username, profile_text, approved_at, approved_by_tg_id, is_active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (telegram_user_id, student_number, full_name, username, profile_text, now_iso, approved_by_tg_id),
        )


def decide_verification_request(
    request_id: int,
    reviewer_tg_id: int,
    approve: bool,
    reviewer_note: str | None = None,
):
    now_iso = utc_now_iso()
    decision_status = APPROVED_STATUS if approve else REJECTED_STATUS
    with get_connection() as conn:
        request_row = conn.execute(
            """
            SELECT id, telegram_user_id, student_number, full_name, username, profile_text, status
            FROM verification_requests
            WHERE id = ?
            """,
            (request_id,),
        ).fetchone()
        if not request_row:
            return None, "not_found"
        if request_row["status"] != PENDING_STATUS:
            return request_row, "already_reviewed"

        if approve:
            active = conn.execute(
                """
                SELECT telegram_user_id
                FROM telegram_students
                WHERE student_number = ? AND is_active = 1
                """,
                (request_row["student_number"],),
            ).fetchone()
            if active and active["telegram_user_id"] != request_row["telegram_user_id"]:
                conn.execute(
                    """
                    UPDATE verification_requests
                    SET status = ?, reviewed_at = ?, reviewed_by_tg_id = ?, reviewer_note = ?
                    WHERE id = ?
                    """,
                    (REJECTED_STATUS, now_iso, reviewer_tg_id, "student_number_already_linked", request_id),
                )
                updated = conn.execute(
                    "SELECT * FROM verification_requests WHERE id = ?",
                    (request_id,),
                ).fetchone()
                return updated, "student_number_already_linked"

            conn.execute(
                """
                UPDATE telegram_students
                SET is_active = 0
                WHERE student_number = ? OR telegram_user_id = ?
                """,
                (request_row["student_number"], request_row["telegram_user_id"]),
            )
            conn.execute(
                """
                INSERT INTO telegram_students (
                    telegram_user_id, student_number, full_name, username, profile_text, approved_at, approved_by_tg_id, is_active
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    request_row["telegram_user_id"],
                    request_row["student_number"],
                    request_row["full_name"],
                    request_row["username"],
                    request_row["profile_text"],
                    now_iso,
                    reviewer_tg_id,
                ),
            )

        conn.execute(
            """
            UPDATE verification_requests
            SET status = ?, reviewed_at = ?, reviewed_by_tg_id = ?, reviewer_note = ?
            WHERE id = ?
            """,
            (decision_status, now_iso, reviewer_tg_id, reviewer_note, request_id),
        )
        updated = conn.execute(
            "SELECT * FROM verification_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
    return updated, decision_status


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
    now_iso = utc_now_iso()
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
    now_iso = utc_now_iso()
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
            SELECT telegram_user_id, student_number, full_name, username, approved_at
            FROM telegram_students
            WHERE is_active = 1
            ORDER BY approved_at ASC
            """
        ).fetchall()


def create_rep_form(
    title: str,
    description: str,
    deadline_at: str | None,
    created_by_tg_id: int,
    created_by_student_number: str,
) -> int:
    now_iso = utc_now_iso()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO rep_forms (
                title, description, deadline_at, created_by_tg_id, created_by_student_number, created_at, is_active
            )
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (title, description, deadline_at, created_by_tg_id, created_by_student_number, now_iso),
        )
    return int(cursor.lastrowid)


def get_rep_form_by_id(form_id: int):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, title, description, deadline_at, created_by_tg_id, created_by_student_number, created_at, is_active
            FROM rep_forms
            WHERE id = ?
            """,
            (form_id,),
        ).fetchone()


def list_rep_forms_by_creator(created_by_tg_id: int):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, title, description, deadline_at, created_at, is_active
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
            SELECT form_id, telegram_user_id, student_number, full_name, username, joined_at
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
    username: str | None,
) -> str:
    form_row = get_rep_form_by_id(form_id)
    if not form_row or form_row["is_active"] != 1:
        return "closed"

    if get_rep_form_entry(form_id, telegram_user_id):
        return "already_joined"

    now_iso = utc_now_iso()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO rep_form_entries (form_id, telegram_user_id, student_number, full_name, username, joined_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (form_id, telegram_user_id, student_number, full_name, username, now_iso),
        )
    return "joined"


def list_rep_form_entries(form_id: int):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT form_id, telegram_user_id, student_number, full_name, username, joined_at
            FROM rep_form_entries
            WHERE form_id = ?
            ORDER BY joined_at ASC
            """,
            (form_id,),
        ).fetchall()
