from __future__ import annotations

import json
from datetime import UTC, datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes, ConversationHandler

from app_callbacks import (
    MENU_REP_FORMS,
    PREFIX_JOIN_FORM_CANCEL,
    PREFIX_JOIN_FORM_CONFIRM,
    PREFIX_REP_FORM_REFRESH,
    PREFIX_REP_FORM_VIEW,
    PREFIX_VERIFY_APPROVE,
    PREFIX_VERIFY_REJECT,
)
from assistant_profile import PROFILE
from config import MAIN_REP_STUDENT_NUMBER
from db import (
    add_rep_form_entry,
    attach_rep_message_refs,
    bulk_upsert_course_grades,
    create_rep_form,
    create_verification_request,
    decide_verification_request,
    deactivate_student,
    find_student,
    get_active_registration_by_student_number,
    get_active_registration_by_tg_id,
    get_pending_request_by_user_id,
    get_rep_form_by_id,
    get_rep_form_entry,
    get_student_grades,
    get_verification_request,
    list_active_registered_users,
    list_pending_verification_requests,
    list_recent_registrations,
    list_rep_form_entries,
    list_rep_forms_by_creator,
    list_students_with_grades,
)
from grade_analytics import build_class_ranking, build_grade_insights, extract_numeric_items
from bot.services.datetime_fa import TEHRAN_TZ, parse_db_datetime, utc_now
from bot.services.formatting import code, e
from bot.services.parsers import parse_grade_list_text, parse_id_from_callback
from bot.services.policies import (
    is_admin,
    is_rep_candidate,
    is_verified_representative,
    is_verified_user,
    normalize_student_number,
    verification_reviewer_ids,
)
from bot.states import (
    WAITING_PROFILE,
    WAITING_REMOVE_STUDENT_NUMBER,
    WAITING_REP_BROADCAST_TEXT,
    WAITING_REP_COURSE_TITLE,
    WAITING_REP_FORM_DEADLINE,
    WAITING_REP_FORM_DESCRIPTION,
    WAITING_REP_FORM_TITLE,
    WAITING_REP_GRADE_LIST,
    WAITING_STUDENT_NUMBER,
)
from bot.ui.keyboards import (
    admin_panel_markup,
    back_home_markup,
    cancel_markup,
    join_form_confirm_markup,
    main_menu_markup,
    rep_form_view_markup,
    rep_forms_menu_markup,
    rep_panel_markup,
    verification_request_markup,
)
from bot.ui.texts import (
    admin_panel_text,
    already_verified_text,
    form_created_text,
    form_join_confirm_text,
    format_rep_form_members,
    grade_report_text,
    pending_requests_text,
    profile_text,
    representative_panel_text,
    verification_approved_student_text,
    verification_intro_text,
    verification_rejected_student_text,
    verification_request_message,
    verification_request_submitted_text,
    welcome_text,
)


async def ensure_verified_for_student_feature(
    update: Update,
    prompt_text: str = "🔐 برای استفاده از این بخش، ابتدا احراز هویت را کامل کن.",
) -> bool:
    user_id = update.effective_user.id
    if is_verified_user(user_id):
        return True

    markup = main_menu_markup(user_id, verified=False)
    if update.callback_query:
        await update.callback_query.edit_message_text(prompt_text, reply_markup=markup)
    elif update.message:
        await update.message.reply_text(prompt_text, reply_markup=markup)
    return False


async def open_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    verified = is_verified_user(user_id)
    text = welcome_text(verified)
    markup = main_menu_markup(user_id, verified=verified)

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(text=text, reply_markup=markup)
        return

    await update.message.reply_text(text=text, reply_markup=markup)


async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await open_main_menu(update, context)
    return ConversationHandler.END


