from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.core.guards import IsOwner
from app.db.repo import StudentRepo, LinkRepo
from app.features.admin.keyboards import admin_menu_kb, students_page_kb, student_actions_kb
from app.features.admin.states import AdminStates
from app.utils.csv_loader import list_courses, get_grade
from app.core.callbacks import AdminStudentCb

router = Router(name="admin")


def _student_label(student_id: str, first_name: str, last_name: str) -> str:
    return f"{student_id} - {first_name} {last_name}"


@router.message(Command("admin"), IsOwner())
async def cmd_admin(message: Message) -> None:
    await message.answer("Admin Panel", reply_markup=admin_menu_kb())


@router.message(F.text == "Back", IsOwner())
async def admin_back(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Admin Panel", reply_markup=admin_menu_kb())


@router.message(F.text == "Students", IsOwner())
async def admin_students(message: Message, state: FSMContext, student_repo: StudentRepo) -> None:
    students = await student_repo.list_students()
    packed = [(s.student_id, _student_label(s.student_id, s.first_name, s.last_name)) for s in students]
    await state.update_data(students=packed, page=0)
    await state.set_state(AdminStates.browsing_students)
    await message.answer("Students List:", reply_markup=students_page_kb(packed, page=0))


@router.message(AdminStates.browsing_students, IsOwner())
async def on_students_list_message(message: Message, state: FSMContext, student_repo: StudentRepo) -> None:
    text = (message.text or "").strip()
    data = await state.get_data()
    packed = data.get("students") or []
    page = int(data.get("page") or 0)

    if text == "Next":
        page += 1
        await state.update_data(page=page)
        await message.answer("Students List:", reply_markup=students_page_kb(packed, page=page))
        return
    if text == "Prev":
        page = max(0, page - 1)
        await state.update_data(page=page)
        await message.answer("Students List:", reply_markup=students_page_kb(packed, page=page))
        return
    if text == "Back":
        await state.clear()
        await message.answer("Admin Panel", reply_markup=admin_menu_kb())
        return

    sid = text.split("-", 1)[0].strip() if "-" in text else None
    if not sid:
        await message.answer("Unknown Command.", reply_markup=students_page_kb(packed, page=page))
        return

    student = await student_repo.get_student(sid)
    if not student:
        await message.answer("Student Not Found.", reply_markup=students_page_kb(packed, page=page))
        return

    await state.update_data(selected_student_id=sid)
    await message.answer(
        f"Student:\n{student.student_id}\n{student.first_name} {student.last_name}",
        reply_markup=student_actions_kb(sid),
    )


@router.callback_query(AdminStudentCb.filter(), IsOwner())
async def on_student_action(call: CallbackQuery, callback_data: AdminStudentCb, state: FSMContext, student_repo: StudentRepo, link_repo: LinkRepo) -> None:
    sid = callback_data.student_id
    action = callback_data.action

    if action == "back":
        await call.message.edit_text("از لیست Students یک دانشجو را انتخاب کنید.")
        await call.answer()
        return

    if action == "unlink":
        await link_repo.unlink_student(sid)
        await call.message.edit_text("✅ ارتباط حذف شد. Student Id آزاد شد.", reply_markup=student_actions_kb(sid))
        await call.answer()
        return

    if action == "edit_name":
        await state.update_data(edit_student_id=sid)
        await state.set_state(AdminStates.editing_name_first)
        await call.message.answer("First Name را بفرست:")
        await call.answer()
        return

    if action == "grades":
        courses = list_courses()
        if not courses:
            await call.message.answer("هیچ فایل نمره‌ای موجود نیست.")
            await call.answer()
            return

        lines = []
        for c in courses:
            g = get_grade(c, sid)
            if g is not None:
                lines.append(f"{c}: {g}")

        await call.message.answer("Grades:\n" + ("\n".join(lines) if lines else "No Grade Found"))
        await call.answer()
        return


@router.message(AdminStates.editing_name_first, IsOwner())
async def admin_edit_first(message: Message, state: FSMContext) -> None:
    fn = (message.text or "").strip()
    if len(fn) < 2:
        await message.answer("First Name کوتاه است. دوباره بفرست:")
        return
    await state.update_data(new_first=fn)
    await state.set_state(AdminStates.editing_name_last)
    await message.answer("Last Name را بفرست:")


@router.message(AdminStates.editing_name_last, IsOwner())
async def admin_edit_last(message: Message, state: FSMContext, student_repo: StudentRepo) -> None:
    ln = (message.text or "").strip()
    if len(ln) < 2:
        await message.answer("Last Name کوتاه است. دوباره بفرست:")
        return

    data = await state.get_data()
    sid = data.get("edit_student_id")
    fn = data.get("new_first")

    if not sid or not fn:
        await message.answer("خطا. از اول وارد Admin شوید.")
        await state.clear()
        return

    await student_repo.update_name(sid, fn, ln)
    await state.set_state(AdminStates.browsing_students)
    await message.answer(f"✅ Updated: {sid} - {fn} {ln}")
