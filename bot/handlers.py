import json

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes, ConversationHandler

from app_callbacks import (
    MENU_REP_FORMS,
    PREFIX_JOIN_FORM_CANCEL,
    PREFIX_JOIN_FORM_CONFIRM,
    PREFIX_REP_FORM_REFRESH,
    PREFIX_REP_FORM_VIEW,
)
from assistant_profile import PROFILE
from config import MAIN_REP_STUDENT_NUMBER
from db import (
    add_rep_form_entry,
    bulk_upsert_course_grades,
    create_rep_form,
    deactivate_student,
    find_student,
    get_active_registration_by_student_number,
    get_active_registration_by_tg_id,
    get_rep_form_by_id,
    get_rep_form_entry,
    get_student_grades,
    list_active_registered_users,
    list_rep_form_entries,
    list_rep_forms_by_creator,
    list_students_with_grades,
    upsert_registration,
)
from grade_analytics import (
    build_class_ranking,
    build_grade_insights,
    extract_numeric_items,
)
from bot.services.localization import fa
from bot.services.parsers import parse_grade_list_text, parse_id_from_callback
from bot.services.policies import (
    is_admin,
    is_rep_candidate,
    is_verified_representative,
    is_verified_user,
    normalize_student_number,
)
from bot.states import (
    WAITING_PROFILE,
    WAITING_REMOVE_STUDENT_NUMBER,
    WAITING_REP_BROADCAST_TEXT,
    WAITING_REP_COURSE_TITLE,
    WAITING_REP_FORM_TITLE,
    WAITING_REP_GRADE_LIST,
    WAITING_STUDENT_NUMBER,
)
from bot.ui.keyboards import (
    back_home_markup,
    cancel_markup,
    join_form_confirm_markup,
    main_menu_markup,
    rep_form_view_markup,
    rep_forms_menu_markup,
    rep_panel_markup,
)
from bot.ui.texts import (
    admin_help_text,
    format_rep_form_members,
    help_text,
    profile_text,
    representative_help_text,
    welcome_text,
)


async def ensure_verified_for_student_feature(
    update: Update,
    prompt_text: str = "🔐 برای استفاده از این بخش، ابتدا احراز هویت را انجام بده.",
) -> bool:
    user_id = update.effective_user.id
    if is_verified_user(user_id):
        return True

    if update.callback_query:
        query = update.callback_query
        await query.edit_message_text(
            text=fa(prompt_text),
            reply_markup=main_menu_markup(user_id, verified=False),
        )
    elif update.message:
        await update.message.reply_text(
            text=fa(prompt_text),
            reply_markup=main_menu_markup(user_id, verified=False),
        )
    return False


async def open_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    verified = is_verified_user(user_id)
    text = fa(welcome_text(verified))
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