def _parse_form_deadline(raw_text: str) -> str | None:
    if raw_text.strip() in {"ندارد", "-", "skip", "Skip"}:
        return None

    cleaned = (raw_text or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
    for fmt in ("%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M"):
        try:
            tehran_dt = datetime.strptime(cleaned.strip(), fmt).replace(tzinfo=TEHRAN_TZ)
            return tehran_dt.astimezone(UTC).isoformat(timespec="seconds")
        except ValueError:
            continue
    return None


async def _send_verification_requests(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    request_id: int,
) -> None:
    request_row = get_verification_request(request_id)
    if not request_row:
        return

    refs = []
    photo = None
    try:
        photos = await context.bot.get_user_profile_photos(update.effective_user.id, limit=1)
        if photos.photos:
            photo = photos.photos[0][-1].file_id
    except TelegramError:
        photo = None

    for reviewer_id in verification_reviewer_ids():
        try:
            if photo:
                msg = await context.bot.send_photo(
                    chat_id=reviewer_id,
                    photo=photo,
                    caption=verification_request_message(request_row),
                    reply_markup=verification_request_markup(request_id),
                )
            else:
                msg = await context.bot.send_message(
                    chat_id=reviewer_id,
                    text=verification_request_message(request_row),
                    reply_markup=verification_request_markup(request_id),
                )
            refs.append(
                {
                    "chat_id": reviewer_id,
                    "message_id": msg.message_id,
                    "kind": "photo" if photo else "text",
                }
            )
        except TelegramError:
            continue

    if refs:
        attach_rep_message_refs(request_id, refs)


async def _sync_verification_request_messages(request_row) -> None:
    refs_raw = request_row["rep_message_refs_json"] or "[]"
    try:
        refs = json.loads(refs_raw)
    except json.JSONDecodeError:
        refs = []
    if not refs:
        return


async def handle_join_form_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE, form_id: int
) -> int:
    user_id = update.effective_user.id
    form_row = get_rep_form_by_id(form_id)
    if not form_row or form_row["is_active"] != 1:
        await update.message.reply_text(
            "❌ این لینک معتبر نیست یا فرم غیرفعال شده است.",
            reply_markup=main_menu_markup(user_id),
        )
        return ConversationHandler.END

    registration = get_active_registration_by_tg_id(user_id)
    if not registration:
        await update.message.reply_text(
            "🔐 برای عضویت در فرم، اول احراز هویت را کامل کن.",
            reply_markup=main_menu_markup(user_id, verified=False),
        )
        return ConversationHandler.END

    joined = get_rep_form_entry(form_id, user_id)
    if joined:
        await update.message.reply_text(
            "✅ قبلا در این فرم عضو شده‌ای.",
            reply_markup=main_menu_markup(user_id),
        )
        return ConversationHandler.END

    await update.message.reply_text(
        form_join_confirm_text(form_row),
        reply_markup=join_form_confirm_markup(form_id),
    )
    return ConversationHandler.END


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    if context.args:
        payload = (context.args[0] or "").strip()
        if payload.startswith("join_form_"):
            form_id_raw = normalize_student_number(payload.replace("join_form_", "", 1))
            if form_id_raw.isdigit():
                return await handle_join_form_start(update, context, int(form_id_raw))
    await open_main_menu(update, context)
    return ConversationHandler.END


async def menu_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not await ensure_verified_for_student_feature(update):
        return

    registered = get_active_registration_by_tg_id(update.effective_user.id)
    await query.edit_message_text(profile_text(registered), reply_markup=back_home_markup())


