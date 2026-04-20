from __future__ import annotations

import json
from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app_callbacks import (
    MENU_ADMIN_PANEL,
    MENU_ADMIN_REMOVE,
    MENU_CANCEL,
    MENU_GRADES,
    MENU_HOME,
    MENU_PROFILE,
    MENU_REGISTER,
    MENU_REP_BROADCAST,
    MENU_REP_FORMS,
    MENU_REP_FORM_CREATE,
    MENU_REP_FORM_LIST,
    MENU_REP_IMPORT_GRADES,
    MENU_REP_PANEL,
    MENU_REP_PENDING,
    MENU_REP_SCHEDULES,
    PREFIX_ADD_ANOTHER_QUESTION,
    PREFIX_CHECKBOX_DONE,
    PREFIX_CHECKBOX_TOGGLE,
    PREFIX_CHOICE_PICK,
    PREFIX_FORM_CLOSE,
    PREFIX_FORM_DUPLICATE,
    PREFIX_FORM_EXPORT,
    PREFIX_FORM_JOIN,
    PREFIX_FORM_MANUAL_ADD,
    PREFIX_FORM_REMOVE_SUBMISSION,
    PREFIX_FORM_REMIND,
    PREFIX_FORM_REOPEN,
    PREFIX_FORM_SEARCH,
    PREFIX_FORM_VIEW,
    PREFIX_PAGE,
    PREFIX_QUESTION_TYPE,
    PREFIX_REQUIRED,
    PREFIX_SCHEDULE_CANCEL,
    PREFIX_SCHEDULE_FORM,
    PREFIX_VERIFY_APPROVE,
    PREFIX_VERIFY_REJECT,
)
from assistant_profile import PROFILE
from bot.services.datetime_fa import TEHRAN_TZ, format_datetime_fa, parse_db_datetime, utc_now
from bot.services.exporters import (
    build_csv_bytes,
    build_json_bytes,
    build_text_name_list,
    build_text_name_student_list,
    build_xlsx_bytes,
)
from bot.services.formatting import code, e
from bot.services.parsers import parse_grade_list_text
from bot.services.policies import (
    is_admin,
    is_rep_candidate,
    is_verified_representative,
    is_verified_user,
    normalize_student_number,
    verification_reviewer_ids,
)
from bot.states import (
    AdminStates,
    AuthStates,
    BroadcastStates,
    FormAdminStates,
    FormCreateStates,
    FormSubmitStates,
    GradeImportStates,
    ScheduleStates,
)
from bot.ui.keyboards import (
    add_another_question_markup,
    admin_panel_markup,
    cancel_markup,
    checkbox_markup,
    form_detail_markup,
    form_join_markup,
    form_list_markup,
    forms_menu_markup,
    home_markup,
    question_type_markup,
    rep_panel_markup,
    required_markup,
    schedule_recurring_markup,
    simple_back_home_markup,
    single_choice_markup,
    verification_request_markup,
)
from bot.ui.texts import (
    ask_question_text,
    form_join_text,
    form_summary_text,
    grades_text,
    home_text,
    pending_requests_text,
    profile_text,
    representative_panel_text,
    schedule_list_text,
    submissions_text,
    verification_intro_text,
    verification_request_message,
)
from db import (
    FORM_STATUS_CLOSED,
    FORM_STATUS_DRAFT,
    FORM_STATUS_OPEN,
    attach_rep_message_refs,
    bulk_upsert_course_grades,
    close_form,
    count_active_form_submissions,
    create_form,
    create_form_schedule,
    create_verification_request,
    decide_verification_request,
    deactivate_schedule,
    deactivate_student,
    duplicate_form,
    find_student,
    get_active_registration_by_student_number,
    get_active_registration_by_tg_id,
    get_form_by_id,
    get_form_by_share_token,
    get_form_statistics,
    get_form_submission,
    get_pending_request_by_user_id,
    get_schedule,
    get_student_grades,
    get_submission_answers,
    get_verification_request,
    list_active_registered_users,
    list_form_questions,
    list_form_schedules,
    list_form_submissions,
    list_forms_by_creator,
    list_non_submitters,
    list_open_forms,
    list_pending_verification_requests,
    list_recent_registrations,
    list_students_with_grades,
    manual_add_submission,
    mark_schedule_run,
    remove_submission,
    reopen_form,
    submit_form,
    update_form_announcement_channel,
)
from grade_analytics import build_class_ranking, build_grade_insights, extract_numeric_items
from bot.services.scheduler import next_recurring_post

router = Router()

FORMS_PAGE_SIZE = 8
PENDING_PAGE_SIZE = 8


