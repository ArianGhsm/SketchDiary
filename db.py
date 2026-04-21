from __future__ import annotations

import csv
import json
import secrets
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from bot.services.datetime_fa import utc_now_iso
from config import DEFAULT_STUDENTS_CSV, DB_PATH, MAIN_REP_STUDENT_NUMBER, MAIN_REP_TELEGRAM_ID
from text_utils import normalize_numeric_input

PENDING_STATUS = "pending"
APPROVED_STATUS = "approved"
REJECTED_STATUS = "rejected"

FORM_STATUS_DRAFT = "draft"
FORM_STATUS_OPEN = "open"
FORM_STATUS_CLOSED = "closed"

SUBMISSION_STATUS_SUBMITTED = "submitted"
SUBMISSION_STATUS_WAITLIST = "waitlist"
SUBMISSION_STATUS_REMOVED = "removed"


def get_connection() -> sqlite3.Connection:
    db_file = Path(DB_PATH)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, column_sql: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_sql}")


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
            CREATE TABLE IF NOT EXISTS representatives (
                student_number TEXT PRIMARY KEY,
                telegram_user_id INTEGER UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                is_owner INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
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
            CREATE TABLE IF NOT EXISTS forms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                share_token TEXT UNIQUE NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                deadline_at TEXT,
                capacity INTEGER,
                waitlist_enabled INTEGER NOT NULL DEFAULT 0,
                created_by_tg_id INTEGER NOT NULL,
                created_by_student_number TEXT NOT NULL,
                created_at TEXT NOT NULL,
                closed_at TEXT,
                announcement_channel_id INTEGER,
                source_form_id INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS form_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                form_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                field_type TEXT NOT NULL,
                label TEXT NOT NULL,
                is_required INTEGER NOT NULL DEFAULT 1,
                options_json TEXT NOT NULL DEFAULT '[]',
                settings_json TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY(form_id) REFERENCES forms(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS form_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                form_id INTEGER NOT NULL,
                telegram_user_id INTEGER NOT NULL,
                student_number TEXT NOT NULL,
                full_name TEXT NOT NULL,
                username TEXT,
                status TEXT NOT NULL DEFAULT 'submitted',
                submitted_at TEXT NOT NULL,
                registration_order INTEGER NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(form_id, telegram_user_id),
                FOREIGN KEY(form_id) REFERENCES forms(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS submission_answers (
                submission_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                answer_text TEXT,
                answer_json TEXT NOT NULL DEFAULT '[]',
                PRIMARY KEY (submission_id, question_id),
                FOREIGN KEY(submission_id) REFERENCES form_submissions(id),
                FOREIGN KEY(question_id) REFERENCES form_questions(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS form_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_form_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                post_at TEXT NOT NULL,
                registration_deadline_at TEXT,
                recurring_rule TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                last_run_at TEXT,
                created_by_tg_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(template_form_id) REFERENCES forms(id)
            )
            """
        )

        _ensure_column(conn, "telegram_students", "username", "TEXT")
        _ensure_column(conn, "telegram_students", "approved_at", "TEXT")
        _ensure_column(conn, "telegram_students", "approved_by_tg_id", "INTEGER")
        _ensure_column(conn, "telegram_students", "is_active", "INTEGER NOT NULL DEFAULT 1")
        _ensure_column(conn, "verification_requests", "username", "TEXT")
        _ensure_column(conn, "verification_requests", "reviewer_note", "TEXT")
        _ensure_column(conn, "verification_requests", "rep_message_refs_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(conn, "forms", "share_token", "TEXT")
        _ensure_column(conn, "forms", "description", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "forms", "status", "TEXT NOT NULL DEFAULT 'draft'")
        _ensure_column(conn, "forms", "deadline_at", "TEXT")
        _ensure_column(conn, "forms", "capacity", "INTEGER")
        _ensure_column(conn, "forms", "waitlist_enabled", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "forms", "closed_at", "TEXT")
        _ensure_column(conn, "forms", "announcement_channel_id", "INTEGER")
        _ensure_column(conn, "forms", "source_form_id", "INTEGER")
        _ensure_column(conn, "form_questions", "options_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(conn, "form_questions", "settings_json", "TEXT NOT NULL DEFAULT '{}'")
        _ensure_column(conn, "form_submissions", "status", "TEXT NOT NULL DEFAULT 'submitted'")
        _ensure_column(conn, "form_submissions", "registration_order", "INTEGER NOT NULL DEFAULT 1")
        _ensure_column(conn, "form_submissions", "updated_at", "TEXT")
        _ensure_column(conn, "submission_answers", "answer_text", "TEXT")
        _ensure_column(conn, "submission_answers", "answer_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(conn, "form_schedules", "registration_deadline_at", "TEXT")
        _ensure_column(conn, "form_schedules", "recurring_rule", "TEXT")
        _ensure_column(conn, "form_schedules", "last_run_at", "TEXT")

        for row in conn.execute("SELECT id, share_token FROM forms").fetchall():
            if not row["share_token"]:
                conn.execute("UPDATE forms SET share_token = ? WHERE id = ?", (_generate_share_token(), row["id"]))

        telegram_student_columns = {row["name"] for row in conn.execute("PRAGMA table_info(telegram_students)").fetchall()}
        if "registered_at" in telegram_student_columns:
            conn.execute(
                """
                UPDATE telegram_students
                SET approved_at = COALESCE(approved_at, registered_at)
                WHERE approved_at IS NULL OR approved_at = ''
                """
            )
        conn.execute(
            """
            UPDATE telegram_students
            SET approved_at = COALESCE(NULLIF(approved_at, ''), ?)
            WHERE approved_at IS NULL OR approved_at = ''
            """,
            (utc_now_iso(),),
        )
        conn.execute(
            """
            UPDATE verification_requests
            SET rep_message_refs_json = '[]'
            WHERE rep_message_refs_json IS NULL OR rep_message_refs_json = ''
            """
        )

    ensure_default_representative()


def ensure_default_representative() -> None:
    if not MAIN_REP_TELEGRAM_ID or not MAIN_REP_STUDENT_NUMBER:
        return
    with get_connection() as conn:
        student = conn.execute(
            "SELECT full_name FROM students WHERE student_number = ?",
            (MAIN_REP_STUDENT_NUMBER,),
        ).fetchone()
        full_name = student["full_name"] if student else "نماینده اصلی کلاس"
        conn.execute(
            """
            INSERT INTO representatives (student_number, telegram_user_id, full_name, is_owner, is_active, created_at)
            VALUES (?, ?, ?, 1, 1, ?)
            ON CONFLICT(student_number) DO UPDATE SET
                telegram_user_id = excluded.telegram_user_id,
                full_name = excluded.full_name,
                is_owner = 1,
                is_active = 1
            """,
            (MAIN_REP_STUDENT_NUMBER, int(MAIN_REP_TELEGRAM_ID), full_name, utc_now_iso()),
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
            "CREATE TABLE IF NOT EXISTS students (student_number TEXT PRIMARY KEY, full_name TEXT NOT NULL)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS student_grades (
                student_number TEXT PRIMARY KEY,
                grades_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
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
    ensure_default_representative()
    return {"status": "seeded", "reason": "ok", "count": inserted}


def find_student(student_number: str):
    with get_connection() as conn:
        return conn.execute(
            "SELECT student_number, full_name FROM students WHERE student_number = ?",
            (student_number,),
        ).fetchone()


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
            [(student_id, row_data["full_name"]) for student_id, row_data in records.items()],
        )
        conn.executemany(
            """
            INSERT INTO student_grades (student_number, grades_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(student_number) DO UPDATE SET
                grades_json = excluded.grades_json,
                updated_at = excluded.updated_at
            """,
            [(student_id, row_data["grades_json"], now_iso) for student_id, row_data in records.items()],
        )
    return len(records)


def list_students_with_grades():
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT s.student_number, s.full_name, g.grades_json, g.updated_at
            FROM students s
            JOIN student_grades g ON g.student_number = s.student_number
            """
        ).fetchall()


def get_student_grades(student_number: str):
    with get_connection() as conn:
        return conn.execute(
            "SELECT student_number, grades_json, updated_at FROM student_grades WHERE student_number = ?",
            (student_number,),
        ).fetchone()


def bulk_upsert_course_grades(course_title: str, grade_entries: Iterable[Tuple[str, str]]) -> Dict[str, List[str] | int]:
    now_iso = utc_now_iso()
    result: Dict[str, List[str] | int] = {"updated_count": 0, "missing_students": []}
    with get_connection() as conn:
        for student_number, grade_value in grade_entries:
            student = conn.execute("SELECT student_number FROM students WHERE student_number = ?", (student_number,)).fetchone()
            if not student:
                result["missing_students"].append(student_number)
                continue

            grade_row = conn.execute("SELECT grades_json FROM student_grades WHERE student_number = ?", (student_number,)).fetchone()
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
            result["updated_count"] = int(result["updated_count"]) + 1
    return result


def list_representatives():
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT student_number, telegram_user_id, full_name, is_owner, is_active, created_at
            FROM representatives
            WHERE is_active = 1
            ORDER BY is_owner DESC, created_at ASC
            """
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
            SET status = 'replaced', reviewed_at = ?, reviewer_note = 'new_request_created'
            WHERE telegram_user_id = ? AND status = ?
            """,
            (now_iso, telegram_user_id, PENDING_STATUS),
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
        return conn.execute("SELECT * FROM verification_requests WHERE id = ?", (request_id,)).fetchone()


def get_pending_request_by_user_id(telegram_user_id: int):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT * FROM verification_requests
            WHERE telegram_user_id = ? AND status = ?
            ORDER BY id DESC LIMIT 1
            """,
            (telegram_user_id, PENDING_STATUS),
        ).fetchone()


def list_pending_verification_requests(limit: int = 30, offset: int = 0):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT * FROM verification_requests
            WHERE status = ?
            ORDER BY requested_at ASC
            LIMIT ? OFFSET ?
            """,
            (PENDING_STATUS, limit, offset),
        ).fetchall()


def attach_rep_message_refs(request_id: int, refs: list[dict]) -> None:
    with get_connection() as conn:
        row = conn.execute("SELECT rep_message_refs_json FROM verification_requests WHERE id = ?", (request_id,)).fetchone()
        existing = []
        if row and row["rep_message_refs_json"]:
            try:
                existing = json.loads(row["rep_message_refs_json"])
            except json.JSONDecodeError:
                existing = []
        existing.extend(refs)
        conn.execute(
            "UPDATE verification_requests SET rep_message_refs_json = ? WHERE id = ?",
            (json.dumps(existing, ensure_ascii=False), request_id),
        )


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


def get_registered_student_by_student_number(student_number: str):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT telegram_user_id, student_number, full_name, username, profile_text, approved_at, approved_by_tg_id
            FROM telegram_students
            WHERE student_number = ? AND is_active = 1
            """,
            (student_number,),
        ).fetchone()


def count_registered_students(query: str | None = None) -> int:
    sql = "SELECT COUNT(*) AS cnt FROM telegram_students WHERE is_active = 1"
    params: list = []
    if query:
        sql += " AND (student_number LIKE ? OR full_name LIKE ? OR COALESCE(username, '') LIKE ? OR CAST(telegram_user_id AS TEXT) LIKE ?)"
        like = f"%{query}%"
        params.extend([like, like, like, like])
    with get_connection() as conn:
        row = conn.execute(sql, tuple(params)).fetchone()
    return int(row["cnt"]) if row else 0


def list_registered_students(
    limit: int = 20,
    offset: int = 0,
    query: str | None = None,
    sort_by: str = "approved_at_desc",
):
    sort_map = {
        "approved_at_desc": "approved_at DESC",
        "approved_at_asc": "approved_at ASC",
        "student_number": "student_number ASC",
        "name": "full_name ASC",
    }
    sql = """
        SELECT telegram_user_id, student_number, full_name, username, profile_text, approved_at, approved_by_tg_id
        FROM telegram_students
        WHERE is_active = 1
    """
    params: list = []
    if query:
        sql += " AND (student_number LIKE ? OR full_name LIKE ? OR COALESCE(username, '') LIKE ? OR CAST(telegram_user_id AS TEXT) LIKE ?)"
        like = f"%{query}%"
        params.extend([like, like, like, like])
    sql += f" ORDER BY {sort_map.get(sort_by, 'approved_at DESC')} LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with get_connection() as conn:
        return conn.execute(sql, tuple(params)).fetchall()


def list_recent_registrations(limit: int = 10):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT telegram_user_id, student_number, full_name, username, approved_at
            FROM telegram_students
            WHERE is_active = 1
            ORDER BY approved_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def list_recent_channel_ids(limit: int = 6) -> list[int]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            WITH channels AS (
                SELECT channel_id AS channel_id, MAX(created_at) AS last_used
                FROM form_schedules
                WHERE channel_id IS NOT NULL
                GROUP BY channel_id
                UNION ALL
                SELECT announcement_channel_id AS channel_id, MAX(created_at) AS last_used
                FROM forms
                WHERE announcement_channel_id IS NOT NULL AND announcement_channel_id != ''
                GROUP BY announcement_channel_id
            )
            SELECT channel_id
            FROM channels
            GROUP BY channel_id
            ORDER BY MAX(last_used) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [int(row["channel_id"]) for row in rows]


def decide_verification_request(request_id: int, reviewer_tg_id: int, approve: bool, reviewer_note: str | None = None):
    now_iso = utc_now_iso()
    decision_status = APPROVED_STATUS if approve else REJECTED_STATUS
    with get_connection() as conn:
        request_row = conn.execute("SELECT * FROM verification_requests WHERE id = ?", (request_id,)).fetchone()
        if not request_row:
            return None, "not_found"
        if request_row["status"] != PENDING_STATUS:
            return request_row, "already_reviewed"

        if approve:
            active = conn.execute(
                "SELECT telegram_user_id FROM telegram_students WHERE student_number = ? AND is_active = 1",
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
                updated = conn.execute("SELECT * FROM verification_requests WHERE id = ?", (request_id,)).fetchone()
                return updated, "student_number_already_linked"

            conn.execute(
                "UPDATE telegram_students SET is_active = 0 WHERE student_number = ? OR telegram_user_id = ?",
                (request_row["student_number"], request_row["telegram_user_id"]),
            )
            telegram_student_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(telegram_students)").fetchall()
            }
            if "registered_at" in telegram_student_columns:
                conn.execute(
                    """
                    INSERT INTO telegram_students (
                        telegram_user_id, student_number, full_name, username, profile_text,
                        registered_at, approved_at, approved_by_tg_id, is_active
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        request_row["telegram_user_id"],
                        request_row["student_number"],
                        request_row["full_name"],
                        request_row["username"],
                        request_row["profile_text"],
                        now_iso,
                        now_iso,
                        reviewer_tg_id,
                    ),
                )
            else:
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
        updated = conn.execute("SELECT * FROM verification_requests WHERE id = ?", (request_id,)).fetchone()
    return updated, decision_status


def deactivate_student(student_number: str) -> int:
    with get_connection() as conn:
        result = conn.execute(
            "UPDATE telegram_students SET is_active = 0 WHERE student_number = ? AND is_active = 1",
            (student_number,),
        )
    return int(result.rowcount)


def _generate_share_token() -> str:
    return secrets.token_urlsafe(8).replace("-", "").replace("_", "")


def create_form(
    title: str,
    description: str,
    deadline_at: str | None,
    capacity: int | None,
    waitlist_enabled: bool,
    created_by_tg_id: int,
    created_by_student_number: str,
    questions: Sequence[dict],
    status: str = FORM_STATUS_OPEN,
    source_form_id: int | None = None,
) -> int:
    now_iso = utc_now_iso()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO forms (
                title, description, share_token, status, deadline_at, capacity, waitlist_enabled,
                created_by_tg_id, created_by_student_number, created_at, source_form_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                description,
                _generate_share_token(),
                status,
                deadline_at,
                capacity,
                1 if waitlist_enabled else 0,
                created_by_tg_id,
                created_by_student_number,
                now_iso,
                source_form_id,
            ),
        )
        form_id = int(cursor.lastrowid)
        _replace_form_questions(conn, form_id, questions)
    return form_id


def _replace_form_questions(conn: sqlite3.Connection, form_id: int, questions: Sequence[dict]) -> None:
    conn.execute("DELETE FROM form_questions WHERE form_id = ?", (form_id,))
    for position, question in enumerate(questions, start=1):
        conn.execute(
            """
            INSERT INTO form_questions (form_id, position, field_type, label, is_required, options_json, settings_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                form_id,
                position,
                question["field_type"],
                question["label"],
                1 if question.get("is_required", True) else 0,
                json.dumps(question.get("options", []), ensure_ascii=False),
                json.dumps(question.get("settings", {}), ensure_ascii=False),
            ),
        )


def get_form_by_id(form_id: int):
    with get_connection() as conn:
        return conn.execute("SELECT * FROM forms WHERE id = ?", (form_id,)).fetchone()


def get_form_by_share_token(share_token: str):
    with get_connection() as conn:
        return conn.execute("SELECT * FROM forms WHERE share_token = ?", (share_token,)).fetchone()


def list_forms_by_creator(created_by_tg_id: int, status: str | None = None):
    query = "SELECT * FROM forms WHERE created_by_tg_id = ?"
    params: list = [created_by_tg_id]
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY id DESC"
    with get_connection() as conn:
        return conn.execute(query, tuple(params)).fetchall()


def list_open_forms(limit: int = 50):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM forms WHERE status = ? ORDER BY created_at DESC LIMIT ?",
            (FORM_STATUS_OPEN, limit),
        ).fetchall()


def list_form_questions(form_id: int):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM form_questions WHERE form_id = ? ORDER BY position ASC",
            (form_id,),
        ).fetchall()


def update_form_announcement_channel(form_id: int, channel_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE forms SET announcement_channel_id = ? WHERE id = ?", (channel_id, form_id))


def close_form(form_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE forms SET status = ?, closed_at = ? WHERE id = ?",
            (FORM_STATUS_CLOSED, utc_now_iso(), form_id),
        )


def reopen_form(form_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE forms SET status = ?, closed_at = NULL WHERE id = ?", (FORM_STATUS_OPEN, form_id))


def duplicate_form(form_id: int, created_by_tg_id: int, created_by_student_number: str) -> int:
    form = get_form_by_id(form_id)
    if not form:
        raise ValueError("form_not_found")
    questions = []
    for question in list_form_questions(form_id):
        questions.append(
            {
                "field_type": question["field_type"],
                "label": question["label"],
                "is_required": bool(question["is_required"]),
                "options": json.loads(question["options_json"] or "[]"),
                "settings": json.loads(question["settings_json"] or "{}"),
            }
        )
    return create_form(
        title=f"{form['title']} (کپی)",
        description=form["description"],
        deadline_at=form["deadline_at"],
        capacity=form["capacity"],
        waitlist_enabled=bool(form["waitlist_enabled"]),
        created_by_tg_id=created_by_tg_id,
        created_by_student_number=created_by_student_number,
        questions=questions,
        status=FORM_STATUS_DRAFT,
        source_form_id=form_id,
    )


def get_form_submission(form_id: int, telegram_user_id: int):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM form_submissions WHERE form_id = ? AND telegram_user_id = ?",
            (form_id, telegram_user_id),
        ).fetchone()


def get_form_submission_by_student_number(form_id: int, student_number: str):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM form_submissions WHERE form_id = ? AND student_number = ?",
            (form_id, student_number),
        ).fetchone()


def count_active_form_submissions(form_id: int) -> int:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS cnt FROM form_submissions
            WHERE form_id = ? AND status IN (?, ?)
            """,
            (form_id, SUBMISSION_STATUS_SUBMITTED, SUBMISSION_STATUS_WAITLIST),
        ).fetchone()
    return int(row["cnt"]) if row else 0


def get_next_registration_order(form_id: int) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(registration_order), 0) AS max_order FROM form_submissions WHERE form_id = ?",
            (form_id,),
        ).fetchone()
    return int(row["max_order"]) + 1