async def menu_grades(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not await ensure_verified_for_student_feature(update):
        return

    registered = get_active_registration_by_tg_id(update.effective_user.id)
    grade_row = get_student_grades(registered["student_number"])
    if not grade_row:
        await query.edit_message_text(
            "ℹ️ هنوز نمره‌ای برای حساب شما ثبت نشده است.",
            reply_markup=back_home_markup(),
        )
        return

    grades = json.loads(grade_row["grades_json"])
    grade_items = extract_numeric_items(grades)
    class_ranking = build_class_ranking(list_students_with_grades())
    insights = build_grade_insights(registered["student_number"], grade_items, class_ranking)
    await query.edit_message_text(
        grade_report_text(registered, grades, insights),
        reply_markup=back_home_markup(),
    )


async def menu_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ دسترسی مدیریت نداری.", reply_markup=back_home_markup())
        return

    await query.edit_message_text(
        admin_panel_text(list_recent_registrations()),
        reply_markup=admin_panel_markup(),
    )


async def menu_rep_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if not is_rep_candidate(user_id):
        await query.edit_message_text("⛔ دسترسی نماینده کلاس نداری.", reply_markup=back_home_markup())
        return

    if not is_verified_representative(user_id):
        await query.edit_message_text(
            (
                "⛔ احراز هویت نماینده کامل نشده است.\n"
                f"این حساب باید با شماره دانشجویی {code(MAIN_REP_STUDENT_NUMBER)} تایید شود."
            ),
            reply_markup=back_home_markup(),
        )
        return

    pending_count = len(list_pending_verification_requests())
    await query.edit_message_text(
        representative_panel_text(pending_count),
        reply_markup=rep_panel_markup(),
    )


async def menu_rep_pending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_verified_representative(update.effective_user.id):
        await query.edit_message_text(
            "⛔ فقط نماینده تاییدشده می‌تواند درخواست‌ها را ببیند.",
            reply_markup=back_home_markup(),
        )
        return
    await query.edit_message_text(
        pending_requests_text(list_pending_verification_requests()),
        reply_markup=rep_panel_markup(),
    )


async def menu_rep_forms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_verified_representative(update.effective_user.id):
        await query.edit_message_text(
            "⛔ فقط نماینده تاییدشده به این بخش دسترسی دارد.",
            reply_markup=back_home_markup(),
        )
        return
    await query.edit_message_text(
        "🗂 <b>فرم‌ها و لیست‌های ثبت‌نام</b>\nفرم جدید بساز یا فهرست فرم‌های خودت را ببین.",
        reply_markup=rep_forms_menu_markup(),
    )


async def begin_register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if is_admin(update.effective_user.id) and not is_rep_candidate(update.effective_user.id):
        await query.edit_message_text(
            "🛠 این حساب مدیر است و نیازی به احراز هویت دانشجویی ندارد.",
            reply_markup=main_menu_markup(update.effective_user.id),
        )
        return ConversationHandler.END

    registered = get_active_registration_by_tg_id(update.effective_user.id)
    if registered:
        await query.edit_message_text(
            already_verified_text(registered),
            reply_markup=back_home_markup(),
        )
        return ConversationHandler.END

    pending = get_pending_request_by_user_id(update.effective_user.id)
    if pending:
        await query.edit_message_text(
            verification_request_submitted_text(pending, pending["id"]),
            reply_markup=back_home_markup(),
        )
        return ConversationHandler.END

    await query.edit_message_text(verification_intro_text(), reply_markup=cancel_markup())
    await query.message.reply_text(
        "🎓 <b>شماره دانشجویی</b>\nشماره دانشجویی را دقیقا همان‌طور که در فایل دانشجویان ثبت شده بفرست.",
        reply_markup=cancel_markup(),
    )
    return WAITING_STUDENT_NUMBER


async def receive_student_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    student_number = normalize_student_number(update.message.text or "")
    if not student_number:
        await update.message.reply_text(
            "⚠️ شماره دانشجویی معتبر نیست. دوباره بفرست.",
            reply_markup=cancel_markup(),
        )
        return WAITING_STUDENT_NUMBER

    student = find_student(student_number)
    if not student:
        await update.message.reply_text(
            "❌ این شماره دانشجویی در پایگاه داده پیدا نشد.",
            reply_markup=cancel_markup(),
        )
        return WAITING_STUDENT_NUMBER

    active_reg = get_active_registration_by_student_number(student_number)
    if active_reg and active_reg["telegram_user_id"] != update.effective_user.id:
        await update.message.reply_text(
            "🔒 این شماره دانشجویی روی حساب دیگری فعال است و باید توسط مدیر آزاد شود.",
            reply_markup=back_home_markup(),
        )
        return ConversationHandler.END

    context.user_data["student_number"] = student["student_number"]
    context.user_data["full_name"] = student["full_name"]
    await update.message.reply_text(
        (
            "✅ هویت اولیه پیدا شد.\n"
            f"👤 <b>نام ثبت‌شده:</b> {e(student['full_name'])}\n\n"
            "📝 حالا یک معرفی کوتاه بفرست؛ مثلا نام، گروه یا توضیحی که نماینده با آن راحت‌تر شما را تشخیص دهد."
        ),
        reply_markup=cancel_markup(),
    )
    return WAITING_PROFILE


async def receive_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    profile_value = (update.message.text or "").strip()
    if not profile_value:
        await update.message.reply_text(
            "⚠️ متن معرفی خالی است. دوباره بفرست.",
            reply_markup=cancel_markup(),
        )
        return WAITING_PROFILE

    student_number = context.user_data.get("student_number")
    full_name = context.user_data.get("full_name")
    if not student_number or not full_name:
        await update.message.reply_text(
            "❌ داده‌های احراز هویت کامل نیست. دوباره از منوی اصلی شروع کن.",
            reply_markup=main_menu_markup(update.effective_user.id),
        )
        return ConversationHandler.END

    request_id = create_verification_request(
        telegram_user_id=update.effective_user.id,
        student_number=student_number,
        full_name=full_name,
        username=update.effective_user.username,
        profile_text=profile_value,
    )
    context.user_data.clear()
    await _send_verification_requests(update, context, request_id)
    await update.message.reply_text(
        verification_request_submitted_text(
            {"full_name": full_name, "student_number": student_number},
            request_id,
        ),
        reply_markup=main_menu_markup(update.effective_user.id, verified=False),
    )
    return ConversationHandler.END


async def review_verification_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    reviewer_id = update.effective_user.id
    if not (is_verified_representative(reviewer_id) or is_admin(reviewer_id)):
        await query.answer("دسترسی بررسی درخواست نداری.", show_alert=True)
        return

    data = query.data or ""
    approve = data.startswith(PREFIX_VERIFY_APPROVE)
    prefix = PREFIX_VERIFY_APPROVE if approve else PREFIX_VERIFY_REJECT
    request_id = parse_id_from_callback(data, prefix)
    if request_id is None:
        await query.answer("شناسه درخواست نامعتبر است.", show_alert=True)
        return

    request_row, result = decide_verification_request(
        request_id=request_id,
        reviewer_tg_id=reviewer_id,
        approve=approve,
        reviewer_note=None if approve else "درخواست توسط نماینده رد شد.",
    )
    if request_row is None:
        await query.edit_message_reply_markup(reply_markup=None)
        return

    await query.edit_message_reply_markup(reply_markup=None)
    if result in {"already_reviewed", "student_number_already_linked"}:
        await query.answer("این درخواست قبلا نهایی شده است.", show_alert=True)
    else:
        await query.answer("درخواست ثبت شد.")

    student_markup = main_menu_markup(request_row["telegram_user_id"], verified=approve)
    try:
        if approve:
            await context.bot.send_message(
                chat_id=request_row["telegram_user_id"],
                text=verification_approved_student_text(request_row),
                reply_markup=student_markup,
            )
        else:
            await context.bot.send_message(
                chat_id=request_row["telegram_user_id"],
                text=verification_rejected_student_text(request_row),
                reply_markup=student_markup,
            )
    except TelegramError:
        pass


async def begin_remove_student(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ دسترسی مدیریت نداری.", reply_markup=back_home_markup())
        return ConversationHandler.END

    await query.edit_message_text(
        admin_panel_text(list_recent_registrations())
        + "\n\n🗑 <b>حذف ثبت فعال</b>\nشماره دانشجویی را بفرست تا ثبت فعال همان دانشجو غیرفعال شود.",
        reply_markup=cancel_markup(),
    )
    return WAITING_REMOVE_STUDENT_NUMBER


async def receive_remove_student_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "⛔ دسترسی مدیریت نداری.",
            reply_markup=main_menu_markup(update.effective_user.id),
        )
        return ConversationHandler.END

    student_number = normalize_student_number(update.message.text or "")
    if not student_number:
        await update.message.reply_text(
            "⚠️ شماره دانشجویی نامعتبر است.",
            reply_markup=cancel_markup(),
        )
        return WAITING_REMOVE_STUDENT_NUMBER

    deactivated = deactivate_student(student_number)
    if deactivated == 0:
        await update.message.reply_text(
            f"ℹ️ ثبت فعالی برای {code(student_number)} پیدا نشد.",
            reply_markup=admin_panel_markup(),
        )
    else:
        await update.message.reply_text(
            f"✅ ثبت فعال دانشجو با شماره {code(student_number)} غیرفعال شد.",
            reply_markup=admin_panel_markup(),
        )
    return ConversationHandler.END


async def begin_rep_import_grades(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not is_verified_representative(update.effective_user.id):
        await query.edit_message_text(
            "⛔ فقط نماینده تاییدشده کلاس به این بخش دسترسی دارد.",
            reply_markup=back_home_markup(),
        )
        return ConversationHandler.END

    await query.edit_message_text(
        "🧾 <b>ثبت گروهی نمره</b>\nنام درس یا ارزیابی را بفرست.",
        reply_markup=cancel_markup(),
    )
    return WAITING_REP_COURSE_TITLE


async def receive_rep_course_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_verified_representative(update.effective_user.id):
        await update.message.reply_text(
            "⛔ دسترسی نماینده تاییدشده لازم است.",
            reply_markup=main_menu_markup(update.effective_user.id),
        )
        return ConversationHandler.END

    course_title = (update.message.text or "").strip()
    if not course_title:
        await update.message.reply_text(
            "⚠️ نام درس خالی است.",
            reply_markup=cancel_markup(),
        )
        return WAITING_REP_COURSE_TITLE

    context.user_data["rep_course_title"] = course_title
    await update.message.reply_text(
        (
            "✅ عنوان ثبت شد.\n"
            "حالا لیست نمره‌ها را خط‌به‌خط با قالب زیر بفرست:\n"
            f"{code('40111270001, 18.5')}\n"
            f"{code('40111270002, 17')}"
        ),
        reply_markup=cancel_markup(),
    )
    return WAITING_REP_GRADE_LIST


async def receive_rep_grade_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_verified_representative(update.effective_user.id):
        await update.message.reply_text(
            "⛔ دسترسی نماینده تاییدشده لازم است.",
            reply_markup=main_menu_markup(update.effective_user.id),
        )
        return ConversationHandler.END

    course_title = context.user_data.get("rep_course_title")
    if not course_title:
        await update.message.reply_text(
            "❌ عنوان درس پیدا نشد. دوباره از پنل نماینده شروع کن.",
            reply_markup=rep_panel_markup(),
        )
        return ConversationHandler.END

    grade_entries, invalid_lines = parse_grade_list_text(update.message.text or "")
    if not grade_entries:
        await update.message.reply_text(
            "⚠️ هیچ ردیف معتبری پیدا نشد. قالب را چک کن و دوباره بفرست.",
            reply_markup=cancel_markup(),
        )
        return WAITING_REP_GRADE_LIST

    result = bulk_upsert_course_grades(course_title, grade_entries)
    missing_students = result["missing_students"]
    updated_count = result["updated_count"]
    lines = [
        "✅ <b>ثبت نمره‌ها انجام شد.</b>",
        f"📚 <b>عنوان:</b> {e(course_title)}",
        f"• ردیف‌های معتبر: {code(len(grade_entries))}",
        f"• ثبت یا بروزرسانی موفق: {code(updated_count)}",
        f"• شماره‌های ناموجود: {code(len(missing_students))}",
        f"• ردیف‌های نامعتبر: {code(len(invalid_lines))}",
    ]
    if missing_students:
        lines.append("")
        lines.append("<b>چند شماره ناموجود</b>")
        lines.extend(f"• {code(item)}" for item in missing_students[:10])
    if invalid_lines:
        lines.append("")
        lines.append("<b>چند ردیف نامعتبر</b>")
        lines.extend(f"• {e(item)}" for item in invalid_lines[:10])

    context.user_data.pop("rep_course_title", None)
    await update.message.reply_text("\n".join(lines), reply_markup=rep_panel_markup())
    return ConversationHandler.END


async def begin_rep_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not is_verified_representative(update.effective_user.id):
        await query.edit_message_text(
            "⛔ فقط نماینده تاییدشده به این بخش دسترسی دارد.",
            reply_markup=back_home_markup(),
        )
        return ConversationHandler.END

    await query.edit_message_text(
        "📣 <b>اطلاعیه همگانی</b>\nمتن اطلاعیه را بفرست تا برای دانشجوهای تاییدشده ارسال شود.",
        reply_markup=cancel_markup(),
    )
    return WAITING_REP_BROADCAST_TEXT


async def receive_rep_broadcast_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_verified_representative(update.effective_user.id):
        await update.message.reply_text(
            "⛔ دسترسی نماینده تاییدشده لازم است.",
            reply_markup=main_menu_markup(update.effective_user.id),
        )
        return ConversationHandler.END

    announcement = (update.message.text or "").strip()
    if not announcement:
        await update.message.reply_text(
            "⚠️ متن اطلاعیه خالی است.",
            reply_markup=cancel_markup(),
        )
        return WAITING_REP_BROADCAST_TEXT

    recipients = list_active_registered_users()
    payload = "📣 <b>اطلاعیه کلاس</b>\n\n" + e(announcement)
    success_count = 0
    failed_count = 0
    for user in recipients:
        try:
            await context.bot.send_message(chat_id=user["telegram_user_id"], text=payload)
            success_count += 1
        except TelegramError:
            failed_count += 1

    await update.message.reply_text(
        (
            "✅ <b>ارسال اطلاعیه انجام شد.</b>\n"
            f"• گیرنده‌ها: {code(len(recipients))}\n"
            f"• ارسال موفق: {code(success_count)}\n"
            f"• ارسال ناموفق: {code(failed_count)}"
        ),
        reply_markup=rep_panel_markup(),
    )
    return ConversationHandler.END


async def begin_rep_form_create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not is_verified_representative(update.effective_user.id):
        await query.edit_message_text(
            "⛔ فقط نماینده تاییدشده به این بخش دسترسی دارد.",
            reply_markup=back_home_markup(),
        )
        return ConversationHandler.END

    context.user_data.pop("new_form", None)
    await query.edit_message_text(
        "➕ <b>ساخت فرم جدید</b>\nعنوان فرم را بفرست.",
        reply_markup=cancel_markup(),
    )
    return WAITING_REP_FORM_TITLE


async def receive_rep_form_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    title = (update.message.text or "").strip()
    if not title:
        await update.message.reply_text("⚠️ عنوان فرم خالی است.", reply_markup=cancel_markup())
        return WAITING_REP_FORM_TITLE
    context.user_data["new_form"] = {"title": title}
    await update.message.reply_text(
        "📝 توضیح کوتاه فرم را بفرست. اگر توضیحی نداری، فقط بنویس «ندارد».",
        reply_markup=cancel_markup(),
    )
    return WAITING_REP_FORM_DESCRIPTION


async def receive_rep_form_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    description = (update.message.text or "").strip() or "ندارد"
    new_form = context.user_data.get("new_form")
    if not new_form:
        await update.message.reply_text("❌ روند ساخت فرم پیدا نشد.", reply_markup=rep_forms_menu_markup())
        return ConversationHandler.END
    new_form["description"] = "" if description == "ندارد" else description
    await update.message.reply_text(
        "⏰ مهلت فرم را با قالب <code>2026/04/30 18:30</code> بفرست. اگر مهلت ندارد، «ندارد» را بفرست.",
        reply_markup=cancel_markup(),
    )
    return WAITING_REP_FORM_DEADLINE


async def receive_rep_form_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    new_form = context.user_data.get("new_form")
    if not new_form:
        await update.message.reply_text("❌ روند ساخت فرم پیدا نشد.", reply_markup=rep_forms_menu_markup())
        return ConversationHandler.END

    deadline_at = _parse_form_deadline(update.message.text or "")
    raw_value = (update.message.text or "").strip()
    if raw_value not in {"ندارد", "-", "skip", "Skip"} and deadline_at is None:
        await update.message.reply_text(
            "⚠️ زمان معتبر نیست. قالب پیشنهادی: <code>2026/04/30 18:30</code>",
            reply_markup=cancel_markup(),
        )
        return WAITING_REP_FORM_DEADLINE

    rep_registration = get_active_registration_by_tg_id(update.effective_user.id)
    if not rep_registration:
        await update.message.reply_text(
            "❌ احراز هویت نماینده پیدا نشد. دوباره از منوی اصلی شروع کن.",
            reply_markup=main_menu_markup(update.effective_user.id),
        )
        return ConversationHandler.END

    form_id = create_rep_form(
        title=new_form["title"],
        description=new_form.get("description", ""),
        deadline_at=deadline_at,
        created_by_tg_id=update.effective_user.id,
        created_by_student_number=rep_registration["student_number"],
    )
    bot_info = await context.bot.get_me()
    join_url = f"https://t.me/{bot_info.username}?start=join_form_{form_id}"
    context.user_data.pop("new_form", None)

    await update.message.reply_text(
        form_created_text(new_form["title"], new_form.get("description", ""), form_id, join_url, deadline_at),
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🔗 باز کردن لینک عضویت", url=join_url)],
                [InlineKeyboardButton("📚 مشاهده اعضا", callback_data=f"{PREFIX_REP_FORM_VIEW}{form_id}")],
                [InlineKeyboardButton("🗂 فرم‌ها و لیست‌ها", callback_data=MENU_REP_FORMS)],
            ]
        ),
    )
    return ConversationHandler.END