def _parse_user_datetime(raw_text: str) -> str | None:
    text = (raw_text or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")).strip()
    if text in {"", "-", "ندارد", "skip", "Skip"}:
        return None
    for fmt in ("%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M"):
        try:
            tehran_dt = datetime.strptime(text, fmt).replace(tzinfo=TEHRAN_TZ)
            return tehran_dt.astimezone(timezone.utc).isoformat(timespec="seconds")
        except ValueError:
            continue
    return None


def _build_form_link(bot_username: str, share_token: str) -> str:
    return f"https://t.me/{bot_username}?start=form_{share_token}"


async def show_home(target: Message | CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user = target.from_user if isinstance(target, CallbackQuery) else target.from_user
    verified = is_verified_user(user.id)
    text = home_text(verified)
    markup = home_markup(user.id, verified)
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=markup)
    else:
        await target.answer(text, reply_markup=markup)


async def ensure_form_owner(callback: CallbackQuery, form_id: int) -> bool:
    form = get_form_by_id(form_id)
    if not form or form["created_by_tg_id"] != callback.from_user.id:
        await callback.answer("این فرم متعلق به شما نیست.", show_alert=True)
        return False
    return True


async def ensure_verified(target: Message | CallbackQuery, state: FSMContext) -> bool:
    user = target.from_user if isinstance(target, CallbackQuery) else target.from_user
    if is_verified_user(user.id):
        return True
    text = "🔐 ابتدا احراز هویت را کامل کن."
    if isinstance(target, CallbackQuery):
        await target.answer()
        await target.message.edit_text(text, reply_markup=home_markup(user.id, False))
    else:
        await target.answer(text, reply_markup=home_markup(user.id, False))
    return False


async def send_verification_cards(bot: Bot, request_id: int, user_id: int) -> None:
    request_row = get_verification_request(request_id)
    if not request_row:
        return
    refs = []
    photo = None
    try:
        photos = await bot.get_user_profile_photos(user_id=user_id, limit=1)
        if photos.photos:
            photo = photos.photos[0][-1].file_id
    except Exception:
        photo = None

    for reviewer_id in verification_reviewer_ids():
        try:
            if photo:
                sent = await bot.send_photo(
                    reviewer_id,
                    photo=photo,
                    caption=verification_request_message(request_row),
                    reply_markup=verification_request_markup(request_id),
                )
            else:
                sent = await bot.send_message(
                    reviewer_id,
                    verification_request_message(request_row),
                    reply_markup=verification_request_markup(request_id),
                )
            refs.append({"chat_id": reviewer_id, "message_id": sent.message_id})
        except Exception:
            continue
    if refs:
        attach_rep_message_refs(request_id, refs)


async def publish_scheduled_form(bot: Bot, scheduler, schedule_id: int) -> None:
    schedule = get_schedule(schedule_id)
    if not schedule or not schedule["is_active"]:
        return
    template = get_form_by_id(schedule["template_form_id"])
    if not template:
        deactivate_schedule(schedule_id)
        return
    created_form_id = duplicate_form(
        template["id"],
        created_by_tg_id=template["created_by_tg_id"],
        created_by_student_number=template["created_by_student_number"],
    )
    if schedule["registration_deadline_at"]:
        with_deadline = schedule["registration_deadline_at"]
    else:
        with_deadline = template["deadline_at"]
    from db import get_connection
    with get_connection() as conn:
        conn.execute(
            "UPDATE forms SET status = ?, deadline_at = ?, announcement_channel_id = ? WHERE id = ?",
            (FORM_STATUS_OPEN, with_deadline, schedule["channel_id"], created_form_id),
        )
    created_form = get_form_by_id(created_form_id)
    me = await bot.get_me()
    link = _build_form_link(me.username, created_form["share_token"])
    await bot.send_message(
        chat_id=schedule["channel_id"],
        text=(
            f"📢 <b>فرم ثبت‌نام {e(created_form['title'])} فعال شد</b>\n\n"
            f"📝 {e(created_form['description'] or 'بدون توضیح')}\n"
            f"⏰ مهلت: {code(format_datetime_fa(created_form['deadline_at']) if created_form['deadline_at'] else 'ندارد')}"
        ),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="📌 ثبت‌نام در فرم", url=link)]]
        ),
    )
    next_post = next_recurring_post(schedule["post_at"], schedule["recurring_rule"])
    mark_schedule_run(schedule_id, next_post)
    if next_post:
        from bot.services.scheduler import schedule_job

        schedule_job(scheduler, schedule_id, next_post, callback=lambda sid: publish_scheduled_form(bot, scheduler, sid))


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext, bot: Bot) -> None:
    payload = (message.text or "").split(maxsplit=1)
    if len(payload) > 1 and payload[1].startswith("form_"):
        token = payload[1][5:]
        form = get_form_by_share_token(token)
        if form:
            questions = list_form_questions(form["id"])
            await message.answer(form_join_text(form, questions), reply_markup=form_join_markup(form["id"]))
            return
    await show_home(message, state)


@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ عملیات لغو شد.", reply_markup=home_markup(message.from_user.id, is_verified_user(message.from_user.id)))