async def handle_join_form_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE, form_id: int
) -> int:
    user_id = update.effective_user.id
    form_row = get_rep_form_by_id(form_id)
    if not form_row or form_row["is_active"] != 1:
        await update.message.reply_text(
            fa("❌ این لینک معتبر نیست یا لیست غیرفعال شده است."),
            reply_markup=main_menu_markup(user_id),
        )
        return ConversationHandler.END

    registration = get_active_registration_by_tg_id(user_id)
    if not registration:
        await update.message.reply_text(
            fa(
                "ℹ️ برای عضویت در لیست، اول باید احراز هویت کرده باشی.\n"
                "از منو روی «🔐 احراز هویت» بزن."
            ),
            reply_markup=main_menu_markup(user_id),
        )
        return ConversationHandler.END

    joined = get_rep_form_entry(form_id, user_id)
    if joined:
        await update.message.reply_text(
            fa(
                "✅ شما قبلا در این لیست عضو شده‌اید.\n"
                f"🗳️ نام لیست: {form_row['title']}"
            ),
            reply_markup=main_menu_markup(user_id),
        )
        return ConversationHandler.END

    await update.message.reply_text(
        fa(
            f"🗳️ لیست: {form_row['title']}\n\n"
            "آیا تایید می‌کنی که وارد این لیست شوی؟"
        ),
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


async def menu_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    await query.edit_message_text(
        text=fa(help_text(is_admin(user_id), is_rep_candidate(user_id), is_verified_user(user_id))),
        reply_markup=back_home_markup(),
    )


async def menu_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not await ensure_verified_for_student_feature(update):
        return

    registered = get_active_registration_by_tg_id(update.effective_user.id)
    if not registered:
        await query.edit_message_text(
            text=fa("ℹ️ هنوز احراز هویت نشده‌ای. از منو روی «🔐 احراز هویت» بزن."),
            reply_markup=back_home_markup(),
        )
        return

    await query.edit_message_text(
        text=fa(profile_text(registered)),
        reply_markup=back_home_markup(),
    )


async def menu_admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        await query.edit_message_text(
            text=fa("⛔ دسترسی ادمین نداری."), reply_markup=back_home_markup()
        )
        return

    await query.edit_message_text(
        text=fa(admin_help_text()),
        reply_markup=back_home_markup(),
    )


async def menu_rep_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if not is_rep_candidate(user_id):
        await query.edit_message_text(
            text=fa("⛔ دسترسی نماینده کلاس نداری."),
            reply_markup=back_home_markup(),
        )
        return

    if not is_verified_representative(user_id):
        await query.edit_message_text(
            text=fa(
                "⛔ احراز هویت نماینده کامل نیست.\n"
                "ابتدا با شماره دانشجویی نماینده اصلی احراز هویت کن:\n"
                f"{MAIN_REP_STUDENT_NUMBER}"
            ),
            reply_markup=back_home_markup(),
        )
        return

    await query.edit_message_text(
        text=fa(
            "🎓 پنل نماینده کلاس\n"
            "از گزینه‌های زیر استفاده کن:"
        ),
        reply_markup=rep_panel_markup(),
    )


async def menu_rep_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_rep_candidate(update.effective_user.id):
        await query.edit_message_text(
            text=fa("⛔ دسترسی نماینده کلاس نداری."),
            reply_markup=back_home_markup(),
        )
        return

    await query.edit_message_text(
        text=fa(representative_help_text()),
        reply_markup=rep_panel_markup(),
    )


async def menu_rep_forms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_verified_representative(update.effective_user.id):
        await query.edit_message_text(
            text=fa("⛔ فقط نماینده تایید‌شده کلاس به این بخش دسترسی دارد."),
            reply_markup=back_home_markup(),
        )
        return
    await query.edit_message_text(
        text=fa("🗳️ ماژول فرم/لیست تلگرامی\nیکی از گزینه‌ها را انتخاب کن:"),
        reply_markup=rep_forms_menu_markup(),
    )


async def begin_rep_form_create(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    if not is_verified_representative(update.effective_user.id):
        await query.edit_message_text(
            text=fa("⛔ فقط نماینده تایید‌شده کلاس به این بخش دسترسی دارد."),
            reply_markup=back_home_markup(),
        )
        return ConversationHandler.END

    await query.edit_message_text(
        text=fa("✍️ عنوان لیست جدید را ارسال کن.\nمثال: متقاضیان کلاس ترمیم ۲"),
        reply_markup=cancel_markup(),
    )
    return WAITING_REP_FORM_TITLE


async def receive_rep_form_title(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    user_id = update.effective_user.id
    if not is_verified_representative(user_id):
        await update.message.reply_text(
            fa("⛔ فقط نماینده تایید‌شده کلاس به این بخش دسترسی دارد."),
            reply_markup=main_menu_markup(user_id),
        )
        return ConversationHandler.END

    title = (update.message.text or "").strip()
    if not title:
        await update.message.reply_text(
            fa("⚠️ عنوان لیست خالی است. دوباره ارسال کن."),
            reply_markup=cancel_markup(),
        )
        return WAITING_REP_FORM_TITLE

    rep_registration = get_active_registration_by_tg_id(user_id)
    if not rep_registration:
        await update.message.reply_text(
            fa("❌ احراز هویت نماینده پیدا نشد. ابتدا دوباره احراز هویت کن."),
            reply_markup=main_menu_markup(user_id),
        )
        return ConversationHandler.END

    form_id = create_rep_form(
        title=title,
        created_by_tg_id=user_id,
        created_by_student_number=rep_registration["student_number"],
    )

    bot_info = await context.bot.get_me()
    join_url = f"https://t.me/{bot_info.username}?start=join_form_{form_id}"

    await update.message.reply_text(
        fa(
            "✅ لیست جدید ساخته شد.\n"
            f"🗳️ عنوان: {title}\n"
            f"🆔 شناسه لیست: {form_id}\n\n"
            "لینک عضویت را برای دانشجوها ارسال کن:"
        ),
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🔗 لینک عضویت", url=join_url)],
                [
                    InlineKeyboardButton(
                        "📋 مشاهده اعضا",
                        callback_data=f"{PREFIX_REP_FORM_VIEW}{form_id}",
                    )
                ],
                [InlineKeyboardButton("🗳️ فرم/لیست‌ها", callback_data=MENU_REP_FORMS)],
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
            text=fa("⛔ فقط نماینده تایید‌شده کلاس به این بخش دسترسی دارد."),
            reply_markup=back_home_markup(),
        )
        return

    forms = list_rep_forms_by_creator(user_id)
    if not forms:
        await query.edit_message_text(
            text=fa("ℹ️ هنوز لیستی نساخته‌ای."),
            reply_markup=rep_forms_menu_markup(),
        )
        return

    rows = []
    for form in forms[:20]:
        rows.append(
            [
                InlineKeyboardButton(
                    fa(f"🗳️ {form['title']}"),
                    callback_data=f"{PREFIX_REP_FORM_VIEW}{form['id']}",
                )
            ]
        )
    rows.append([InlineKeyboardButton("🗳️ بازگشت", callback_data=MENU_REP_FORMS)])

    await query.edit_message_text(
        text=fa("📂 لیست‌های ساخته‌شده توسط شما:"),
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def show_rep_form_members(
    update: Update, context: ContextTypes.DEFAULT_TYPE, form_id: int
) -> None:
    query = update.callback_query
    form_row = get_rep_form_by_id(form_id)
    if not form_row:
        await query.edit_message_text(
            text=fa("❌ لیست موردنظر پیدا نشد."),
            reply_markup=rep_forms_menu_markup(),
        )
        return

    if form_row["created_by_tg_id"] != update.effective_user.id:
        await query.edit_message_text(
            text=fa("⛔ این لیست متعلق به شما نیست."),
            reply_markup=rep_forms_menu_markup(),
        )
        return

    entries = list_rep_form_entries(form_id)
    text = fa(format_rep_form_members(form_row, entries))
    await query.edit_message_text(
        text=text,
        reply_markup=rep_form_view_markup(form_id),
    )


async def menu_rep_form_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_verified_representative(update.effective_user.id):
        await query.edit_message_text(
            text=fa("⛔ فقط نماینده تایید‌شده کلاس به این بخش دسترسی دارد."),
            reply_markup=back_home_markup(),
        )
        return

    form_id = parse_id_from_callback(query.data or "", PREFIX_REP_FORM_VIEW)
    if form_id is None:
        await query.edit_message_text(
            text=fa("❌ شناسه لیست نامعتبر است."),
            reply_markup=rep_forms_menu_markup(),
        )
        return
    await show_rep_form_members(update, context, form_id)


async def menu_rep_form_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_verified_representative(update.effective_user.id):
        await query.edit_message_text(
            text=fa("⛔ فقط نماینده تایید‌شده کلاس به این بخش دسترسی دارد."),
            reply_markup=back_home_markup(),
        )
        return

    form_id = parse_id_from_callback(query.data or "", PREFIX_REP_FORM_REFRESH)
    if form_id is None:
        await query.edit_message_text(
            text=fa("❌ شناسه لیست نامعتبر است."),
            reply_markup=rep_forms_menu_markup(),
        )
        return
    await show_rep_form_members(update, context, form_id)


async def join_form_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    form_id = parse_id_from_callback(query.data or "", PREFIX_JOIN_FORM_CONFIRM)
    if form_id is None:
        await query.edit_message_text(
            text=fa("❌ درخواست نامعتبر است."),
            reply_markup=main_menu_markup(user_id),
        )
        return

    form_row = get_rep_form_by_id(form_id)
    if not form_row or form_row["is_active"] != 1:
        await query.edit_message_text(
            text=fa("❌ این لیست معتبر نیست یا غیرفعال شده است."),
            reply_markup=main_menu_markup(user_id),
        )
        return

    registration = get_active_registration_by_tg_id(user_id)
    if not registration:
        await query.edit_message_text(
            text=fa("ℹ️ ابتدا باید در ربات احراز هویت کرده باشی."),
            reply_markup=main_menu_markup(user_id),
        )
        return

    status = add_rep_form_entry(
        form_id=form_id,
        telegram_user_id=user_id,
        student_number=registration["student_number"],
        full_name=registration["full_name"],
    )
    if status == "joined":
        text = (
            "✅ عضویت شما ثبت شد.\n"
            f"🗳️ لیست: {form_row['title']}\n"
            f"🎓 شماره دانشجویی: {registration['student_number']}\n"
            f"🧑‍🎓 نام: {registration['full_name']}"
        )
    elif status == "already_joined":
        text = (
            "ℹ️ شما قبلا در این لیست عضو شده‌ای.\n"
            f"🗳️ لیست: {form_row['title']}"
        )
    else:
        text = "❌ این لیست دیگر فعال نیست."

    await query.edit_message_text(
        text=fa(text),
        reply_markup=main_menu_markup(user_id),
    )


async def join_form_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    form_id = parse_id_from_callback(query.data or "", PREFIX_JOIN_FORM_CANCEL)
    form_name = ""
    if form_id is not None:
        form_row = get_rep_form_by_id(form_id)
        if form_row:
            form_name = f"\n🗳️ لیست: {form_row['title']}"

    await query.edit_message_text(
        text=fa("🛑 عضویت در لیست لغو شد." + form_name),
        reply_markup=main_menu_markup(user_id),
    )


async def menu_grades(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not await ensure_verified_for_student_feature(update):
        return

    registered = get_active_registration_by_tg_id(update.effective_user.id)
    if not registered:
        await query.edit_message_text(
            text=fa("ℹ️ برای دیدن نمرات، اول باید احراز هویت انجام بدهی."),
            reply_markup=back_home_markup(),
        )
        return

    grade_row = get_student_grades(registered["student_number"])
    if not grade_row:
        await query.edit_message_text(
            text=fa("ℹ️ هنوز نمره‌ای برای این شماره دانشجویی ثبت نشده است."),
            reply_markup=back_home_markup(),
        )
        return

    try:
        grades = json.loads(grade_row["grades_json"])
    except json.JSONDecodeError:
        grades = {}

    if not grades:
        await query.edit_message_text(
            text=fa("ℹ️ اطلاعات نمرات موجود است ولی مقدار قابل‌نمایش ندارد."),
            reply_markup=back_home_markup(),
        )
        return

    numeric_items = extract_numeric_items(grades)
    ranking = build_class_ranking(list_students_with_grades())
    insights = build_grade_insights(
        student_number=registered["student_number"],
        grade_items=numeric_items,
        class_ranking=ranking,
    )
    personal_avg_text = (
        f"{insights.personal_average:.2f}"
        if insights.personal_average is not None
        else "ناموجود"
    )

    rank_text = (
        f"{insights.rank_position} از {insights.rank_total}"
        if insights.rank_position is not None
        else "ناموجود"
    )
    class_avg_text = (
        f"{insights.class_average:.2f}"
        if insights.class_average is not None
        else "ناموجود"
    )
    delta_text = (
        f"{insights.delta_from_class_average:+.2f}"
        if insights.delta_from_class_average is not None
        else "ناموجود"
    )
    top_text = (
        f"{insights.top_student_name} ({insights.top_student_average:.2f})"
        if insights.top_student_name and insights.top_student_average is not None
        else "ناموجود"
    )

    grade_lines = [f"• {key}: {value}" for key, value in grades.items()]
    message = (
        "📊 نمرات شما:\n"
        f"🎓 شماره دانشجویی: {registered['student_number']}\n"
        f"🧑‍🎓 نام: {registered['full_name']}\n\n"
        + "\n".join(grade_lines)
        + "\n\n📈 تحلیل عملکرد:\n"
        f"• میانگین شما: {personal_avg_text}\n"
        f"• رتبه در کلاس: {rank_text}\n"
        f"• میانگین کلاس: {class_avg_text}\n"
        f"• اختلاف با میانگین کلاس: {delta_text}\n"
        f"• نفر اول کلاس: {top_text}"
    )
    await query.edit_message_text(text=fa(message), reply_markup=back_home_markup())


async def begin_register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if is_admin(update.effective_user.id) and not is_rep_candidate(update.effective_user.id):
        await query.edit_message_text(
            text=fa(
                "🛠️ شما به عنوان ادمین شناسایی شدی.\n"
                "برای دسترسی مدیریتی نیاز به احراز هویت دانشجویی نداری."
            ),
            reply_markup=main_menu_markup(update.effective_user.id),
        )
        return ConversationHandler.END

    registered = get_active_registration_by_tg_id(update.effective_user.id)
    if registered:
        await query.edit_message_text(
            text=fa(
                "✅ قبلا احراز هویت شده‌ای.\n"
                f"🎓 شماره دانشجویی: {registered['student_number']}\n"
                f"🧑‍🎓 نام: {registered['full_name']}"
            ),
            reply_markup=back_home_markup(),
        )
        return ConversationHandler.END

    await query.edit_message_text(
        text=fa("🔢 شماره دانشجویی خودت رو برای احراز هویت ارسال کن."),
        reply_markup=cancel_markup(),
    )
    return WAITING_STUDENT_NUMBER


async def receive_student_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    student_number = normalize_student_number(update.message.text or "")
    if not student_number:
        await update.message.reply_text(
            fa("⚠️ شماره دانشجویی معتبر نیست. دوباره ارسال کن."),
            reply_markup=cancel_markup(),
        )
        return WAITING_STUDENT_NUMBER

    student = find_student(student_number)
    if not student:
        await update.message.reply_text(
            fa("❌ این شماره دانشجویی در دیتابیس نیست. دوباره تلاش کن."),
            reply_markup=cancel_markup(),
        )
        return WAITING_STUDENT_NUMBER

    active_reg = get_active_registration_by_student_number(student_number)
    if active_reg and active_reg["telegram_user_id"] != update.effective_user.id:
        await update.message.reply_text(
            fa("🔒 این شماره دانشجویی روی اکانت دیگری ثبت شده و باید توسط ادمین حذف شود."),
            reply_markup=back_home_markup(),
        )
        return ConversationHandler.END

    context.user_data["student_number"] = student["student_number"]
    context.user_data["full_name"] = student["full_name"]

    await update.message.reply_text(
        fa(
            f"✅ {student['full_name']} تایید شد.\n"
            "📝 حالا مشخصات تکمیلی‌ات را ارسال کن."
        ),
        reply_markup=cancel_markup(),
    )
    return WAITING_PROFILE


async def receive_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    profile_text = (update.message.text or "").strip()
    if not profile_text:
        await update.message.reply_text(
            fa("⚠️ مشخصات خالی است. دوباره ارسال کن."),
            reply_markup=cancel_markup(),
        )
        return WAITING_PROFILE

    student_number = context.user_data.get("student_number")
    full_name = context.user_data.get("full_name")
    if not student_number or not full_name:
        await update.message.reply_text(
            fa("❌ خطا در فرآیند احراز هویت. دوباره از منو احراز هویت را شروع کن."),
            reply_markup=main_menu_markup(update.effective_user.id),
        )
        return ConversationHandler.END

    upsert_registration(
        telegram_user_id=update.effective_user.id,
        student_number=student_number,
        full_name=full_name,
        profile_text=profile_text,
    )
    context.user_data.clear()

    await update.message.reply_text(
        fa("🎉 احراز هویت با موفقیت انجام شد و تا حذف توسط ادمین فعال می‌ماند."),
        reply_markup=main_menu_markup(update.effective_user.id),
    )
    return ConversationHandler.END


async def begin_remove_student(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if not is_admin(update.effective_user.id):
        await query.edit_message_text(
            text=fa("⛔ دسترسی ادمین نداری."), reply_markup=back_home_markup()
        )
        return ConversationHandler.END

    await query.edit_message_text(
        text=fa("🗑️ شماره دانشجویی دانشجو برای حذف را ارسال کن."),
        reply_markup=cancel_markup(),
    )
    return WAITING_REMOVE_STUDENT_NUMBER


async def receive_remove_student_number(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            fa("⛔ دسترسی ادمین نداری."),
            reply_markup=main_menu_markup(update.effective_user.id),
        )
        return ConversationHandler.END

    student_number = normalize_student_number(update.message.text or "")
    if not student_number:
        await update.message.reply_text(
            fa("⚠️ شماره دانشجویی نامعتبر است."),
            reply_markup=cancel_markup(),
        )
        return WAITING_REMOVE_STUDENT_NUMBER

    deactivated = deactivate_student(student_number)
    if deactivated == 0:
        await update.message.reply_text(
            fa("ℹ️ رکورد فعال برای این شماره پیدا نشد."),
            reply_markup=main_menu_markup(update.effective_user.id),
        )
    else:
        await update.message.reply_text(
            fa("✅ ثبت فعال دانشجو حذف شد."),
            reply_markup=main_menu_markup(update.effective_user.id),
        )
    return ConversationHandler.END


async def begin_rep_import_grades(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()

    if not is_verified_representative(update.effective_user.id):
        await query.edit_message_text(
            text=fa("⛔ فقط نماینده تایید‌شده کلاس به این بخش دسترسی دارد."),
            reply_markup=back_home_markup(),
        )
        return ConversationHandler.END

    await query.edit_message_text(
        text=fa("🧾 نام درس/ارزیابی را ارسال کن.\nمثال: میان‌ترم پروتز ۱"),
        reply_markup=cancel_markup(),
    )
    return WAITING_REP_COURSE_TITLE


async def receive_rep_course_title(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if not is_verified_representative(update.effective_user.id):
        await update.message.reply_text(
            fa("⛔ دسترسی نماینده کلاس تایید نشده است."),
            reply_markup=main_menu_markup(update.effective_user.id),
        )
        return ConversationHandler.END

    course_title = (update.message.text or "").strip()
    if not course_title:
        await update.message.reply_text(
            fa("⚠️ نام درس خالی است. دوباره ارسال کن."),
            reply_markup=cancel_markup(),
        )
        return WAITING_REP_COURSE_TITLE

    context.user_data["rep_course_title"] = course_title
    await update.message.reply_text(
        fa(
            "✅ نام درس ثبت شد.\n"
            "حالا لیست نمرات را خط‌به‌خط بفرست با فرمت:\n"
            "شماره‌دانشجویی، نمره\n\n"
            "مثال:\n"
            "۴۰۲۱۱۲۷۲۰۰۳، ۱۸٫۵\n"
            "۴۰۲۱۱۲۷۲۰۴۲، ۱۷"
        ),
        reply_markup=cancel_markup(),
    )
    return WAITING_REP_GRADE_LIST


async def receive_rep_grade_list(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if not is_verified_representative(update.effective_user.id):
        await update.message.reply_text(
            fa("⛔ دسترسی نماینده کلاس تایید نشده است."),
            reply_markup=main_menu_markup(update.effective_user.id),
        )
        return ConversationHandler.END

    course_title = context.user_data.get("rep_course_title")
    if not course_title:
        await update.message.reply_text(
            fa("❌ نام درس پیدا نشد. دوباره فرآیند را از پنل نماینده شروع کن."),
            reply_markup=main_menu_markup(update.effective_user.id),
        )
        return ConversationHandler.END

    grade_entries, invalid_lines = parse_grade_list_text(update.message.text or "")
    if not grade_entries:
        await update.message.reply_text(
            fa(
                "⚠️ هیچ ردیف معتبری در لیست پیدا نشد.\n"
                "فرمت درست: شماره‌دانشجویی، نمره"
            ),
            reply_markup=cancel_markup(),
        )
        return WAITING_REP_GRADE_LIST

    result = bulk_upsert_course_grades(course_title, grade_entries)
    missing_students = result["missing_students"]
    updated_count = result["updated_count"]

    preview_missing = "\n".join(f"• {item}" for item in missing_students[:10])
    preview_invalid = "\n".join(f"• {item}" for item in invalid_lines[:10])

    report = (
        "✅ ثبت لیست نمره انجام شد.\n"
        f"📚 درس: {course_title}\n"
        f"• تعداد ردیف معتبر دریافت‌شده: {len(grade_entries)}\n"
        f"• تعداد ثبت/به‌روزرسانی موفق: {updated_count}\n"
        f"• تعداد شماره دانشجویی ناموجود: {len(missing_students)}\n"
        f"• تعداد ردیف نامعتبر: {len(invalid_lines)}"
    )
    if preview_missing:
        report += "\n\n⚠️ شماره‌های ناموجود (حداکثر ۱۰ مورد):\n" + preview_missing
    if preview_invalid:
        report += "\n\n⚠️ ردیف‌های نامعتبر (حداکثر ۱۰ مورد):\n" + preview_invalid

    context.user_data.pop("rep_course_title", None)
    await update.message.reply_text(
        fa(report),
        reply_markup=rep_panel_markup(),
    )
    return ConversationHandler.END


async def begin_rep_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if not is_verified_representative(update.effective_user.id):
        await query.edit_message_text(
            text=fa("⛔ فقط نماینده تایید‌شده کلاس به این بخش دسترسی دارد."),
            reply_markup=back_home_markup(),
        )
        return ConversationHandler.END

    await query.edit_message_text(
        text=fa("📣 متن اطلاعیه را ارسال کن تا برای همه دانشجوهای ثبت‌شده فرستاده شود."),
        reply_markup=cancel_markup(),
    )
    return WAITING_REP_BROADCAST_TEXT


async def receive_rep_broadcast_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if not is_verified_representative(update.effective_user.id):
        await update.message.reply_text(
            fa("⛔ دسترسی نماینده کلاس تایید نشده است."),
            reply_markup=main_menu_markup(update.effective_user.id),
        )
        return ConversationHandler.END

    announcement = (update.message.text or "").strip()
    if not announcement:
        await update.message.reply_text(
            fa("⚠️ متن اطلاعیه خالی است. دوباره ارسال کن."),
            reply_markup=cancel_markup(),
        )
        return WAITING_REP_BROADCAST_TEXT

    recipients = list_active_registered_users()
    success_count = 0
    failed_count = 0

    payload = fa(
        "📣 اطلاعیه کلاس دندان‌پزشکی ورودی ۱۴۰۲\n\n"
        + announcement
    )

    for user in recipients:
        try:
            await context.bot.send_message(chat_id=user["telegram_user_id"], text=payload)
            success_count += 1
        except TelegramError:
            failed_count += 1

    await update.message.reply_text(
        fa(
            "✅ ارسال اطلاعیه انجام شد.\n"
            f"• تعداد گیرنده: {len(recipients)}\n"
            f"• ارسال موفق: {success_count}\n"
            f"• ارسال ناموفق: {failed_count}"
        ),
        reply_markup=rep_panel_markup(),
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text=fa("🛑 عملیات لغو شد."),
            reply_markup=main_menu_markup(update.effective_user.id),
        )
    else:
        await update.message.reply_text(
            fa("🛑 عملیات لغو شد."),
            reply_markup=main_menu_markup(update.effective_user.id),
        )
    return ConversationHandler.END


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        fa(f"❓ دستور ناشناخته است. برای ورود به {PROFILE.display_name}، /start را بزن."),
        reply_markup=main_menu_markup(update.effective_user.id),
    )


async def plain_text_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    UX guard: when user sends plain text outside active flows,
    guide them back to inline menu instead of leaving them confused.
    """
    user_id = update.effective_user.id
    if is_verified_user(user_id):
        text = "برای ادامه از دکمه‌های منو استفاده کن 👇"
    else:
        text = "🔐 ابتدا احراز هویت را انجام بده، سپس وارد منوی کامل می‌شوی 👇"
    await update.message.reply_text(
        fa(text),
        reply_markup=main_menu_markup(user_id),
    )