def submit_form(
    form_id: int,
    telegram_user_id: int,
    student_number: str,
    full_name: str,
    username: str | None,
    answers: Sequence[dict],
) -> tuple[str, int]:
    form = get_form_by_id(form_id)
    if not form:
        return "not_found", 0
    if form["status"] != FORM_STATUS_OPEN:
        return "closed", 0
    if get_form_submission(form_id, telegram_user_id):
        return "duplicate", 0

    order = get_next_registration_order(form_id)
    status = SUBMISSION_STATUS_SUBMITTED
    current_count = count_active_form_submissions(form_id)
    if form["capacity"] and current_count >= int(form["capacity"]):
        if not form["waitlist_enabled"]:
            return "capacity_full", 0
        status = SUBMISSION_STATUS_WAITLIST

    now_iso = utc_now_iso()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO form_submissions (
                form_id, telegram_user_id, student_number, full_name, username,
                status, submitted_at, registration_order, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                form_id,
                telegram_user_id,
                student_number,
                full_name,
                username,
                status,
                now_iso,
                order,
                now_iso,
            ),
        )
        submission_id = int(cursor.lastrowid)
        for answer in answers:
            conn.execute(
                """
                INSERT INTO submission_answers (submission_id, question_id, answer_text, answer_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    submission_id,
                    answer["question_id"],
                    answer.get("answer_text"),
                    json.dumps(answer.get("answer_json", []), ensure_ascii=False),
                ),
            )
    return status, order


def list_form_submissions(
    form_id: int,
    query: str | None = None,
    status: str | None = None,
    sort_by: str = "submitted_at_asc",
):
    sort_map = {
        "submitted_at_asc": "registration_order ASC",
        "submitted_at_desc": "registration_order DESC",
        "student_number": "student_number ASC",
        "name": "full_name ASC",
    }
    sql = "SELECT * FROM form_submissions WHERE form_id = ?"
    params: list = [form_id]
    if status:
        sql += " AND status = ?"
        params.append(status)
    if query:
        sql += """
            AND (
                student_number LIKE ?
                OR full_name LIKE ?
                OR COALESCE(username, '') LIKE ?
                OR CAST(telegram_user_id AS TEXT) LIKE ?
                OR EXISTS (
                    SELECT 1
                    FROM submission_answers a
                    WHERE a.submission_id = form_submissions.id
                      AND (
                          COALESCE(a.answer_text, '') LIKE ?
                          OR COALESCE(a.answer_json, '') LIKE ?
                      )
                )
            )
        """
        like = f"%{query}%"
        params.extend([like, like, like, like, like, like])
    sql += f" ORDER BY {sort_map.get(sort_by, 'registration_order ASC')}"
    with get_connection() as conn:
        return conn.execute(sql, tuple(params)).fetchall()


def get_submission_answers(submission_id: int):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT a.submission_id, a.question_id, a.answer_text, a.answer_json,
                   q.label, q.field_type, q.position
            FROM submission_answers a
            JOIN form_questions q ON q.id = a.question_id
            WHERE a.submission_id = ?
            ORDER BY q.position ASC
            """,
            (submission_id,),
        ).fetchall()
    return rows


