from __future__ import annotations

import csv
import json
from io import BytesIO, StringIO

from openpyxl import Workbook

from bot.services.datetime_fa import format_datetime_fa, unix_timestamp
from bot.services.formatting import code, e, status_badge
from db import get_submission_answers, list_form_submissions


def build_text_name_list(form_id: int) -> str:
    rows = list_form_submissions(form_id, sort_by="submitted_at_asc")
    if not rows:
        return "هنوز هیچ پاسخی ثبت نشده است."
    lines = ["📋 <b>فهرست ثبت‌نام‌ها بر اساس اولویت</b>", ""]
    for index, row in enumerate(rows, start=1):
        answers = get_submission_answers(row["id"])
        answer_lines = []
        for answer in answers:
            answer_text = answer["answer_text"] or ", ".join(json.loads(answer["answer_json"] or "[]")) or "بدون پاسخ"
            answer_lines.append(f"• <b>{e(answer['label'])}:</b> {e(answer_text)}")
        lines.append(
            f"{index}. <b>{e(row['full_name'])}</b>\n"
            f"🕒 زمان ثبت: {code(format_datetime_fa(row['submitted_at']))}\n"
            f"{chr(10).join(answer_lines) if answer_lines else '• پاسخ ثبت نشده'}"
        )
    return "\n".join(lines)


def build_text_name_student_list(form_id: int) -> str:
    rows = list_form_submissions(form_id, sort_by="submitted_at_asc")
    if not rows:
        return "هنوز هیچ پاسخی ثبت نشده است."
    lines = ["📋 <b>فهرست نام و شماره دانشجویی</b>", ""]
    for index, row in enumerate(rows, start=1):
        answers = get_submission_answers(row["id"])
        answer_lines = []
        for answer in answers:
            answer_text = answer["answer_text"] or ", ".join(json.loads(answer["answer_json"] or "[]")) or "بدون پاسخ"
            answer_lines.append(f"• <b>{e(answer['label'])}:</b> {e(answer_text)}")
        lines.append(
            f"{index}. <b>{e(row['full_name'])}</b> — 🎓 {code(row['student_number'])}\n"
            f"🕒 زمان ثبت: {code(format_datetime_fa(row['submitted_at']))}\n"
            f"{chr(10).join(answer_lines) if answer_lines else '• پاسخ ثبت نشده'}"
        )
    return "\n".join(lines)


def _build_export_rows(form_id: int) -> list[dict]:
    submissions = list_form_submissions(form_id, sort_by="submitted_at_asc")
    export_rows: list[dict] = []
    for submission in submissions:
        row = {
            "full_name": submission["full_name"],
            "student_number": submission["student_number"],
            "telegram_user_id": submission["telegram_user_id"],
            "username": submission["username"] or "",
            "status": submission["status"],
            "status_fa": status_badge(submission["status"]),
            "submitted_at_fa": format_datetime_fa(submission["submitted_at"]),
            "submitted_at_unix": unix_timestamp(submission["submitted_at"]) or "",
            "registration_order": submission["registration_order"],
        }
        for answer in get_submission_answers(submission["id"]):
            row[answer["label"]] = answer["answer_text"] or ", ".join(json.loads(answer["answer_json"] or "[]"))
        export_rows.append(row)
    return export_rows


def build_csv_bytes(form_id: int) -> bytes:
    rows = _build_export_rows(form_id)
    output = StringIO()
    if rows:
        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    else:
        output.write("full_name,student_number\n")
    return output.getvalue().encode("utf-8-sig")


def build_json_bytes(form_id: int) -> bytes:
    rows = _build_export_rows(form_id)
    return json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")


def build_xlsx_bytes(form_id: int) -> bytes:
    rows = _build_export_rows(form_id)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "results"
    if rows:
        headers = list(rows[0].keys())
        sheet.append(headers)
        for row in rows:
            sheet.append([row.get(header, "") for header in headers])
    else:
        sheet.append(["full_name", "student_number"])

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
