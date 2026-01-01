from __future__ import annotations

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from app.core.callbacks import AdminStudentCb


def admin_menu_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text="Students"))
    kb.row(KeyboardButton(text="Back"))
    return kb.as_markup(resize_keyboard=True)


def students_page_kb(students: list[tuple[str, str]], page: int, page_size: int = 12) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    start = page * page_size
    end = start + page_size

    for sid, label in students[start:end]:
        kb.row(KeyboardButton(text=label))

    nav_row = []
    if page > 0:
        nav_row.append(KeyboardButton(text="Prev"))
    if end < len(students):
        nav_row.append(KeyboardButton(text="Next"))
    if nav_row:
        kb.row(*nav_row)

    kb.row(KeyboardButton(text="Back"))
    return kb.as_markup(resize_keyboard=True)


def student_actions_kb(student_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="View Grades", callback_data=AdminStudentCb(student_id=student_id, action="grades").pack())
    kb.button(text="Unlink", callback_data=AdminStudentCb(student_id=student_id, action="unlink").pack())
    kb.button(text="Edit Name", callback_data=AdminStudentCb(student_id=student_id, action="edit_name").pack())
    kb.button(text="Back", callback_data=AdminStudentCb(student_id=student_id, action="back").pack())
    kb.adjust(2)
    return kb.as_markup()
