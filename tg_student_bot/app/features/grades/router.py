from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.callbacks import GradeCb
from app.core.guards import IsRegistered
from app.db.repo import LinkRepo
from app.utils.csv_loader import list_courses, get_grade

router = Router(name="grades")


def courses_kb(courses: list[str]):
    kb = InlineKeyboardBuilder()
    for c in courses:
        kb.button(text=c, callback_data=GradeCb(course=c).pack())
    kb.adjust(2)
    return kb.as_markup()


@router.message(Command("grades"), IsRegistered())
async def cmd_grades(message: Message) -> None:
    courses = list_courses()
    if not courses:
        await message.answer("فعلاً هیچ فایل نمره‌ای موجود نیست.")
        return
    await message.answer("درس را انتخاب کنید:", reply_markup=courses_kb(courses))


@router.callback_query(GradeCb.filter(), IsRegistered())
async def on_course(call: CallbackQuery, callback_data: GradeCb, link_repo: LinkRepo) -> None:
    link = await link_repo.get_link_by_telegram(call.from_user.id)
    grade = get_grade(callback_data.course, link.student_id)

    if grade is None:
        await call.message.answer(f"برای درس {callback_data.course} نمره‌ای برای شما پیدا نشد.")
    else:
        await call.message.answer(f"نمرهٔ شما در {callback_data.course}: {grade}")

    await call.answer()