async def menu_rep_form_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not is_verified_representative(user_id):
        await query.edit_message_text(
            "⛔ فقط نماینده تاییدشده به این بخش دسترسی دارد.",
            reply_markup=back_home_markup(),
        )
        return

    forms = list_rep_forms_by_creator(user_id)
    if not forms:
        await query.edit_message_text(
            "ℹ️ هنوز فرمی نساخته‌ای.",
            reply_markup=rep_forms_menu_markup(),
        )
        return

    rows = [
        [InlineKeyboardButton(f"🗂 {form['title']}", callback_data=f"{PREFIX_REP_FORM_VIEW}{form['id']}")]
        for form in forms[:20]
    ]
    rows.append([InlineKeyboardButton("↩️ بازگشت", callback_data=MENU_REP_FORMS)])
    await query.edit_message_text(
        "📚 <b>فرم‌های ساخته‌شده</b>\nیکی از فرم‌ها را برای مشاهده اعضا انتخاب کن.",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def show_rep_form_members(
    update: Update, context: ContextTypes.DEFAULT_TYPE, form_id: int
) -> None:
    query = update.callback_query
    form_row = get_rep_form_by_id(form_id)
    if not form_row:
        await query.edit_message_text("❌ فرم پیدا نشد.", reply_markup=rep_forms_menu_markup())
        return
    if form_row["created_by_tg_id"] != update.effective_user.id:
        await query.edit_message_text("⛔ این فرم متعلق به شما نیست.", reply_markup=rep_forms_menu_markup())
        return

    entries = list_rep_form_entries(form_id)
    await query.edit_message_text(
        format_rep_form_members(form_row, entries),
        reply_markup=rep_form_view_markup(form_id),
    )


async def menu_rep_form_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    form_id = parse_id_from_callback(query.data or "", PREFIX_REP_FORM_VIEW)
    if form_id is None:
        await query.edit_message_text("❌ شناسه فرم نامعتبر است.", reply_markup=rep_forms_menu_markup())
        return
    await show_rep_form_members(update, context, form_id)


async def menu_rep_form_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    form_id = parse_id_from_callback(query.data or "", PREFIX_REP_FORM_REFRESH)
    if form_id is None:
        await query.edit_message_text("❌ شناسه فرم نامعتبر است.", reply_markup=rep_forms_menu_markup())
        return
    await show_rep_form_members(update, context, form_id)


async def join_form_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    form_id = parse_id_from_callback(query.data or "", PREFIX_JOIN_FORM_CONFIRM)
    if form_id is None:
        await query.edit_message_text("❌ درخواست نامعتبر است.", reply_markup=main_menu_markup(user_id))
        return

    form_row = get_rep_form_by_id(form_id)
    if not form_row or form_row["is_active"] != 1:
        await query.edit_message_text(
            "❌ این فرم معتبر نیست یا غیرفعال شده است.",
            reply_markup=main_menu_markup(user_id),
        )
        return

    if form_row["deadline_at"]:
        deadline = parse_db_datetime(form_row["deadline_at"])
        if deadline and deadline <= utc_now():
            await query.edit_message_text(
                "⛔ مهلت این فرم به پایان رسیده است.",
                reply_markup=main_menu_markup(user_id),
            )
            return

    registration = get_active_registration_by_tg_id(user_id)
    if not registration:
        await query.edit_message_text(
            "🔐 ابتدا احراز هویت را کامل کن.",
            reply_markup=main_menu_markup(user_id, verified=False),
        )
        return

    result = add_rep_form_entry(
        form_id=form_id,
        telegram_user_id=user_id,
        student_number=registration["student_number"],
        full_name=registration["full_name"],
        username=registration["username"],
    )
    if result == "already_joined":
        text = "✅ قبلا در این فرم عضو شده‌ای."
    elif result == "closed":
        text = "⛔ این فرم بسته شده است."
    else:
        text = (
            "✅ عضویت ثبت شد.\n"
            f"🗂 <b>فرم:</b> {e(form_row['title'])}\n"
            f"🎓 <b>شماره دانشجویی:</b> {code(registration['student_number'])}"
        )
    await query.edit_message_text(text, reply_markup=main_menu_markup(user_id))


async def join_form_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    form_id = parse_id_from_callback(query.data or "", PREFIX_JOIN_FORM_CANCEL)
    suffix = f" برای فرم {code(form_id)}" if form_id is not None else ""
    await query.edit_message_text(
        f"❌ عضویت{suffix} لغو شد.",
        reply_markup=main_menu_markup(update.effective_user.id),
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "❌ عملیات لغو شد.",
            reply_markup=main_menu_markup(update.effective_user.id),
        )
    else:
        await update.message.reply_text(
            "❌ عملیات لغو شد.",
            reply_markup=main_menu_markup(update.effective_user.id),
        )
    return ConversationHandler.END


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"❓ این دستور شناخته نشد. برای ورود به {e(PROFILE.display_name)} از /start استفاده کن.",
        reply_markup=main_menu_markup(update.effective_user.id),
    )


async def plain_text_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if is_verified_user(user_id):
        text = "👆 برای ادامه از دکمه‌های منوی اصلی استفاده کن."
    else:
        text = "🔐 ابتدا از دکمه احراز هویت شروع کن تا بقیه امکانات فعال شود."
    await update.message.reply_text(text, reply_markup=main_menu_markup(user_id))
