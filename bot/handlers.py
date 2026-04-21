from __future__ import annotations

import json
from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram.types import BufferedInputFile, CallbackQuery, CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app_callbacks import (
    MENU_ADMIN_BACKUP,
    MENU_ADMIN_CHANNELS,
    MENU_ADMIN_PANEL,
    MENU_ADMIN_REMOVE,
    MENU_ADMIN_REMOVE_DIRECT,
    MENU_ADMIN_STUDENTS,
    MENU_CANCEL,
    MENU_GRADES,
    MENU_HOME,
    MENU_PROFILE,
    MENU_REGISTER,
    MENU_REP_BROADCAST,
    MENU_REP_FORMS,
    MENU_REP_FORM_CREATE,
    MENU_REP_FORM_CREATE_QUICK,
    MENU_REP_FORM_LIST,
    MENU_REP_IMPORT_GRADES,
    MENU_REP_PANEL,
    MENU_REP_PENDING,
    MENU_REP_SCHEDULES,
    PREFIX_ADD_ANOTHER_QUESTION,
    PREFIX_ADMIN_CHANNEL_PICK,
    PREFIX_ADMIN_CHANNEL_SET,
    PREFIX_ADMIN_REMOVE_CANCEL,
    PREFIX_ADMIN_REMOVE_CONFIRM,
    PREFIX_ADMIN_REMOVE_SELECT,
    PREFIX_ADMIN_STUDENT_SEARCH,
    PREFIX_ADMIN_STUDENT_SORT,
    PREFIX_CHECKBOX_DONE,
    PREFIX_CHECKBOX_TOGGLE,
    PREFIX_CHOICE_PICK,
    PREFIX_DATE_PICKER,
    PREFIX_FORM_CLOSE,
    PREFIX_FORM_CHANNELS,
    PREFIX_FORM_CHANNEL_PICK,
    PREFIX_FORM_DELETE,
    PREFIX_FORM_DELETE_CONFIRM,
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
    PREFIX_SCHEDULE_CHANNEL_PICK,
    PREFIX_SCHEDULE_DEACTIVATE,
    PREFIX_SCHEDULE_FORM,
    PREFIX_SCHEDULE_VIEW,
    PREFIX_VERIFY_APPROVE,
    PREFIX_VERIFY_REJECT,
)
from bot.services.backup import build_database_backup_zip
from bot.services.date_picker import clamp_day, default_picker_state, jalali_selection_to_utc_iso, now_jalali, shift_month
from assistant_profile import PROFILE
from bot.services.datetime_fa import TEHRAN_TZ, format_datetime_fa, render_telegram_time
from bot.services.exporters import (
    build_csv_bytes,
    build_json_bytes,
    build_text_name_list,
    build_text_name_student_list,
    build_xlsx_bytes,
)
from bot.services.formatting import code, e
from bot.services.media import resolve_verification_photo
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
    admin_channel_picker_markup,
    admin_channel_settings_markup,
    admin_panel_markup,
    admin_remove_confirmation_markup,
    admin_student_list_markup,
    cancel_markup,
    checkbox_markup,
    date_picker_markup,
    form_detail_markup,
    form_channel_settings_markup,
    form_delete_confirmation_markup,
    form_join_markup,
    form_list_markup,
    forms_menu_markup,
    home_markup,
    pending_requests_markup,
    question_type_markup,
    rep_panel_markup,
    required_markup,
    schedule_detail_markup,
    schedule_list_markup,
    schedule_recurring_markup,
    simple_back_home_markup,
    single_choice_markup,
    verification_request_markup,
)
from bot.ui.texts import (
    admin_panel_text,
    admin_remove_confirmation_text,
    ask_question_text,
    bot_channels_settings_text,
    date_picker_text,
    form_channel_settings_text,
    form_delete_confirmation_text,
    form_join_text,
    form_summary_text,
    grades_text,
    home_text,
    pending_requests_text,
    profile_text,
    registered_students_text,
    representative_panel_text,
    schedule_detail_text,
    schedule_list_text,
    submissions_text,
    verification_intro_text,
    verification_request_message,
)
from db import (
    CHANNEL_KIND_CLASS,
    CHANNEL_KIND_NOTES,
    FORM_KIND_CUSTOM,
    FORM_KIND_QUICK_LIST,
    FORM_STATUS_CLOSED,
    FORM_STATUS_DRAFT,
    FORM_STATUS_OPEN,
    attach_rep_message_refs,
    bulk_upsert_course_grades,
    close_form,
    count_registered_students,
    create_form,
    create_form_schedule,
    create_verification_request,
    decide_verification_request,
    deactivate_schedule,
    deactivate_student,
    delete_form,
    duplicate_form,
    find_student,
    get_active_registration_by_student_number,
    get_active_registration_by_tg_id,
    get_bot_channels,
    get_form_by_id,
    get_form_by_share_token,
    get_form_statistics,
    get_form_submission,
    get_registered_student_by_student_number,
    get_pending_request_by_user_id,
    get_schedule,
    get_student_grades,
    get_verification_request,
    list_active_registered_users,
    list_form_questions,
    list_form_schedules,
    list_form_submissions,
    list_forms_by_creator,
    list_configured_bot_channels,
    list_non_submitters,
    list_pending_verification_requests,
    list_registered_students,
    list_recent_channel_ids,
    list_recent_registrations,
    list_students_with_grades,
    manual_add_submission,
    mark_schedule_run,
    remove_submission,
    reopen_form,
    set_bot_channel,
    submit_form,
    update_form_announcement_channel,
)
from grade_analytics import build_class_ranking, build_grade_insights, extract_numeric_items
from bot.services.scheduler import next_recurring_post

