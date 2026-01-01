from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.core.callbacks import RegCb
from app.features.registration.states import RegistrationStates
from app.features.registration.keyboards import confirm_kb
from app.db.repo import StudentRepo, LinkRepo, AttemptRepo
from app.utils.csv_loader import iter_registry_rows

router = Router(name="registration")

WELCOME = (
    "سلام 👋\n"
    "برای استفاده از ربات، ابتدا باید ثبت‌نام کنید.\n"
    "لطفاً شمارهٔ دانشجویی را ارسال کنید."
)

LOCKED = "اکانت شما به دلیل ۳ تلاش ناموفق قفل شده است. با پشتیبانی تماس بگیرید."


async def ensure_registry_loaded(student_repo: StudentRepo) -> None:
    for row in iter_registry_rows():
        sid = row.get("student_id", "").strip()
        fn = row.get("first_name", "").strip()
        ln = row.get("last_name", "").strip()
        if sid and fn and ln:
            await student_repo.upsert_student(sid, fn, ln)


@router.message(Command("start"))
async def start(message: Message, state: FSMContext, student_repo: StudentRepo, link_repo: LinkRepo, attempt_repo: AttemptRepo) -> None:
    await ensure_registry_loaded(student_repo)

    user_id = message.from_user.id
    link = await link_repo.get_link_by_telegram(user_id)
    if link:
        await message.answer("شما قبلاً ثبت‌نام کرده‌اید.\nبرای دیدن نمرات دستور /grades را بزنید.")
        return

    attempt = await attempt_repo.get_or_create(user_id)
    if attempt.locked:
        await message.answer(LOCKED)
        return

    await state.set_state(RegistrationStates.waiting_student_id)
    remaining = 3 - attempt.failures
    await message.answer(f"{WELCOME}\n\nتلاش باقی‌مانده: {remaining}")


@router.message(RegistrationStates.waiting_student_id)
async def on_student_id(message: Message, state: FSMContext, student_repo: StudentRepo, link_repo: LinkRepo, attempt_repo: AttemptRepo) -> None:
    user_id = message.from_user.id
    attempt = await attempt_repo.get_or_create(user_id)
    if attempt.locked:
        await message.answer(LOCKED)
        return

    sid = (message.text or "").strip()

    # Basic validation
    if not sid.isdigit() or len(sid) < 5:
        attempt = await attempt_repo.increment_failure(user_id)
        if attempt.locked:
            await message.answer("شمارهٔ دانشجویی نامعتبر بود و اکانت شما قفل شد.")
        else:
            await message.answer(f"شمارهٔ دانشجویی نامعتبر است.\nتلاش باقی‌مانده: {3 - attempt.failures}")
        return

    student = await student_repo.get_student(sid)
    if not student:
        attempt = await attempt_repo.increment_failure(user_id)
        if attempt.locked:
            await message.answer("این شمارهٔ دانشجویی در لیست نیست و اکانت شما قفل شد.")
        else:
            await message.answer(f"این شمارهٔ دانشجویی در لیست نیست.\nتلاش باقی‌مانده: {3 - attempt.failures}")
        return

    existing = await link_repo.get_link_by_student(sid)
    if existing:
        attempt = await attempt_repo.increment_failure(user_id)
        if attempt.locked:
            await message.answer("این شمارهٔ دانشجویی قبلاً ثبت شده است و اکانت شما قفل شد.")
        else:
            await message.answer(f"این شمارهٔ دانشجویی قبلاً ثبت شده است.\nتلاش باقی‌مانده: {3 - attempt.failures}")
        return

    await state.update_data(student_id=sid)
    await state.set_state(RegistrationStates.waiting_confirm)

    await message.answer(
        "اطلاعات شما پیدا شد:\n"
        f"شمارهٔ دانشجویی: {student.student_id}\n"
        f"نام: {student.first_name}\n"
        f"نام خانوادگی: {student.last_name}\n\n"
        "آیا تأیید می‌کنید؟",
        reply_markup=confirm_kb(),
    )


@router.callback_query(RegCb.filter(F.action == "confirm_yes"), RegistrationStates.waiting_confirm)
async def confirm_yes(call: CallbackQuery, state: FSMContext, link_repo: LinkRepo, attempt_repo: AttemptRepo) -> None:
    data = await state.get_data()
    sid = data.get("student_id")
    if not sid:
        await call.message.edit_text("خطا. لطفاً دوباره /start را بزنید.")
        await state.clear()
        await call.answer()
        return

    await link_repo.create_link(call.from_user.id, sid)
    await attempt_repo.reset(call.from_user.id)
    await state.clear()

    await call.message.edit_text("✅ ثبت‌نام با موفقیت انجام شد.\nبرای دیدن نمرات: /grades")
    await call.answer()


@router.callback_query(RegCb.filter(F.action == "confirm_no"), RegistrationStates.waiting_confirm)
async def confirm_no(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(RegistrationStates.waiting_student_id)
    await call.message.edit_text("باشه.\nلطفاً شمارهٔ دانشجویی را دوباره وارد کنید:")
    await call.answer()