def get_form_statistics(form_id: int) -> dict:
    with get_connection() as conn:
        stats = conn.execute(
            """
            SELECT
                SUM(CASE WHEN status = 'submitted' THEN 1 ELSE 0 END) AS submitted_count,
                SUM(CASE WHEN status = 'waitlist' THEN 1 ELSE 0 END) AS waitlist_count,
                SUM(CASE WHEN status = 'removed' THEN 1 ELSE 0 END) AS removed_count,
                COUNT(*) AS total_count
            FROM form_submissions
            WHERE form_id = ?
            """,
            (form_id,),
        ).fetchone()
    return {
        "submitted_count": int(stats["submitted_count"] or 0),
        "waitlist_count": int(stats["waitlist_count"] or 0),
        "removed_count": int(stats["removed_count"] or 0),
        "total_count": int(stats["total_count"] or 0),
    }


def remove_submission(form_id: int, student_number: str) -> int:
    now_iso = utc_now_iso()
    with get_connection() as conn:
        result = conn.execute(
            """
            UPDATE form_submissions
            SET status = ?, updated_at = ?
            WHERE form_id = ? AND student_number = ? AND status != ?
            """,
            (SUBMISSION_STATUS_REMOVED, now_iso, form_id, student_number, SUBMISSION_STATUS_REMOVED),
        )
    return int(result.rowcount)