router = Router()

FORMS_PAGE_SIZE = 8
PENDING_PAGE_SIZE = 8
SCHEDULES_PAGE_SIZE = 8
ADMIN_STUDENTS_PAGE_SIZE = 6


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


def _parse_channel_id(raw_text: str) -> int | None:
    text = (raw_text or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")).strip()
    if not text:
        return None
    candidate = text[1:] if text.startswith("-") else text
    if not candidate.isdigit():
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _channel_kind_label(channel_kind: str) -> str:
    if channel_kind == CHANNEL_KIND_NOTES:
        return "جزوه‌نویسی"
    return "اطلاع‌رسانی"


def _build_form_link(bot_username: str, share_token: str) -> str:
    return f"https://t.me/{bot_username}?start=form_{share_token}"


async def _get_user_photo(bot: Bot, user_id: int):
    try:
        photos = await bot.get_user_profile_photos(user_id=user_id, limit=1)
    except Exception:
        return None
    if not photos.photos:
        return None
    return photos.photos[0][-1].file_id


async def _build_form_share_link(bot: Bot, share_token: str) -> str | None:
    try:
        me = await bot.get_me()
    except Exception:
        return None
    if not me.username:
        return None
    return _build_form_link(me.username, share_token)


async def _show_form_detail(callback: CallbackQuery, form_id: int, bot: Bot) -> None:
    form_row = get_form_by_id(form_id)
    questions = list_form_questions(form_id)
    stats = get_form_statistics(form_id)
    share_link = await _build_form_share_link(bot, form_row["share_token"]) if form_row else None
    await callback.message.edit_text(
        form_summary_text(form_row, stats, questions, share_link=share_link),
        reply_markup=form_detail_markup(form_id, share_link=share_link),
    )


async def _show_form_channels(target: Message | CallbackQuery, form_id: int) -> None:
    form_row = get_form_by_id(form_id)
    if not form_row:
        return
    available_channels = list_configured_bot_channels()
    text = form_channel_settings_text(form_row, available_channels)
    markup = form_channel_settings_markup(form_id, available_channels)
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=markup)
    else:
        await target.answer(text, reply_markup=markup)


async def _show_bot_channels(target: Message | CallbackQuery) -> None:
    channels = get_bot_channels()
    text = bot_channels_settings_text(channels)
    markup = admin_channel_settings_markup()
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=markup)
    else:
        await target.answer(text, reply_markup=markup)


async def _finalize_form_create(callback: CallbackQuery, state: FSMContext) -> None:
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
        questions=data.get("questions", []),
        form_kind=data.get("form_kind", FORM_KIND_CUSTOM),
        status=FORM_STATUS_OPEN,
    )
    await state.clear()
    await _show_form_detail(callback, form_id, callback.bot)