@router.callback_query(F.data == MENU_HOME)
async def menu_home(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await show_home(callback, state)


@router.callback_query(F.data == MENU_CANCEL)
async def menu_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer("لغو شد.")
    await show_home(callback, state)


@router.callback_query(F.data == MENU_REGISTER)
async def menu_register(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if is_verified_user(callback.from_user.id):
        registered = get_active_registration_by_tg_id(callback.from_user.id)
        await callback.message.edit_text(profile_text(registered), reply_markup=simple_back_home_markup())
        return
    pending = get_pending_request_by_user_id(callback.from_user.id)
    if pending:
        await callback.message.edit_text(
            "📨 درخواست شما قبلا ثبت شده و منتظر بررسی است.",
            reply_markup=simple_back_home_markup(),
        )
        return
    await state.set_state(AuthStates.waiting_student_number)
    await callback.message.edit_text(verification_intro_text(), reply_markup=cancel_markup())
    await callback.message.answer("🎓 شماره دانشجویی را بفرست.", reply_markup=cancel_markup())


@router.message(AuthStates.waiting_student_number)
async def auth_student_number(message: Message, state: FSMContext) -> None:
    student_number = normalize_student_number(message.text or "")
    if not student_number:
        await message.answer("⚠️ شماره دانشجویی معتبر نیست.", reply_markup=cancel_markup())
        return
    student = find_student(student_number)
    if not student:
        await message.answer("❌ این شماره دانشجویی در دیتابیس پیدا نشد.", reply_markup=cancel_markup())
        return
    active = get_active_registration_by_student_number(student_number)
    if active and active["telegram_user_id"] != message.from_user.id:
        await message.answer("🔒 این شماره دانشجویی روی حساب دیگری فعال است.", reply_markup=simple_back_home_markup())
        await state.clear()
        return
    await state.update_data(student_number=student["student_number"], full_name=student["full_name"])
    await state.set_state(AuthStates.waiting_profile_text)
    await message.answer(
        f"✅ دانشجو پیدا شد: <b>{e(student['full_name'])}</b>\nحالا یک معرفی کوتاه بفرست.",
        reply_markup=cancel_markup(),
    )


@router.message(AuthStates.waiting_profile_text)
async def auth_profile_text(message: Message, state: FSMContext, bot: Bot) -> None:
    profile_text_value = (message.text or "").strip()
    if not profile_text_value:
        await message.answer("⚠️ معرفی کوتاه خالی است.", reply_markup=cancel_markup())
        return
    data = await state.get_data()
    request_id = create_verification_request(
        telegram_user_id=message.from_user.id,
        student_number=data["student_number"],
        full_name=data["full_name"],
        username=message.from_user.username,
        profile_text=profile_text_value,
    )
    await state.clear()
    await send_verification_cards(bot, request_id, message.from_user.id)
    await message.answer(
        (
            "📨 درخواست احراز هویت ثبت شد.\n"
            f"👤 <b>نام:</b> {e(data['full_name'])}\n"
            f"🎓 <b>شماره دانشجویی:</b> {code(data['student_number'])}"
        ),
        reply_markup=home_markup(message.from_user.id, False),
    )


@router.callback_query(F.data.startswith(PREFIX_VERIFY_APPROVE) | F.data.startswith(PREFIX_VERIFY_REJECT))
async def review_verification(callback: CallbackQuery, bot: Bot) -> None:
    await callback.answer()
    if not (is_verified_representative(callback.from_user.id) or is_admin(callback.from_user.id)):
        await callback.answer("دسترسی بررسی درخواست نداری.", show_alert=True)
        return
    approve = callback.data.startswith(PREFIX_VERIFY_APPROVE)
    request_id = int(callback.data.split(":")[1])
    request_row, result = decide_verification_request(
        request_id=request_id,
        reviewer_tg_id=callback.from_user.id,
        approve=approve,
        reviewer_note=None if approve else "درخواست توسط نماینده رد شد.",
    )
    if not request_row:
        await callback.answer("درخواست پیدا نشد.", show_alert=True)
        return
    await callback.message.edit_reply_markup(reply_markup=None)
    if result in {"already_reviewed", "student_number_already_linked"}:
        await callback.answer("این درخواست قبلا نهایی شده است.", show_alert=True)
        return
    if approve:
        await bot.send_message(
            request_row["telegram_user_id"],
            "✅ احراز هویت شما تایید شد.",
            reply_markup=home_markup(request_row["telegram_user_id"], True),
        )
    else:
        await bot.send_message(
            request_row["telegram_user_id"],
            "❌ درخواست احراز هویت شما رد شد. از منوی اصلی دوباره تلاش کن.",
            reply_markup=home_markup(request_row["telegram_user_id"], False),
        )


@router.callback_query(F.data == MENU_PROFILE)
async def menu_profile(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if not await ensure_verified(callback, state):
        return
    registered = get_active_registration_by_tg_id(callback.from_user.id)
    await callback.message.edit_text(profile_text(registered), reply_markup=simple_back_home_markup())


@router.callback_query(F.data == MENU_GRADES)
async def menu_grades(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if not await ensure_verified(callback, state):
        return
    registered = get_active_registration_by_tg_id(callback.from_user.id)
    grade_row = get_student_grades(registered["student_number"])
    if not grade_row:
        await callback.message.edit_text("ℹ️ هنوز نمره‌ای ثبت نشده است.", reply_markup=simple_back_home_markup())
        return
    grades = json.loads(grade_row["grades_json"])
    grade_items = extract_numeric_items(grades)
    ranking = build_class_ranking(list_students_with_grades())
    insights = build_grade_insights(registered["student_number"], grade_items, ranking)
    await callback.message.edit_text(grades_text(registered, grades, insights), reply_markup=simple_back_home_markup())


@router.callback_query(F.data == MENU_REP_PANEL)
async def menu_rep_panel(callback: CallbackQuery) -> None:
    await callback.answer()
    if not is_rep_candidate(callback.from_user.id):
        await callback.message.edit_text("⛔ شما نماینده ثبت‌شده نیستی.", reply_markup=simple_back_home_markup())
        return
    if not is_verified_representative(callback.from_user.id):
        await callback.message.edit_text("⛔ ابتدا احراز هویت نماینده را کامل کن.", reply_markup=simple_back_home_markup())
        return
    pending_count = len(list_pending_verification_requests())
    form_count = len(list_forms_by_creator(callback.from_user.id))
    schedule_count = len(list_form_schedules(callback.from_user.id, active_only=True))
    await callback.message.edit_text(
        representative_panel_text(pending_count, form_count, schedule_count),
        reply_markup=rep_panel_markup(),
    )


@router.callback_query(F.data == MENU_REP_PENDING)
async def menu_rep_pending(callback: CallbackQuery) -> None:
    await callback.answer()
    page = 1
    rows = list_pending_verification_requests(limit=PENDING_PAGE_SIZE, offset=0)
    total = len(list_pending_verification_requests(limit=1000, offset=0))
    pages = max(1, (total + PENDING_PAGE_SIZE - 1) // PENDING_PAGE_SIZE)
    kb = InlineKeyboardMarkup(
        inline_keyboard=(
            [[InlineKeyboardButton(text="▶️ بعدی", callback_data=f"{PREFIX_PAGE}pending:2")]] if pages > 1 else []
        ) + [[InlineKeyboardButton(text="↩️ پنل نماینده", callback_data=MENU_REP_PANEL)]]
    )
    await callback.message.edit_text(pending_requests_text(rows, page), reply_markup=kb)


@router.callback_query(F.data.startswith(f"{PREFIX_PAGE}"))
async def paginate(callback: CallbackQuery) -> None:
    await callback.answer()
    payload = callback.data[len(PREFIX_PAGE):]
    section, page_raw = payload.split(":")
    page = max(1, int(page_raw))
    if section == "pending":
        total = len(list_pending_verification_requests(limit=1000, offset=0))
        pages = max(1, (total + PENDING_PAGE_SIZE - 1) // PENDING_PAGE_SIZE)
        rows = list_pending_verification_requests(limit=PENDING_PAGE_SIZE, offset=(page - 1) * PENDING_PAGE_SIZE)
        kb_rows = []
        nav = []
        if page > 1:
            nav.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"{PREFIX_PAGE}pending:{page - 1}"))
        if page < pages:
            nav.append(InlineKeyboardButton(text="▶️ بعدی", callback_data=f"{PREFIX_PAGE}pending:{page + 1}"))
        if nav:
            kb_rows.append(nav)
        kb_rows.append([InlineKeyboardButton(text="↩️ پنل نماینده", callback_data=MENU_REP_PANEL)])
        await callback.message.edit_text(pending_requests_text(rows, page), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
        return
    if section == "forms":
        forms = list_forms_by_creator(callback.from_user.id)
        pages = max(1, (len(forms) + FORMS_PAGE_SIZE - 1) // FORMS_PAGE_SIZE)
        chunk = forms[(page - 1) * FORMS_PAGE_SIZE : page * FORMS_PAGE_SIZE]
        await callback.message.edit_text("📚 <b>فرم‌های من</b>", reply_markup=form_list_markup(chunk, page, pages))


@router.callback_query(F.data == MENU_REP_FORMS)
async def menu_rep_forms(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text("🗂 <b>مدیریت فرم‌ها</b>", reply_markup=forms_menu_markup())


@router.callback_query(F.data == MENU_REP_FORM_LIST)
async def menu_rep_form_list(callback: CallbackQuery) -> None:
    await callback.answer()
    forms = list_forms_by_creator(callback.from_user.id)
    page = 1
    chunk = forms[:FORMS_PAGE_SIZE]
    pages = max(1, (len(forms) + FORMS_PAGE_SIZE - 1) // FORMS_PAGE_SIZE)
    await callback.message.edit_text("📚 <b>فرم‌های من</b>", reply_markup=form_list_markup(chunk, page, pages))


@router.callback_query(F.data == MENU_REP_FORM_CREATE)
async def begin_form_create(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await state.update_data(questions=[])
    await state.set_state(FormCreateStates.waiting_title)
    await callback.message.edit_text("➕ عنوان فرم را بفرست.", reply_markup=cancel_markup())


@router.message(FormCreateStates.waiting_title)
async def create_form_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=(message.text or "").strip())
    await state.set_state(FormCreateStates.waiting_description)
    await message.answer("📝 توضیح فرم را بفرست. اگر ندارد، «ندارد» را بفرست.", reply_markup=cancel_markup())


@router.message(FormCreateStates.waiting_description)
async def create_form_description(message: Message, state: FSMContext) -> None:
    description = (message.text or "").strip()
    await state.update_data(description="" if description == "ندارد" else description)
    await state.set_state(FormCreateStates.waiting_deadline)
    await message.answer("⏰ مهلت را با قالب <code>2026/04/30 18:30</code> بفرست یا «ندارد».", reply_markup=cancel_markup())


@router.message(FormCreateStates.waiting_deadline)
async def create_form_deadline(message: Message, state: FSMContext) -> None:
    deadline = _parse_user_datetime(message.text or "")
    if (message.text or "").strip() not in {"ندارد", "-", "skip", "Skip"} and deadline is None:
        await message.answer("⚠️ زمان نامعتبر است.", reply_markup=cancel_markup())
        return
    await state.update_data(deadline_at=deadline)
    await state.set_state(FormCreateStates.waiting_capacity)
    await message.answer("📦 ظرفیت را عددی بفرست یا «ندارد».", reply_markup=cancel_markup())


@router.message(FormCreateStates.waiting_capacity)
async def create_form_capacity(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if raw in {"ندارد", "-", ""}:
        capacity = None
    else:
        normalized = normalize_student_number(raw)
        if not normalized:
            await message.answer("⚠️ ظرفیت باید عددی باشد.", reply_markup=cancel_markup())
            return
        capacity = int(normalized)
    await state.update_data(capacity=capacity)
    await state.set_state(FormCreateStates.waiting_waitlist)
    await message.answer("🪪 اگر ظرفیت پر شد، لیست انتظار فعال باشد؟", reply_markup=required_markup())


@router.callback_query(FormCreateStates.waiting_waitlist, F.data.startswith(PREFIX_REQUIRED))
async def create_form_waitlist(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    waitlist_enabled = callback.data.endswith("yes")
    await state.update_data(waitlist_enabled=waitlist_enabled)
    await state.set_state(FormCreateStates.waiting_question_type)
    await callback.message.edit_text("🧩 نوع سوال اول را انتخاب کن.", reply_markup=question_type_markup())


@router.callback_query(FormCreateStates.waiting_question_type, F.data.startswith(PREFIX_QUESTION_TYPE))
async def create_question_type(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    field_type = callback.data.split(":")[1]
    await state.update_data(current_question={"field_type": field_type})
    await state.set_state(FormCreateStates.waiting_question_label)
    await callback.message.edit_text("❓ متن سوال را بفرست.", reply_markup=cancel_markup())


@router.message(FormCreateStates.waiting_question_label)
async def create_question_label(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    current = data.get("current_question", {})
    current["label"] = (message.text or "").strip()
    await state.update_data(current_question=current)
    if current["field_type"] in {"multiple_choice", "checkboxes", "dropdown"}:
        await state.set_state(FormCreateStates.waiting_question_options)
        await message.answer("🧾 گزینه‌ها را خط‌به‌خط بفرست.", reply_markup=cancel_markup())
    else:
        await state.set_state(FormCreateStates.waiting_question_required)
        await message.answer("این سوال اجباری باشد؟", reply_markup=required_markup())


@router.message(FormCreateStates.waiting_question_options)
async def create_question_options(message: Message, state: FSMContext) -> None:
    options = [line.strip() for line in (message.text or "").splitlines() if line.strip()]
    if len(options) < 2:
        await message.answer("⚠️ حداقل دو گزینه لازم است.", reply_markup=cancel_markup())
        return
    data = await state.get_data()
    current = data.get("current_question", {})
    current["options"] = options
    await state.update_data(current_question=current)
    await state.set_state(FormCreateStates.waiting_question_required)
    await message.answer("این سوال اجباری باشد؟", reply_markup=required_markup())


@router.callback_query(FormCreateStates.waiting_question_required, F.data.startswith(PREFIX_REQUIRED))
async def create_question_required(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    current = data.get("current_question", {})
    current["is_required"] = callback.data.endswith("yes")
    questions = data.get("questions", [])
    questions.append(current)
    await state.update_data(questions=questions, current_question=None)
    await state.set_state(FormCreateStates.waiting_add_another)
    await callback.message.edit_text("✅ سوال ذخیره شد. سوال دیگری هم می‌خواهی؟", reply_markup=add_another_question_markup())


@router.callback_query(FormCreateStates.waiting_add_another, F.data.startswith(PREFIX_ADD_ANOTHER_QUESTION))
async def create_question_next(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    another = callback.data.endswith("yes")
    if another:
        await state.set_state(FormCreateStates.waiting_question_type)
        await callback.message.edit_text("🧩 نوع سوال بعدی را انتخاب کن.", reply_markup=question_type_markup())
        return
    data = await state.get_data()
    registration = get_active_registration_by_tg_id(callback.from_user.id)
    form_id = create_form(
        title=data["title"],
        description=data["description"],
        deadline_at=data["deadline_at"],
        capacity=data["capacity"],
        waitlist_enabled=data["waitlist_enabled"],
        created_by_tg_id=callback.from_user.id,
        created_by_student_number=registration["student_number"],
        questions=data["questions"],
        status=FORM_STATUS_OPEN,
    )
    await state.clear()
    form_row = get_form_by_id(form_id)
    stats = get_form_statistics(form_id)
    questions = list_form_questions(form_id)
    await callback.message.edit_text(form_summary_text(form_row, stats, questions), reply_markup=form_detail_markup(form_id))


@router.callback_query(F.data.startswith(PREFIX_FORM_VIEW))
async def view_form(callback: CallbackQuery) -> None:
    await callback.answer()
    form_id = int(callback.data.split(":")[1])
    if not await ensure_form_owner(callback, form_id):
        return
    form_row = get_form_by_id(form_id)
    questions = list_form_questions(form_id)
    stats = get_form_statistics(form_id)
    await callback.message.edit_text(form_summary_text(form_row, stats, questions), reply_markup=form_detail_markup(form_id))


@router.callback_query(F.data.startswith(PREFIX_FORM_JOIN))
async def start_form_submission(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if not await ensure_verified(callback, state):
        return
    form_id = int(callback.data.split(":")[1])
    form = get_form_by_id(form_id)
    questions = [dict(row) for row in list_form_questions(form_id)]
    if not form or form["status"] != FORM_STATUS_OPEN:
        await callback.message.edit_text("⛔ این فرم بسته است.", reply_markup=simple_back_home_markup())
        return
    if get_form_submission(form_id, callback.from_user.id):
        await callback.message.edit_text("✅ شما قبلا این فرم را ارسال کرده‌اید.", reply_markup=simple_back_home_markup())
        return
    await state.set_state(FormSubmitStates.answering_question)
    await state.update_data(form_id=form_id, questions=questions, question_index=0, answers={}, checkbox_selected=[])
    await prompt_next_question(callback.message, state)


async def prompt_next_question(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    questions = data["questions"]
    index = data["question_index"]
    if index >= len(questions):
        await finish_form_submission(message, state)
        return
    question = questions[index]
    qid = question["id"]
    text = ask_question_text(index + 1, len(questions), question)
    if question["field_type"] in {"multiple_choice", "dropdown"}:
        options = json.loads(question["options_json"] or "[]")
        await message.answer(text, reply_markup=single_choice_markup(qid, options))
    elif question["field_type"] == "checkboxes":
        options = json.loads(question["options_json"] or "[]")
        await message.answer(text, reply_markup=checkbox_markup(qid, options, set()))
    else:
        await message.answer(text, reply_markup=cancel_markup())


@router.callback_query(FormSubmitStates.answering_question, F.data.startswith(PREFIX_CHOICE_PICK))
async def answer_single_choice(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    payload = callback.data[len(PREFIX_CHOICE_PICK):]
    question_id_raw, option_index_raw = payload.split(":")
    question_id = int(question_id_raw)
    option_index = int(option_index_raw)
    data = await state.get_data()
    questions = data["questions"]
    question = questions[data["question_index"]]
    options = json.loads(question["options_json"] or "[]")
    answer = options[option_index]
    answers = data.get("answers", {})
    answers[str(question_id)] = {"answer_text": answer, "answer_json": [answer]}
    await state.update_data(answers=answers, question_index=data["question_index"] + 1)
    await callback.message.answer(f"✅ پاسخ ثبت شد: {e(answer)}")
    await prompt_next_question(callback.message, state)


@router.callback_query(FormSubmitStates.answering_question, F.data.startswith(PREFIX_CHECKBOX_TOGGLE))
async def answer_checkbox_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    payload = callback.data[len(PREFIX_CHECKBOX_TOGGLE):]
    question_id_raw, option_index_raw = payload.split(":")
    question_id = int(question_id_raw)
    option_index = int(option_index_raw)
    data = await state.get_data()
    selected = set(data.get("checkbox_selected", []))
    if option_index in selected:
        selected.remove(option_index)
    else:
        selected.add(option_index)
    question = data["questions"][data["question_index"]]
    options = json.loads(question["options_json"] or "[]")
    await state.update_data(checkbox_selected=list(selected))
    await callback.message.edit_reply_markup(reply_markup=checkbox_markup(question_id, options, selected))


@router.callback_query(FormSubmitStates.answering_question, F.data.startswith(PREFIX_CHECKBOX_DONE))
async def answer_checkbox_done(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    question_id = int(callback.data[len(PREFIX_CHECKBOX_DONE):])
    data = await state.get_data()
    question = data["questions"][data["question_index"]]
    options = json.loads(question["options_json"] or "[]")
    selected_indexes = data.get("checkbox_selected", [])
    selected_values = [options[index] for index in selected_indexes]
    answers = data.get("answers", {})
    answers[str(question_id)] = {"answer_text": ", ".join(selected_values), "answer_json": selected_values}
    await state.update_data(answers=answers, question_index=data["question_index"] + 1, checkbox_selected=[])
    await callback.message.answer("✅ انتخاب‌ها ثبت شد.")
    await prompt_next_question(callback.message, state)


@router.message(FormSubmitStates.answering_question)
async def answer_textual_question(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    question = data["questions"][data["question_index"]]
    value = (message.text or "").strip()
    if question["field_type"] == "number" and not normalize_student_number(value):
        await message.answer("⚠️ این سوال عددی است. مقدار معتبر بفرست.", reply_markup=cancel_markup())
        return
    if question["field_type"] == "date_time":
        parsed = _parse_user_datetime(value)
        if parsed is None:
            await message.answer("⚠️ قالب تاریخ/زمان نامعتبر است.", reply_markup=cancel_markup())
            return
        value = format_datetime_fa(parsed)
    answers = data.get("answers", {})
    answers[str(question["id"])] = {"answer_text": value, "answer_json": [value]}
    await state.update_data(answers=answers, question_index=data["question_index"] + 1)
    await prompt_next_question(message, state)


async def finish_form_submission(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    form_id = data["form_id"]
    answers_map = data.get("answers", {})
    answers_payload = [
        {"question_id": int(question_id), "answer_text": payload["answer_text"], "answer_json": payload.get("answer_json", [])}
        for question_id, payload in answers_map.items()
    ]
    registration = get_active_registration_by_tg_id(message.from_user.id)
    status, order = submit_form(
        form_id=form_id,
        telegram_user_id=message.from_user.id,
        student_number=registration["student_number"],
        full_name=registration["full_name"],
        username=registration["username"],
        answers=answers_payload,
    )
    await state.clear()
    if status == "capacity_full":
        await message.answer("⛔ ظرفیت فرم پر شده و لیست انتظار هم غیرفعال است.", reply_markup=home_markup(message.from_user.id, True))
        return
    if status == "duplicate":
        await message.answer("✅ قبلا این فرم را ثبت کرده‌ای.", reply_markup=home_markup(message.from_user.id, True))
        return
    if status == "waitlist":
        text = f"🟡 پاسخ شما در لیست انتظار ثبت شد.\nشماره اولویت: {code(order)}"
    else:
        text = f"✅ پاسخ شما ثبت شد.\nشماره ثبت: {code(order)}"
    await message.answer(text, reply_markup=home_markup(message.from_user.id, True))


@router.callback_query(F.data == MENU_REP_IMPORT_GRADES)
async def begin_import_grades(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(GradeImportStates.waiting_course_title)
    await callback.message.edit_text("📚 عنوان درس یا ارزیابی را بفرست.", reply_markup=cancel_markup())


@router.message(GradeImportStates.waiting_course_title)
async def import_grade_title(message: Message, state: FSMContext) -> None:
    await state.update_data(course_title=(message.text or "").strip())
    await state.set_state(GradeImportStates.waiting_grade_lines)
    await message.answer(
        f"🧾 لیست نمره‌ها را خط‌به‌خط بفرست. نمونه:\n{code('40111270001, 18.5')}",
        reply_markup=cancel_markup(),
    )


@router.message(GradeImportStates.waiting_grade_lines)
async def import_grade_lines(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    grade_entries, invalid_lines = parse_grade_list_text(message.text or "")
    if not grade_entries:
        await message.answer("⚠️ هیچ ردیف معتبری پیدا نشد.", reply_markup=cancel_markup())
        return
    result = bulk_upsert_course_grades(data["course_title"], grade_entries)
    await state.clear()
    missing = result["missing_students"]
    lines = [
        "✅ ثبت نمره انجام شد.",
        f"• ردیف معتبر: {code(len(grade_entries))}",
        f"• ذخیره موفق: {code(result['updated_count'])}",
        f"• دانشجوی ناموجود: {code(len(missing))}",
        f"• ردیف نامعتبر: {code(len(invalid_lines))}",
    ]
    await message.answer("\n".join(lines), reply_markup=rep_panel_markup())


@router.callback_query(F.data == MENU_REP_BROADCAST)
async def begin_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(BroadcastStates.waiting_message)
    await callback.message.edit_text("📣 متن اطلاعیه را بفرست.", reply_markup=cancel_markup())


@router.message(BroadcastStates.waiting_message)
async def do_broadcast(message: Message, state: FSMContext, bot: Bot) -> None:
    payload = (message.text or "").strip()
    recipients = list_active_registered_users()
    success_count = 0
    failed_count = 0
    for recipient in recipients:
        try:
            await bot.send_message(recipient["telegram_user_id"], f"📣 <b>اطلاعیه کلاس</b>\n\n{e(payload)}")
            success_count += 1
        except Exception:
            failed_count += 1
    await state.clear()
    await message.answer(
        f"✅ اطلاعیه ارسال شد.\n• موفق: {code(success_count)}\n• ناموفق: {code(failed_count)}",
        reply_markup=rep_panel_markup(),
    )


@router.callback_query(F.data.startswith(PREFIX_FORM_EXPORT))
async def export_form(callback: CallbackQuery, bot: Bot) -> None:
    await callback.answer()
    _, export_type, form_id_raw = callback.data.split(":")
    form_id = int(form_id_raw)
    if not await ensure_form_owner(callback, form_id):
        return
    if export_type == "names":
        await callback.message.answer(build_text_name_list(form_id))
        return
    if export_type == "name_ids":
        await callback.message.answer(build_text_name_student_list(form_id))
        return
    if export_type == "csv":
        data = build_csv_bytes(form_id)
        await bot.send_document(callback.from_user.id, BufferedInputFile(data, filename=f"form_{form_id}.csv"))
        return
    if export_type == "xlsx":
        data = build_xlsx_bytes(form_id)
        await bot.send_document(callback.from_user.id, BufferedInputFile(data, filename=f"form_{form_id}.xlsx"))
        return
    if export_type == "json":
        data = build_json_bytes(form_id)
        await bot.send_document(callback.from_user.id, BufferedInputFile(data, filename=f"form_{form_id}.json"))


@router.callback_query(F.data.startswith(PREFIX_FORM_DUPLICATE))
async def duplicate_form_handler(callback: CallbackQuery) -> None:
    await callback.answer()
    form_id = int(callback.data.split(":")[1])
    if not await ensure_form_owner(callback, form_id):
        return
    registration = get_active_registration_by_tg_id(callback.from_user.id)
    new_form_id = duplicate_form(form_id, callback.from_user.id, registration["student_number"])
    form_row = get_form_by_id(new_form_id)
    stats = get_form_statistics(new_form_id)
    questions = list_form_questions(new_form_id)
    await callback.message.edit_text(form_summary_text(form_row, stats, questions), reply_markup=form_detail_markup(new_form_id))


@router.callback_query(F.data.startswith(PREFIX_FORM_CLOSE))
async def close_form_handler(callback: CallbackQuery) -> None:
    form_id = int(callback.data.split(":")[1])
    if not await ensure_form_owner(callback, form_id):
        return
    await callback.answer("فرم بسته شد.")
    close_form(form_id)
    form_row = get_form_by_id(form_id)
    stats = get_form_statistics(form_id)
    questions = list_form_questions(form_id)
    await callback.message.edit_text(form_summary_text(form_row, stats, questions), reply_markup=form_detail_markup(form_id))


@router.callback_query(F.data.startswith(PREFIX_FORM_REOPEN))
async def reopen_form_handler(callback: CallbackQuery) -> None:
    form_id = int(callback.data.split(":")[1])
    if not await ensure_form_owner(callback, form_id):
        return
    await callback.answer("فرم باز شد.")
    reopen_form(form_id)
    form_row = get_form_by_id(form_id)
    stats = get_form_statistics(form_id)
    questions = list_form_questions(form_id)
    await callback.message.edit_text(form_summary_text(form_row, stats, questions), reply_markup=form_detail_markup(form_id))


@router.callback_query(F.data.startswith(PREFIX_FORM_REMIND))
async def remind_non_submitters(callback: CallbackQuery, bot: Bot) -> None:
    await callback.answer()
    form_id = int(callback.data.split(":")[1])
    if not await ensure_form_owner(callback, form_id):
        return
    form = get_form_by_id(form_id)
    if not form:
        return
    me = await bot.get_me()
    link = _build_form_link(me.username, form["share_token"])
    recipients = list_non_submitters(form_id)
    sent = 0
    for recipient in recipients:
        try:
            await bot.send_message(
                recipient["telegram_user_id"],
                (
                    f"⏳ <b>یادآوری ثبت‌نام</b>\n"
                    f"فرم <b>{e(form['title'])}</b> هنوز توسط شما تکمیل نشده است.\n"
                    f"🔗 {code(link)}"
                ),
            )
            sent += 1
        except Exception:
            continue
    await callback.message.answer(f"📣 یادآوری برای {code(sent)} نفر ارسال شد.")


@router.callback_query(F.data.startswith(PREFIX_FORM_MANUAL_ADD))
async def begin_manual_add(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    form_id = int(callback.data.split(":")[1])
    if not await ensure_form_owner(callback, form_id):
        return
    await state.set_state(FormAdminStates.waiting_manual_add_student)
    await state.update_data(target_form_id=form_id)
    await callback.message.answer("➕ شماره دانشجویی و نام را با قالب `student_number | full_name` بفرست.", reply_markup=cancel_markup())


@router.message(FormAdminStates.waiting_manual_add_student)
async def do_manual_add(message: Message, state: FSMContext) -> None:
    payload = message.text or ""
    if "|" not in payload:
        await message.answer("⚠️ قالب درست نیست.", reply_markup=cancel_markup())
        return
    student_number_raw, full_name = [part.strip() for part in payload.split("|", 1)]
    student_number = normalize_student_number(student_number_raw)
    data = await state.get_data()
    status, order = manual_add_submission(data["target_form_id"], student_number, full_name)
    await state.clear()
    await message.answer(f"✅ دانشجو اضافه شد. وضعیت: {code(status)} | ترتیب: {code(order)}", reply_markup=rep_panel_markup())


@router.callback_query(F.data.startswith(PREFIX_FORM_REMOVE_SUBMISSION))
async def begin_remove_submission(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    form_id = int(callback.data.split(":")[1])
    if not await ensure_form_owner(callback, form_id):
        return
    await state.set_state(FormAdminStates.waiting_manual_remove_student)
    await state.update_data(target_form_id=form_id)
    await callback.message.answer("🗑 شماره دانشجویی را بفرست تا از فرم حذف شود.", reply_markup=cancel_markup())


@router.message(FormAdminStates.waiting_manual_remove_student)
async def do_remove_submission(message: Message, state: FSMContext) -> None:
    student_number = normalize_student_number(message.text or "")
    data = await state.get_data()
    removed = remove_submission(data["target_form_id"], student_number)
    await state.clear()
    await message.answer(f"✅ تعداد رکوردهای تغییر یافته: {code(removed)}", reply_markup=rep_panel_markup())


@router.callback_query(F.data.startswith(PREFIX_FORM_SEARCH))
async def begin_search_submission(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    form_id = int(callback.data[len(PREFIX_FORM_SEARCH):])
    if not await ensure_form_owner(callback, form_id):
        return
    await state.set_state(FormAdminStates.waiting_search_query)
    await state.update_data(target_form_id=form_id)
    await callback.message.answer("🔍 عبارت جستجو را بفرست: نام، شماره دانشجویی یا یوزرنیم.", reply_markup=cancel_markup())


@router.message(FormAdminStates.waiting_search_query)
async def do_search_submission(message: Message, state: FSMContext) -> None:
    query = (message.text or "").strip()
    data = await state.get_data()
    form_id = data["target_form_id"]
    results = list_form_submissions(form_id, query=query)
    form_row = get_form_by_id(form_id)
    await state.clear()
    await message.answer(submissions_text(form_row, list(results), title="نتیجه جستجو"), reply_markup=rep_panel_markup())


@router.callback_query(F.data == MENU_REP_SCHEDULES)
async def list_schedules(callback: CallbackQuery) -> None:
    await callback.answer()
    rows = list_form_schedules(callback.from_user.id)
    await callback.message.edit_text(schedule_list_text(rows), reply_markup=rep_panel_markup())


@router.callback_query(F.data.startswith(PREFIX_SCHEDULE_FORM))
async def begin_schedule(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    form_id = int(callback.data.split(":")[1])
    if not await ensure_form_owner(callback, form_id):
        return
    await state.set_state(ScheduleStates.waiting_channel_id)
    await state.update_data(schedule_form_id=form_id)
    await callback.message.answer("📢 شناسه کانال را بفرست. مثال: `-1001234567890`", reply_markup=cancel_markup())


@router.message(ScheduleStates.waiting_channel_id)
async def schedule_channel(message: Message, state: FSMContext) -> None:
    text = (message.text or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")).strip()
    raw = normalize_student_number(text)
    if not raw:
        await message.answer("⚠️ شناسه کانال نامعتبر است.", reply_markup=cancel_markup())
        return
    channel_id = int(text)
    await state.update_data(channel_id=channel_id)
    await state.set_state(ScheduleStates.waiting_post_at)
    await message.answer("⏰ زمان انتشار را با قالب `2026/04/30 18:30` بفرست.", reply_markup=cancel_markup())


@router.message(ScheduleStates.waiting_post_at)
async def schedule_post_at(message: Message, state: FSMContext) -> None:
    post_at = _parse_user_datetime(message.text or "")
    if post_at is None:
        await message.answer("⚠️ زمان انتشار نامعتبر است.", reply_markup=cancel_markup())
        return
    await state.update_data(post_at=post_at)
    await state.set_state(ScheduleStates.waiting_deadline)
    await message.answer("🕒 مهلت ثبت‌نام فرم منتشرشده را بفرست یا «ندارد».", reply_markup=cancel_markup())


@router.message(ScheduleStates.waiting_deadline)
async def schedule_deadline(message: Message, state: FSMContext) -> None:
    deadline = _parse_user_datetime(message.text or "")
    if (message.text or "").strip() not in {"ندارد", "-", "skip", "Skip"} and deadline is None:
        await message.answer("⚠️ مهلت نامعتبر است.", reply_markup=cancel_markup())
        return
    await state.update_data(registration_deadline_at=deadline)
    await state.set_state(ScheduleStates.waiting_recurring)
    await message.answer("🔁 نوع تکرار را انتخاب کن.", reply_markup=schedule_recurring_markup())


@router.callback_query(ScheduleStates.waiting_recurring, F.data.startswith(PREFIX_SCHEDULE_CANCEL))
async def finish_schedule(
    callback: CallbackQuery,
    state: FSMContext,
    scheduler: AsyncIOScheduler,
    schedule_runner,
) -> None:
    await callback.answer()
    recurring_rule = callback.data.split(":")[1]
    if recurring_rule == "once":
        recurring_rule = None
    data = await state.get_data()
    schedule_id = create_form_schedule(
        template_form_id=data["schedule_form_id"],
        channel_id=data["channel_id"],
        post_at=data["post_at"],
        registration_deadline_at=data["registration_deadline_at"],
        recurring_rule=recurring_rule,
        created_by_tg_id=callback.from_user.id,
    )
    from bot.services.scheduler import schedule_job
    schedule_job(scheduler, schedule_id, data["post_at"], callback=schedule_runner)
    await state.clear()
    await callback.message.edit_text(
        f"✅ زمان‌بندی ثبت شد.\n🆔 {code(schedule_id)}\n⏰ {code(format_datetime_fa(data['post_at']))}",
        reply_markup=rep_panel_markup(),
    )


@router.callback_query(F.data == MENU_ADMIN_PANEL)
async def menu_admin_panel(callback: CallbackQuery) -> None:
    await callback.answer()
    if not is_admin(callback.from_user.id):
        await callback.message.edit_text("⛔ دسترسی مدیریت نداری.", reply_markup=simple_back_home_markup())
        return
    recent = list_recent_registrations()
    lines = ["🛠 <b>پنل مدیریت</b>", "", "<b>ثبت‌های اخیر</b>"]
    for row in recent:
        lines.append(f"• {e(row['full_name'])} — {code(row['student_number'])}")
    await callback.message.edit_text("\n".join(lines), reply_markup=admin_panel_markup())


@router.callback_query(F.data == MENU_ADMIN_REMOVE)
async def begin_admin_remove(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(AdminStates.waiting_remove_student)
    await callback.message.edit_text("🗑 شماره دانشجویی را بفرست تا ثبت فعالش غیرفعال شود.", reply_markup=cancel_markup())


@router.message(AdminStates.waiting_remove_student, F.text)
async def admin_remove_student(message: Message, state: FSMContext) -> None:
    student_number = normalize_student_number(message.text or "")
    removed = deactivate_student(student_number)
    await state.clear()
    await message.answer(f"✅ تعداد ثبت فعال غیرفعال‌شده: {code(removed)}", reply_markup=admin_panel_markup())


@router.message()
async def plain_text_router(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current:
        return
    await message.answer(
        f"برای استفاده از {e(PROFILE.display_name)} از دکمه‌های اینلاین یا /start استفاده کن.",
        reply_markup=home_markup(message.from_user.id, is_verified_user(message.from_user.id)),
    )