def manual_add_submission(
    form_id: int,
    student_number: str,
    full_name: str,
    username: str | None = None,
    telegram_user_id: int = 0,
) -> tuple[str, int]:
    if get_form_submission_by_student_number(form_id, student_number):
        return "duplicate", 0
    order = get_next_registration_order(form_id)
    form = get_form_by_id(form_id)
    status = SUBMISSION_STATUS_SUBMITTED
    current_count = count_active_form_submissions(form_id)
    if form and form["capacity"] and current_count >= int(form["capacity"]):
        status = SUBMISSION_STATUS_WAITLIST if form["waitlist_enabled"] else SUBMISSION_STATUS_SUBMITTED
    now_iso = utc_now_iso()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO form_submissions (
                form_id, telegram_user_id, student_number, full_name, username,
                status, submitted_at, registration_order, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (form_id, telegram_user_id, student_number, full_name, username, status, now_iso, order, now_iso),
        )
    return status, order


def list_non_submitters(form_id: int):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT ts.telegram_user_id, ts.student_number, ts.full_name, ts.username
            FROM telegram_students ts
            WHERE ts.is_active = 1
              AND NOT EXISTS (
                  SELECT 1 FROM form_submissions fs
                  WHERE fs.form_id = ? AND fs.student_number = ts.student_number AND fs.status != 'removed'
              )
            ORDER BY ts.full_name ASC
            """,
            (form_id,),
        ).fetchall()


def create_form_schedule(
    template_form_id: int,
    channel_id: int,
    post_at: str,
    registration_deadline_at: str | None,
    recurring_rule: str | None,
    created_by_tg_id: int,
) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO form_schedules (
                template_form_id, channel_id, post_at, registration_deadline_at, recurring_rule,
                is_active, created_by_tg_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (template_form_id, channel_id, post_at, registration_deadline_at, recurring_rule, created_by_tg_id, utc_now_iso()),
        )
    return int(cursor.lastrowid)


def list_form_schedules(created_by_tg_id: int | None = None, active_only: bool = False):
    sql = "SELECT * FROM form_schedules WHERE 1=1"
    params: list = []
    if created_by_tg_id is not None:
        sql += " AND created_by_tg_id = ?"
        params.append(created_by_tg_id)
    if active_only:
        sql += " AND is_active = 1"
    sql += " ORDER BY post_at ASC"
    with get_connection() as conn:
        return conn.execute(sql, tuple(params)).fetchall()


def get_schedule(schedule_id: int):
    with get_connection() as conn:
        return conn.execute("SELECT * FROM form_schedules WHERE id = ?", (schedule_id,)).fetchone()


def deactivate_schedule(schedule_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE form_schedules SET is_active = 0 WHERE id = ?", (schedule_id,))


def mark_schedule_run(schedule_id: int, next_post_at: str | None = None) -> None:
    with get_connection() as conn:
        if next_post_at:
            conn.execute(
                "UPDATE form_schedules SET last_run_at = ?, post_at = ? WHERE id = ?",
                (utc_now_iso(), next_post_at, schedule_id),
            )
        else:
            conn.execute(
                "UPDATE form_schedules SET last_run_at = ?, is_active = 0 WHERE id = ?",
                (utc_now_iso(), schedule_id),
            )