async def _show_pending_requests_page(callback: CallbackQuery, page: int) -> None:
    total = len(list_pending_verification_requests(limit=1000, offset=0))
    pages = max(1, (total + PENDING_PAGE_SIZE - 1) // PENDING_PAGE_SIZE)
    page = max(1, min(page, pages))
    rows = list_pending_verification_requests(limit=PENDING_PAGE_SIZE, offset=(page - 1) * PENDING_PAGE_SIZE)
    await callback.message.edit_text(
        pending_requests_text(rows, page, pages),
        reply_markup=pending_requests_markup(page, pages),
    )


async def _show_schedule_page(callback: CallbackQuery, page: int) -> None:
    schedules = list_form_schedules(callback.from_user.id)
    pages = max(1, (len(schedules) + SCHEDULES_PAGE_SIZE - 1) // SCHEDULES_PAGE_SIZE)
    page = max(1, min(page, pages))
    chunk = schedules[(page - 1) * SCHEDULES_PAGE_SIZE : page * SCHEDULES_PAGE_SIZE]
    await callback.message.edit_text(
        schedule_list_text(chunk, page, pages),
        reply_markup=schedule_list_markup(chunk, page, pages),
    )


async def _build_admin_students_view(state: FSMContext, page: int) -> tuple[str, InlineKeyboardMarkup]:
    data = await state.get_data()
    query = (data.get("admin_student_query") or "").strip() or None
    sort_by = data.get("admin_student_sort_by") or "approved_at_desc"
    total = count_registered_students(query=query)
    pages = max(1, (total + ADMIN_STUDENTS_PAGE_SIZE - 1) // ADMIN_STUDENTS_PAGE_SIZE)
    page = max(1, min(page, pages))
    rows = list_registered_students(
        limit=ADMIN_STUDENTS_PAGE_SIZE,
        offset=(page - 1) * ADMIN_STUDENTS_PAGE_SIZE,
        query=query,
        sort_by=sort_by,
    )
    return (
        registered_students_text(rows, page, pages, total, query=query, sort_by=sort_by),
        admin_student_list_markup(rows, page, pages, query=query, sort_by=sort_by),
    )


async def _show_admin_students_page(callback: CallbackQuery, state: FSMContext, page: int) -> None:
    text, markup = await _build_admin_students_view(state, page)
    await callback.message.edit_text(text, reply_markup=markup)


async def _finalize_verification_messages(bot: Bot, request_row, decision_text: str) -> None:
    refs = []
    try:
        refs = json.loads(request_row["rep_message_refs_json"] or "[]")
    except json.JSONDecodeError:
        refs = []

    final_text = verification_request_message(request_row) + f"\n\n{decision_text}"
    for ref in refs:
        chat_id = ref.get("chat_id")
        message_id = ref.get("message_id")
        if not chat_id or not message_id:
            continue
        try:
            await bot.edit_message_caption(
                chat_id=chat_id,
                message_id=message_id,
                caption=final_text,
                reply_markup=None,
            )
            continue
        except Exception:
            pass
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=final_text,
                reply_markup=None,
            )
        except Exception:
            continue


async def _send_date_picker(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    picker = data.get("date_picker")
    if not picker:
        return
    await message.answer(date_picker_text(picker), reply_markup=date_picker_markup(picker))


async def _edit_date_picker(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    picker = data.get("date_picker")
    if not picker:
        await callback.answer("انتخاب‌گر زمان در دسترس نیست.", show_alert=True)
        return
    await callback.message.edit_text(date_picker_text(picker), reply_markup=date_picker_markup(picker))


async def _begin_date_picker(
    message: Message,
    state: FSMContext,
    *,
    target: str,
    label: str,
    allow_none: bool,
) -> None:
    await state.update_data(date_picker=default_picker_state(target=target, label=label, allow_none=allow_none))
    await _send_date_picker(message, state)


async def _finalize_date_picker(callback: CallbackQuery, state: FSMContext, *, selected_iso: str | None) -> None:
    data = await state.get_data()
    picker = data.get("date_picker", {})
    target = picker.get("target")
    await state.update_data(date_picker=None)

    if target == "form_deadline":
        await state.update_data(deadline_at=selected_iso)
        await state.set_state(FormCreateStates.waiting_capacity)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            (
                f"✅ مهلت فرم ثبت شد: {code(format_datetime_fa(selected_iso))}"
                if selected_iso
                else "✅ فرم بدون مهلت ساخته می‌شود."
            ),
            reply_markup=cancel_markup(),
        )
        await callback.message.answer("📦 ظرفیت را عددی بفرست یا «ندارد» را ارسال کن.", reply_markup=cancel_markup())
        return

    if target == "schedule_post_at":
        await state.update_data(post_at=selected_iso)
        await state.set_state(ScheduleStates.waiting_deadline)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            f"✅ زمان انتشار ثبت شد: {code(format_datetime_fa(selected_iso))}",
            reply_markup=cancel_markup(),
        )
        await _begin_date_picker(
            callback.message,
            state,
            target="schedule_deadline",
            label="مهلت ثبت‌نام فرم",
            allow_none=True,
        )
        return

    if target == "schedule_deadline":
        await state.update_data(registration_deadline_at=selected_iso)
        await state.set_state(ScheduleStates.waiting_recurring)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            (
                f"✅ مهلت فرم ثبت شد: {code(format_datetime_fa(selected_iso))}"
                if selected_iso
                else "✅ فرم منتشرشده بدون مهلت ثبت می‌شود."
            ),
            reply_markup=schedule_recurring_markup(),
        )
        return

    if target == "answer_datetime":
        question = data["questions"][data["question_index"]]
        answers = data.get("answers", {})
        if selected_iso is None and question["is_required"]:
            await callback.answer("این سوال اجباری است.", show_alert=True)
            return
        if selected_iso is None:
            answers[str(question["id"])] = {"answer_text": "", "answer_json": []}
        else:
            answers[str(question["id"])] = {
                "answer_text": format_datetime_fa(selected_iso),
                "answer_json": [selected_iso],
            }
        await state.update_data(answers=answers, question_index=data["question_index"] + 1)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            (
                f"✅ زمان انتخاب شد: {code(format_datetime_fa(selected_iso))}"
                if selected_iso
                else "✅ این سوال بدون مقدار رد شد."
            )
        )
        await prompt_next_question(callback.message, state)


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
    photo = resolve_verification_photo(await _get_user_photo(bot, user_id))

    for reviewer_id in verification_reviewer_ids():
        try:
            if photo:
                sent = await bot.send_photo(
                    reviewer_id,
                    photo=photo,
                    caption=verification_request_message(request_row),
                    reply_markup=verification_request_markup(request_id, request_row["student_number"]),
                )
            else:
                sent = await bot.send_message(
                    reviewer_id,
                    verification_request_message(request_row),
                    reply_markup=verification_request_markup(request_id, request_row["student_number"]),
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
    target_column = "notes_channel_id" if schedule["channel_kind"] == CHANNEL_KIND_NOTES else "class_channel_id"
    with get_connection() as conn:
        if target_column == "class_channel_id":
            conn.execute(
                "UPDATE forms SET status = ?, deadline_at = ?, announcement_channel_id = ?, class_channel_id = ? WHERE id = ?",
                (FORM_STATUS_OPEN, with_deadline, schedule["channel_id"], schedule["channel_id"], created_form_id),
            )
        else:
            conn.execute(
                "UPDATE forms SET status = ?, deadline_at = ?, notes_channel_id = ? WHERE id = ?",
                (FORM_STATUS_OPEN, with_deadline, schedule["channel_id"], created_form_id),
            )
    created_form = get_form_by_id(created_form_id)
    link = await _build_form_share_link(bot, created_form["share_token"])
    reply_rows = []
    if link:
        reply_rows.append([InlineKeyboardButton(text="📌 ثبت‌نام در فرم", url=link, style="success")])
        reply_rows.append([InlineKeyboardButton(text="📋 کپی لینک", copy_text=CopyTextButton(text=link))])
    await bot.send_message(
        chat_id=schedule["channel_id"],
        text=(
            f"📢 <b>فرم ثبت‌نام {e(created_form['title'])} فعال شد</b>\n\n"
            f"📝 {e(created_form['description'] or 'بدون توضیح')}\n"
            f"{render_telegram_time(created_form['deadline_at'], 'مهلت ثبت‌نام') if created_form['deadline_at'] else '🗓 <b>مهلت ثبت‌نام:</b> ندارد'}"
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=reply_rows) if reply_rows else None,
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
            await message.answer(
                form_join_text(form, questions),
                reply_markup=form_join_markup(form["id"], form["form_kind"] or FORM_KIND_CUSTOM),
            )
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


@router.callback_query(F.data.startswith(PREFIX_DATE_PICKER))
async def handle_date_picker(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    picker = data.get("date_picker")
    if not picker:
        await callback.answer("انتخاب‌گر زمان فعال نیست.", show_alert=True)
        return

    payload = callback.data[len(PREFIX_DATE_PICKER):]
    action, value = payload.split(":", 1)

    if action == "year_base":
        picker["year_base"] = int(value)
    elif action == "set_year":
        picker["year"] = int(value)
        picker["year_base"] = picker["year"] - 1
        picker["step"] = "month"
    elif action == "set_month":
        picker["month"] = int(value)
        picker["day"] = clamp_day(picker["year"], picker["month"], picker["day"])
        picker["step"] = "day"
    elif action == "nav_month":
        year, month = shift_month(picker["year"], picker["month"], int(value))
        picker["year"] = year
        picker["month"] = month
        picker["day"] = clamp_day(year, month, picker["day"])
        picker["step"] = "day"
    elif action == "set_day":
        picker["day"] = int(value)
        picker["step"] = "hour"
    elif action == "set_hour":
        picker["hour"] = int(value)
        picker["step"] = "minute"
    elif action == "set_minute":
        picker["minute"] = int(value)
        picker["step"] = "confirm"
    elif action == "back":
        picker["step"] = value
    elif action == "today":
        now = now_jalali()
        picker["year"] = now.year
        picker["month"] = now.month
        picker["day"] = now.day
        picker["hour"] = now.hour
        picker["minute"] = (now.minute // 5) * 5
        picker["step"] = "confirm"
    elif action == "clear":
        picker = default_picker_state(
            target=picker["target"],
            label=picker["label"],
            allow_none=bool(picker.get("allow_none")),
        )
    elif action == "skip":
        await _finalize_date_picker(callback, state, selected_iso=None)
        return
    elif action == "confirm":
        selected_iso = jalali_selection_to_utc_iso(
            picker["year"],
            picker["month"],
            picker["day"],
            picker["hour"],
            picker["minute"],
        )
        await _finalize_date_picker(callback, state, selected_iso=selected_iso)
        return

    await state.update_data(date_picker=picker)
    await _edit_date_picker(callback, state)


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
    if result in {"already_reviewed", "student_number_already_linked"}:
        await _finalize_verification_messages(bot, request_row, "⚠️ این درخواست قبلا نهایی شده است.")
        await callback.answer("این درخواست قبلا نهایی شده است.", show_alert=True)
        return
    if approve:
        await _finalize_verification_messages(bot, request_row, "✅ این حساب تایید شد و به شماره دانشجویی متصل شد.")
        await bot.send_message(
            request_row["telegram_user_id"],
            (
                "✅ <b>احراز هویت شما تایید شد.</b>\n"
                f"🎓 شماره دانشجویی: {code(request_row['student_number'])}\n"
                "امکانات دانشجویی از همین حالا برای شما فعال است."
            ),
            reply_markup=home_markup(request_row["telegram_user_id"], True),
        )
    else:
        await _finalize_verification_messages(bot, request_row, "❌ این درخواست رد شد.")
        await bot.send_message(
            request_row["telegram_user_id"],
            (
                "❌ <b>درخواست احراز هویت شما رد شد.</b>\n"
                "از منوی اصلی دوباره فرایند احراز هویت را شروع کن و اطلاعات کامل‌تری بفرست."
            ),
            reply_markup=home_markup(request_row["telegram_user_id"], False),
        )
    await callback.answer("تصمیم شما ثبت شد.")


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
    await _show_pending_requests_page(callback, page=1)


@router.callback_query(F.data.startswith(f"{PREFIX_PAGE}"))
async def paginate(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    payload = callback.data[len(PREFIX_PAGE):]
    section, page_raw = payload.split(":")
    page = max(1, int(page_raw))
    if section == "pending":
        await _show_pending_requests_page(callback, page)
        return
    if section == "forms":
        forms = list_forms_by_creator(callback.from_user.id)
        pages = max(1, (len(forms) + FORMS_PAGE_SIZE - 1) // FORMS_PAGE_SIZE)
        chunk = forms[(page - 1) * FORMS_PAGE_SIZE : page * FORMS_PAGE_SIZE]
        await callback.message.edit_text("📚 <b>فرم‌های من</b>", reply_markup=form_list_markup(chunk, page, pages))
        return
    if section == "schedules":
        await _show_schedule_page(callback, page)
        return
    if section == "admin_students":
        await _show_admin_students_page(callback, state, page)


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
    await state.update_data(questions=[], form_kind=FORM_KIND_CUSTOM)
    await state.set_state(FormCreateStates.waiting_title)
    await callback.message.edit_text("🧩 عنوان فرم سفارشی را بفرست.", reply_markup=cancel_markup())


@router.callback_query(F.data == MENU_REP_FORM_CREATE_QUICK)
async def begin_quick_form_create(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await state.update_data(questions=[], form_kind=FORM_KIND_QUICK_LIST)
    await state.set_state(FormCreateStates.waiting_title)
    await callback.message.edit_text(
        "⚡ عنوان فرم سریع را بفرست. این نوع فرم فقط لیست تاییدشده‌ی نام و شماره دانشجویی جمع می‌کند.",
        reply_markup=cancel_markup(),
    )


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
    await _begin_date_picker(
        message,
        state,
        target="form_deadline",
        label="مهلت فرم",
        allow_none=True,
    )


@router.message(FormCreateStates.waiting_deadline)
async def create_form_deadline(message: Message, state: FSMContext) -> None:
    deadline = _parse_user_datetime(message.text or "")
    if (message.text or "").strip() not in {"ندارد", "-", "skip", "Skip"} and deadline is None:
        await message.answer("⚠️ زمان نامعتبر است. از picker استفاده کن یا زمان را با قالب درست بفرست.", reply_markup=cancel_markup())
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
    data = await state.get_data()
    if data.get("form_kind") == FORM_KIND_QUICK_LIST:
        await _finalize_form_create(callback, state)
        return
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
    await _finalize_form_create(callback, state)


@router.callback_query(F.data.startswith(PREFIX_FORM_VIEW))
async def view_form(callback: CallbackQuery, bot: Bot) -> None:
    await callback.answer()
    form_id = int(callback.data.split(":")[1])
    if not await ensure_form_owner(callback, form_id):
        return
    await _show_form_detail(callback, form_id, bot)


@router.callback_query(F.data.startswith(PREFIX_FORM_CHANNELS))
async def view_form_channels(callback: CallbackQuery) -> None:
    await callback.answer()
    form_id = int(callback.data[len(PREFIX_FORM_CHANNELS):])
    if not await ensure_form_owner(callback, form_id):
        return
    configured_channels = list_configured_bot_channels()
    if len(configured_channels) == 1:
        channel_kind, channel_id = configured_channels[0]
        update_form_announcement_channel(form_id, channel_id)
        await callback.answer(
            f"چون فقط یک کانال سراسری تعیین شده، این فرم به کانال {_channel_kind_label(channel_kind)} فرستاده می‌شود.",
            show_alert=True,
        )
        await _show_form_detail(callback, form_id, callback.bot)
        return
    await _show_form_channels(callback, form_id)


@router.callback_query(F.data.startswith(PREFIX_FORM_CHANNEL_PICK))
async def pick_form_channel(callback: CallbackQuery) -> None:
    await callback.answer()
    payload = callback.data[len(PREFIX_FORM_CHANNEL_PICK):]
    form_id_raw, channel_kind = payload.split(":", 1)
    form_id = int(form_id_raw)
    if channel_kind not in {CHANNEL_KIND_CLASS, CHANNEL_KIND_NOTES}:
        await callback.answer("نوع کانال نامعتبر است.", show_alert=True)
        return
    if not await ensure_form_owner(callback, form_id):
        return
    channels = get_bot_channels()
    channel_id = channels.get(channel_kind)
    if channel_id is None:
        await callback.answer("این کانال سراسری هنوز ثبت نشده است.", show_alert=True)
        return
    update_form_announcement_channel(form_id, channel_id)
    await callback.answer(f"کانال انتشار فرم روی {_channel_kind_label(channel_kind)} تنظیم شد.")
    await _show_form_detail(callback, form_id, callback.bot)


@router.callback_query(F.data.startswith(PREFIX_FORM_DELETE))
async def confirm_form_delete(callback: CallbackQuery) -> None:
    await callback.answer()
    form_id = int(callback.data[len(PREFIX_FORM_DELETE):])
    if not await ensure_form_owner(callback, form_id):
        return
    form_row = get_form_by_id(form_id)
    if not form_row:
        await callback.answer("فرم پیدا نشد.", show_alert=True)
        return
    await callback.message.edit_text(
        form_delete_confirmation_text(form_row),
        reply_markup=form_delete_confirmation_markup(form_id),
    )


@router.callback_query(F.data.startswith(PREFIX_FORM_DELETE_CONFIRM))
async def delete_form_handler(callback: CallbackQuery) -> None:
    await callback.answer()
    form_id = int(callback.data[len(PREFIX_FORM_DELETE_CONFIRM):])
    if not await ensure_form_owner(callback, form_id):
        return
    removed = delete_form(form_id)
    if not removed:
        await callback.answer("فرم پیدا نشد.", show_alert=True)
        return
    await callback.message.edit_text("✅ فرم و داده‌های وابسته‌اش حذف شد.", reply_markup=forms_menu_markup())


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
    elif question["field_type"] == "date_time":
        await state.update_data(
            date_picker=default_picker_state(
                target="answer_datetime",
                label=question["label"],
                allow_none=not bool(question["is_required"]),
            )
        )
        picker_data = (await state.get_data())["date_picker"]
        await message.answer(
            f"{text}\n\n{date_picker_text(picker_data)}",
            reply_markup=date_picker_markup(picker_data),
        )
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
        friendly_value = format_datetime_fa(parsed)
        answers = data.get("answers", {})
        answers[str(question["id"])] = {"answer_text": friendly_value, "answer_json": [parsed]}
        await state.update_data(answers=answers, question_index=data["question_index"] + 1)
        await prompt_next_question(message, state)
        return
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
    await _show_form_detail(callback, new_form_id, callback.bot)


@router.callback_query(F.data.startswith(PREFIX_FORM_CLOSE))
async def close_form_handler(callback: CallbackQuery) -> None:
    form_id = int(callback.data.split(":")[1])
    if not await ensure_form_owner(callback, form_id):
        return
    await callback.answer("فرم بسته شد.")
    close_form(form_id)
    await _show_form_detail(callback, form_id, callback.bot)


@router.callback_query(F.data.startswith(PREFIX_FORM_REOPEN))
async def reopen_form_handler(callback: CallbackQuery) -> None:
    form_id = int(callback.data.split(":")[1])
    if not await ensure_form_owner(callback, form_id):
        return
    await callback.answer("فرم باز شد.")
    reopen_form(form_id)
    await _show_form_detail(callback, form_id, callback.bot)


@router.callback_query(F.data.startswith(PREFIX_FORM_REMIND))
async def remind_non_submitters(callback: CallbackQuery, bot: Bot) -> None:
    await callback.answer()
    form_id = int(callback.data.split(":")[1])
    if not await ensure_form_owner(callback, form_id):
        return
    form = get_form_by_id(form_id)
    if not form:
        return
    link = await _build_form_share_link(bot, form["share_token"])
    recipients = list_non_submitters(form_id)
    sent = 0
    for recipient in recipients:
        try:
            await bot.send_message(
                recipient["telegram_user_id"],
                (
                    f"⏳ <b>یادآوری ثبت‌نام</b>\n"
                    f"فرم <b>{e(form['title'])}</b> هنوز توسط شما تکمیل نشده است.\n"
                    f"{render_telegram_time(form['deadline_at'], 'مهلت پاسخ‌گویی') if form['deadline_at'] else ''}\n"
                    f"{f'🔗 {code(link)}' if link else ''}"
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
    await _show_schedule_page(callback, page=1)


@router.callback_query(F.data.startswith(PREFIX_SCHEDULE_VIEW))
async def view_schedule(callback: CallbackQuery) -> None:
    await callback.answer()
    schedule_id = int(callback.data[len(PREFIX_SCHEDULE_VIEW):])
    schedule = get_schedule(schedule_id)
    if not schedule or schedule["created_by_tg_id"] != callback.from_user.id:
        await callback.answer("این زمان‌بندی برای شما در دسترس نیست.", show_alert=True)
        return
    template_form = get_form_by_id(schedule["template_form_id"])
    await callback.message.edit_text(
        schedule_detail_text(schedule, template_form),
        reply_markup=schedule_detail_markup(schedule_id),
    )


@router.callback_query(F.data.startswith(PREFIX_SCHEDULE_DEACTIVATE))
async def deactivate_schedule_handler(callback: CallbackQuery) -> None:
    await callback.answer()
    schedule_id = int(callback.data[len(PREFIX_SCHEDULE_DEACTIVATE):])
    schedule = get_schedule(schedule_id)
    if not schedule or schedule["created_by_tg_id"] != callback.from_user.id:
        await callback.answer("این زمان‌بندی برای شما در دسترس نیست.", show_alert=True)
        return
    deactivate_schedule(schedule_id)
    await callback.answer("زمان‌بندی غیرفعال شد.")
    await _show_schedule_page(callback, page=1)


@router.callback_query(F.data.startswith(PREFIX_SCHEDULE_FORM))
async def begin_schedule(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    form_id = int(callback.data.split(":")[1])
    if not await ensure_form_owner(callback, form_id):
        return
    form = get_form_by_id(form_id)
    configured_channels = list_configured_bot_channels()
    selected_channel_id = form["announcement_channel_id"] if form else None
    auto_message = None
    if not selected_channel_id:
        if len(configured_channels) == 1:
            channel_kind, selected_channel_id = configured_channels[0]
            update_form_announcement_channel(form_id, selected_channel_id)
            auto_message = (
                f"چون فقط یک کانال سراسری تعیین شده، این فرم به کانال {_channel_kind_label(channel_kind)} فرستاده می‌شود.\n\n"
            )
        elif not configured_channels:
            await callback.answer("هنوز کانال سراسری برای ربات ثبت نشده است.", show_alert=True)
            return
        else:
            await callback.answer("اول کانال انتشار این فرم را انتخاب کن.", show_alert=True)
            await _show_form_channels(callback, form_id)
            return
    channel_kind = CHANNEL_KIND_CLASS
    for configured_kind, configured_channel_id in configured_channels:
        if configured_channel_id == selected_channel_id:
            channel_kind = configured_kind
            break
    if not selected_channel_id:
        await callback.answer("کانال انتشار فرم مشخص نیست.", show_alert=True)
        await _show_form_channels(callback, form_id)
        return
    await state.set_state(ScheduleStates.waiting_post_at)
    await state.update_data(
        schedule_form_id=form_id,
        channel_id=selected_channel_id,
        channel_kind=channel_kind,
    )
    await callback.message.edit_text(
        (
            (auto_message or "")
            + f"📣 این فرم زمان‌دار در کانال {_channel_kind_label(channel_kind)} با شناسه {code(selected_channel_id)} منتشر می‌شود."
        ),
        reply_markup=cancel_markup(),
    )
    await _begin_date_picker(
        callback.message,
        state,
        target="schedule_post_at",
        label="زمان انتشار",
        allow_none=False,
    )


@router.callback_query(ScheduleStates.waiting_channel_id, F.data.startswith(PREFIX_SCHEDULE_CHANNEL_PICK))
async def schedule_channel_pick(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    selected = callback.data[len(PREFIX_SCHEDULE_CHANNEL_PICK):]
    if selected == "manual":
        await callback.message.edit_text("📢 شناسه کانال را بفرست. مثال: `-1001234567890`", reply_markup=cancel_markup())
        return
    channel_id = int(selected)
    await state.update_data(channel_id=channel_id)
    await state.set_state(ScheduleStates.waiting_post_at)
    await callback.message.edit_text(f"📣 کانال انتخاب شد: {code(channel_id)}", reply_markup=None)
    await _begin_date_picker(
        callback.message,
        state,
        target="schedule_post_at",
        label="زمان انتشار",
        allow_none=False,
    )


@router.message(ScheduleStates.waiting_channel_id)
async def schedule_channel(message: Message, state: FSMContext) -> None:
    channel_id = _parse_channel_id(message.text or "")
    if channel_id is None:
        await message.answer("⚠️ شناسه کانال نامعتبر است.", reply_markup=cancel_markup())
        return
    await state.update_data(channel_id=channel_id)
    await state.set_state(ScheduleStates.waiting_post_at)
    await _begin_date_picker(
        message,
        state,
        target="schedule_post_at",
        label="زمان انتشار",
        allow_none=False,
    )


@router.message(ScheduleStates.waiting_post_at)
async def schedule_post_at(message: Message, state: FSMContext) -> None:
    post_at = _parse_user_datetime(message.text or "")
    if post_at is None:
        await message.answer("⚠️ زمان انتشار نامعتبر است. از picker استفاده کن یا زمان معتبر بفرست.", reply_markup=cancel_markup())
        return
    await state.update_data(post_at=post_at)
    await state.set_state(ScheduleStates.waiting_deadline)
    await _begin_date_picker(
        message,
        state,
        target="schedule_deadline",
        label="مهلت ثبت‌نام فرم",
        allow_none=True,
    )


@router.message(ScheduleStates.waiting_deadline)
async def schedule_deadline(message: Message, state: FSMContext) -> None:
    deadline = _parse_user_datetime(message.text or "")
    if (message.text or "").strip() not in {"ندارد", "-", "skip", "Skip"} and deadline is None:
        await message.answer("⚠️ مهلت نامعتبر است. از picker استفاده کن یا زمان معتبر بفرست.", reply_markup=cancel_markup())
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
        channel_kind=data.get("channel_kind", CHANNEL_KIND_CLASS),
    )
    from bot.services.scheduler import schedule_job
    schedule_job(scheduler, schedule_id, data["post_at"], callback=schedule_runner)
    await state.clear()
    await callback.message.edit_text(
        (
            f"✅ <b>زمان‌بندی ثبت شد.</b>\n"
            f"🆔 شناسه: {code(schedule_id)}\n"
            f"{render_telegram_time(data['post_at'], 'انتشار اول')}"
        ),
        reply_markup=rep_panel_markup(),
    )


@router.callback_query(F.data == MENU_ADMIN_PANEL)
async def menu_admin_panel(callback: CallbackQuery) -> None:
    await callback.answer()
    if not is_admin(callback.from_user.id):
        await callback.message.edit_text("⛔ دسترسی مدیریت نداری.", reply_markup=simple_back_home_markup())
        return
    recent = list_recent_registrations()
    total_students = count_registered_students()
    await callback.message.edit_text(admin_panel_text(recent, total_students), reply_markup=admin_panel_markup())


@router.callback_query(F.data == MENU_ADMIN_CHANNELS)
async def menu_admin_channels(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if not is_admin(callback.from_user.id):
        await callback.message.edit_text("⛔ دسترسی مدیریت نداری.", reply_markup=simple_back_home_markup())
        return
    await state.clear()
    await _show_bot_channels(callback)


@router.callback_query(F.data == MENU_ADMIN_BACKUP)
async def admin_backup_database(callback: CallbackQuery, bot: Bot) -> None:
    await callback.answer()
    if not is_admin(callback.from_user.id):
        await callback.message.edit_text("⛔ دسترسی مدیریت نداری.", reply_markup=simple_back_home_markup())
        return
    try:
        archive_bytes, archive_name = build_database_backup_zip()
    except FileNotFoundError:
        await callback.message.answer("⚠️ فایل دیتابیس پیدا نشد.", reply_markup=admin_panel_markup())
        return
    await bot.send_document(
        callback.from_user.id,
        BufferedInputFile(archive_bytes, filename=archive_name),
        caption="🗜 بکاپ ZIP دیتابیس ربات",
    )
    await callback.message.answer("✅ بکاپ دیتابیس در همین گفت‌وگو ارسال شد.", reply_markup=admin_panel_markup())


@router.callback_query(F.data.startswith(PREFIX_ADMIN_CHANNEL_SET))
async def admin_channel_set(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if not is_admin(callback.from_user.id):
        await callback.message.edit_text("⛔ دسترسی مدیریت نداری.", reply_markup=simple_back_home_markup())
        return
    channel_kind = callback.data[len(PREFIX_ADMIN_CHANNEL_SET):]
    if channel_kind not in {CHANNEL_KIND_CLASS, CHANNEL_KIND_NOTES}:
        await callback.answer("نوع کانال نامعتبر است.", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_channel_id)
    await state.update_data(admin_channel_kind=channel_kind)
    recent_channels = list_recent_channel_ids(channel_kind=channel_kind)
    await callback.message.edit_text(
        f"📣 شناسه کانال {_channel_kind_label(channel_kind)} را انتخاب کن یا دستی وارد کن.",
        reply_markup=admin_channel_picker_markup(channel_kind, recent_channels),
    )


@router.callback_query(F.data.startswith(PREFIX_ADMIN_CHANNEL_PICK))
async def admin_channel_pick(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if not is_admin(callback.from_user.id):
        await callback.message.edit_text("⛔ دسترسی مدیریت نداری.", reply_markup=simple_back_home_markup())
        return
    payload = callback.data[len(PREFIX_ADMIN_CHANNEL_PICK):]
    channel_kind, selected = payload.split(":", 1)
    if selected == "manual":
        await state.set_state(AdminStates.waiting_channel_id)
        await state.update_data(admin_channel_kind=channel_kind)
        await callback.message.edit_text(
            f"📣 شناسه کانال {_channel_kind_label(channel_kind)} را بفرست. مثال: `-1001234567890`",
            reply_markup=cancel_markup(),
        )
        return
    channel_id = _parse_channel_id(selected)
    if channel_id is None:
        await callback.answer("شناسه کانال نامعتبر است.", show_alert=True)
        return
    set_bot_channel(channel_kind, channel_id)
    await state.clear()
    await _show_bot_channels(callback)


@router.message(AdminStates.waiting_channel_id, F.text)
async def admin_channel_submit(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    channel_kind = data.get("admin_channel_kind")
    if channel_kind not in {CHANNEL_KIND_CLASS, CHANNEL_KIND_NOTES}:
        await state.clear()
        await message.answer("⚠️ تنظیم کانال سراسری در دسترس نیست.", reply_markup=admin_panel_markup())
        return
    channel_id = _parse_channel_id(message.text or "")
    if channel_id is None:
        await message.answer("⚠️ شناسه کانال نامعتبر است. نمونه: `-1001234567890`", reply_markup=cancel_markup())
        return
    set_bot_channel(channel_kind, channel_id)
    await state.clear()
    await message.answer(
        f"✅ کانال {_channel_kind_label(channel_kind)} ذخیره شد: {code(channel_id)}\n\n{bot_channels_settings_text(get_bot_channels())}",
        reply_markup=admin_channel_settings_markup(),
    )


@router.callback_query(F.data == MENU_ADMIN_STUDENTS)
async def begin_admin_remove(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await _show_admin_students_page(callback, state, page=1)


@router.callback_query(F.data == MENU_ADMIN_REMOVE)
async def admin_remove_from_list(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await _show_admin_students_page(callback, state, page=1)


@router.callback_query(F.data.startswith(PREFIX_ADMIN_STUDENT_SEARCH))
async def admin_student_search_action(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    action = callback.data[len(PREFIX_ADMIN_STUDENT_SEARCH):]
    current_data = await state.get_data()
    sort_by = current_data.get("admin_student_sort_by") or "approved_at_desc"
    if action == "clear":
        await state.clear()
        await state.update_data(admin_student_sort_by=sort_by)
        await _show_admin_students_page(callback, state, page=1)
        return
    await state.set_state(AdminStates.waiting_student_search)
    await callback.message.answer(
        "🔎 عبارت جستجو را بفرست. نام، شماره دانشجویی، آیدی عددی تلگرام، یوزرنیم و پاسخ‌های فرم‌ها در جستجو پوشش داده می‌شوند.",
        reply_markup=cancel_markup(),
    )


@router.message(AdminStates.waiting_student_search, F.text)
async def admin_student_search_submit(message: Message, state: FSMContext) -> None:
    query = (message.text or "").strip()
    current_data = await state.get_data()
    sort_by = current_data.get("admin_student_sort_by") or "approved_at_desc"
    await state.clear()
    await state.update_data(admin_student_query=query or None, admin_student_sort_by=sort_by)
    text, markup = await _build_admin_students_view(state, page=1)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith(PREFIX_ADMIN_STUDENT_SORT))
async def admin_student_sort_action(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    sort_by = callback.data[len(PREFIX_ADMIN_STUDENT_SORT):]
    current_data = await state.get_data()
    query = current_data.get("admin_student_query")
    await state.clear()
    await state.update_data(admin_student_query=query, admin_student_sort_by=sort_by)
    await _show_admin_students_page(callback, state, page=1)


@router.callback_query(F.data == MENU_ADMIN_REMOVE_DIRECT)
async def admin_remove_direct(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(AdminStates.waiting_remove_student)
    await callback.message.edit_text(
        "🗑 شماره دانشجویی را بفرست تا ثبت فعال همان دانشجو غیرفعال شود.",
        reply_markup=cancel_markup(),
    )


@router.callback_query(F.data.startswith(PREFIX_ADMIN_REMOVE_SELECT))
async def admin_remove_select(callback: CallbackQuery) -> None:
    await callback.answer()
    student_number = callback.data[len(PREFIX_ADMIN_REMOVE_SELECT):]
    registered = get_registered_student_by_student_number(student_number)
    if not registered:
        await callback.answer("ثبت فعالی برای این دانشجو پیدا نشد.", show_alert=True)
        return
    await callback.message.edit_text(
        admin_remove_confirmation_text(registered),
        reply_markup=admin_remove_confirmation_markup(student_number),
    )


@router.callback_query(F.data.startswith(PREFIX_ADMIN_REMOVE_CANCEL))
async def admin_remove_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer("حذف لغو شد.")
    await state.clear()
    await _show_admin_students_page(callback, state, page=1)


@router.callback_query(F.data.startswith(PREFIX_ADMIN_REMOVE_CONFIRM))
async def admin_remove_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    student_number = callback.data[len(PREFIX_ADMIN_REMOVE_CONFIRM):]
    removed = deactivate_student(student_number)
    await state.clear()
    await callback.message.edit_text(
        f"✅ تعداد ثبت فعال غیرفعال‌شده: {code(removed)}",
        reply_markup=admin_panel_markup(),
    )


@router.message(AdminStates.waiting_remove_student, F.text)
async def admin_remove_student(message: Message, state: FSMContext) -> None:
    student_number = normalize_student_number(message.text or "")
    registered = get_registered_student_by_student_number(student_number)
    if not registered:
        await message.answer("ثبت فعالی برای این شماره دانشجویی پیدا نشد.", reply_markup=cancel_markup())
        return
    removed = deactivate_student(student_number)
    await state.clear()
    await message.answer(
        f"✅ تعداد ثبت فعال غیرفعال‌شده: {code(removed)}\n🎓 شماره دانشجویی: {code(student_number)}",
        reply_markup=admin_panel_markup(),
    )


@router.message()
async def plain_text_router(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current:
        return
    await message.answer(
        f"برای استفاده از {e(PROFILE.display_name)} از دکمه‌های اینلاین یا /start استفاده کن.",
        reply_markup=home_markup(message.from_user.id, is_verified_user(message.from_user.id)),
    )
