"""
Inline-First UX Contract (Non-Negotiable):
1) Every end-user feature must start from an inline button (callback).
2) Text input is allowed only for data-entry steps (free text / list input).
3) Every user-facing response must include inline navigation (home/back/cancel/panel).
4) Slash commands are only recovery/bootstrap tools: /start and /cancel.

If you add a new feature, keep this contract.
"""

import json
import logging
import re
from typing import List, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app_callbacks import (
    MENU_ADMIN_HELP,
    MENU_ADMIN_REMOVE,
    MENU_BACK,
    MENU_CANCEL,
    MENU_GRADES,
    MENU_HELP,
    MENU_PROFILE,
    MENU_REGISTER,
    MENU_REP_BROADCAST,
    MENU_REP_FORMS,
    MENU_REP_FORM_CREATE,
    MENU_REP_FORM_LIST,
    MENU_REP_HELP,
    MENU_REP_IMPORT_GRADES,
    MENU_REP_PANEL,
    PREFIX_JOIN_FORM_CANCEL,
    PREFIX_JOIN_FORM_CONFIRM,
    PREFIX_REP_FORM_REFRESH,
    PREFIX_REP_FORM_VIEW,
)
from assistant_profile import PROFILE
from config import (
    ADMIN_IDS,
    MAIN_REP_STUDENT_NUMBER,
    MAIN_REP_TELEGRAM_ID,
    bot_token,
)
from db import (
    bulk_upsert_course_grades,
    create_rep_form,
    deactivate_student,
    get_rep_form_by_id,
    get_rep_form_entry,
    find_student,
    list_rep_form_entries,
    list_rep_forms_by_creator,
    get_active_registration_by_student_number,
    get_active_registration_by_tg_id,
    get_student_grades,
    init_db,
    add_rep_form_entry,
    list_active_registered_users,
    list_students_with_grades,
    upsert_registration,
)
from grade_analytics import (
    build_class_ranking,
    build_grade_insights,
    extract_numeric_items,
)
from text_utils import normalize_numeric_input, to_persian_text

# Conversation states for text-input steps.
(
    WAITING_STUDENT_NUMBER,
    WAITING_PROFILE,
    WAITING_REMOVE_STUDENT_NUMBER,
    WAITING_REP_COURSE_TITLE,
    WAITING_REP_GRADE_LIST,
    WAITING_REP_BROADCAST_TEXT,
    WAITING_REP_FORM_TITLE,
) = range(7)


def fa(text: str) -> str:
    return to_persian_text(text)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def is_rep_candidate(user_id: int) -> bool:
    return user_id == MAIN_REP_TELEGRAM_ID


def is_verified_representative(user_id: int) -> bool:
    if not is_rep_candidate(user_id):
        return False
    registered = get_active_registration_by_tg_id(user_id)
    return bool(
        registered and registered["student_number"] == normalize_numeric_input(MAIN_REP_STUDENT_NUMBER)
    )


def main_menu_markup(user_id: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("📝 ثبت‌نام", callback_data=MENU_REGISTER),
            InlineKeyboardButton("📄 پروفایل من", callback_data=MENU_PROFILE),
        ],
        [
            InlineKeyboardButton("📊 نمرات من", callback_data=MENU_GRADES),
            InlineKeyboardButton("❓ راهنما", callback_data=MENU_HELP),
        ],
    ]
    if is_admin(user_id):
        rows.append(
            [
                InlineKeyboardButton("🛠️ پنل ادمین", callback_data=MENU_ADMIN_HELP),
                InlineKeyboardButton("🗑️ حذف دانشجو", callback_data=MENU_ADMIN_REMOVE),
            ]
        )
    if is_rep_candidate(user_id):
        rows.append([InlineKeyboardButton("🎓 پنل نماینده کلاس", callback_data=MENU_REP_PANEL)])
    return InlineKeyboardMarkup(rows)


def rep_panel_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🧾 ثبت لیست نمره درس", callback_data=MENU_REP_IMPORT_GRADES),
                InlineKeyboardButton("📣 اطلاعیه همگانی", callback_data=MENU_REP_BROADCAST),
            ],
            [InlineKeyboardButton("🗳️ فرم/لیست تلگرامی", callback_data=MENU_REP_FORMS)],
            [InlineKeyboardButton("📘 راهنمای نماینده", callback_data=MENU_REP_HELP)],
            [InlineKeyboardButton("🏠 بازگشت به منو", callback_data=MENU_BACK)],
        ]
    )


def rep_forms_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✍️ ساخت لیست جدید", callback_data=MENU_REP_FORM_CREATE),
                InlineKeyboardButton("📂 لیست‌های من", callback_data=MENU_REP_FORM_LIST),
            ],
            [InlineKeyboardButton("🎓 بازگشت به پنل نماینده", callback_data=MENU_REP_PANEL)],
        ]
    )


def rep_form_view_markup(form_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔄 بروزرسانی لحظه‌ای",
                    callback_data=f"{PREFIX_REP_FORM_REFRESH}{form_id}",
                )
            ],
            [InlineKeyboardButton("🗳️ فرم/لیست‌ها", callback_data=MENU_REP_FORMS)],
            [InlineKeyboardButton("🎓 پنل نماینده", callback_data=MENU_REP_PANEL)],
        ]
    )


def join_form_confirm_markup(form_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ تایید عضویت",
                    callback_data=f"{PREFIX_JOIN_FORM_CONFIRM}{form_id}",
                ),
                InlineKeyboardButton(
                    "❌ انصراف",
                    callback_data=f"{PREFIX_JOIN_FORM_CANCEL}{form_id}",
                ),
            ],
            [InlineKeyboardButton("🏠 منوی اصلی", callback_data=MENU_BACK)],
        ]
    )


def back_home_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🏠 بازگشت به منو", callback_data=MENU_BACK)]]
    )


def cancel_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🛑 لغو", callback_data=MENU_CANCEL)]]
    )


def help_text(admin: bool, rep: bool) -> str:
    active_modules = "\n".join(f"• {module}" for module in PROFILE.active_modules)
    upcoming_modules = "\n".join(f"• {module}" for module in PROFILE.upcoming_modules)
    text = (
        f"📌 {PROFILE.display_name}\n\n"
        f"🎯 گروه هدف: {PROFILE.target_group}\n"
        f"🧭 ماموریت: {PROFILE.mission_statement}\n\n"
        "✅ مسیر فعلی:\n"
        "۱) روی «📝 ثبت‌نام» بزن\n"
        "۲) شماره دانشجویی را بفرست\n"
        "۳) مشخصات تکمیلی را ارسال کن\n"
        "۴) ثبت شما فعال می‌ماند تا ادمین حذف کند\n\n"
        "🧩 ماژول‌های فعال:\n"
        f"{active_modules}\n\n"
        "🚀 ماژول‌های برنامه‌ریزی‌شده:\n"
        f"{upcoming_modules}"
    )
    if admin:
        text += "\n\n🛠️ دسترسی ادمین:\n• پنل ادمین\n• حذف دانشجو"
    if rep:
        text += "\n\n🎓 دسترسی نماینده:\n• پنل نماینده کلاس"
    return text


def admin_help_text() -> str:
    return (
        "🛠️ راهنمای ادمین\n\n"
        "• با «🗑️ حذف دانشجو» ثبت فعال یک شماره دانشجویی غیرفعال می‌شود.\n"
        "• بعد از حذف، دانشجو می‌تواند دوباره ثبت‌نام کند."
    )


def representative_help_text() -> str:
    return (
        "🎓 راهنمای پنل نماینده کلاس\n\n"
        "۱) 🧾 ثبت لیست نمره درس:\n"
        "• اول نام درس/ارزیابی را می‌فرستی.\n"
        "• بعد لیست نمره را خط‌به‌خط می‌فرستی با فرمت:\n"
        "شماره‌دانشجویی، نمره\n"
        "مثال:\n"
        "۴۰۲۱۱۲۷۲۰۰۳، ۱۸٫۵\n"
        "۴۰۲۱۱۲۷۲۰۴۲، ۱۷\n\n"
        "۲) 📣 اطلاعیه همگانی:\n"
        "• متن اطلاعیه را می‌فرستی.\n"
        "• ربات آن را برای همه دانشجوهای ثبت‌شده ارسال می‌کند.\n\n"
        "۳) 🗳️ فرم/لیست تلگرامی:\n"
        "• یک لیست جدید می‌سازی و لینک عضویت می‌گیری.\n"
        "• دانشجو با لینک وارد ربات می‌شود و عضویت را تایید می‌کند.\n"
        "• هر لحظه با دکمه بروزرسانی، لیست اعضا را به‌صورت لحظه‌ای می‌بینی."
    )


def parse_grade_line(line: str) -> Tuple[str, str]:
    normalized = normalize_numeric_input(line)
    normalized = normalized.replace("،", ",").replace("؛", ",").replace(";", ",")
    parts = [p.strip() for p in normalized.split(",", 1)]

    if len(parts) == 2 and parts[0] and parts[1]:
        student_number = normalize_numeric_input(parts[0])
        grade_value = normalize_numeric_input(parts[1])
    else:
        tokens = normalized.split()
        if len(tokens) < 2:
            raise ValueError("invalid format")
        student_number = normalize_numeric_input(tokens[0])
        grade_value = normalize_numeric_input(" ".join(tokens[1:]))

    if not student_number or not grade_value:
        raise ValueError("missing values")
    if not re.fullmatch(r"\d+", student_number):
        raise ValueError("student number must be numeric")

    return student_number, grade_value


def parse_grade_list_text(text: str) -> Tuple[List[Tuple[str, str]], List[str]]:
    grade_entries: List[Tuple[str, str]] = []
    invalid_lines: List[str] = []

    for index, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            grade_entries.append(parse_grade_line(line))
        except ValueError:
            invalid_lines.append(f"{index}: {line}")

    return grade_entries, invalid_lines


def parse_id_from_callback(data: str, prefix: str) -> int | None:
    if not data.startswith(prefix):
        return None
    raw = data[len(prefix) :]
    if not raw.isdigit():
        return None
    return int(raw)


def format_rep_form_members(form_row, entries) -> str:
    lines = [
        f"🗳️ لیست: {form_row['title']}",
        f"🆔 شناسه لیست: {form_row['id']}",
        f"👥 تعداد اعضا: {len(entries)}",
        "",
        "📋 اعضای فعلی:",
    ]

    if not entries:
        lines.append("• هنوز کسی عضو نشده است.")
        return "\n".join(lines)

    max_show = 80
    for idx, entry in enumerate(entries[:max_show], start=1):
        lines.append(
            f"{idx}) {entry['full_name']} - {entry['student_number']}"
        )
    if len(entries) > max_show:
        lines.append(f"... و {len(entries) - max_show} نفر دیگر")
    return "\n".join(lines)


async def open_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = fa(
        f"👋 به {PROFILE.display_name} خوش آمدی.\n"
        "از منوی زیر گزینه موردنظرت رو انتخاب کن:"
    )
    markup = main_menu_markup(update.effective_user.id)

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
                "ℹ️ برای عضویت در لیست، اول باید در ربات ثبت‌نام کرده باشی.\n"
                "از منو روی «📝 ثبت‌نام» بزن."
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
            form_id_raw = normalize_numeric_input(payload.replace("join_form_", "", 1))
            if form_id_raw.isdigit():
                return await handle_join_form_start(update, context, int(form_id_raw))
    await open_main_menu(update, context)
    return ConversationHandler.END


async def menu_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    await query.edit_message_text(
        text=fa(help_text(is_admin(user_id), is_rep_candidate(user_id))),
        reply_markup=back_home_markup(),
    )


async def menu_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    registered = get_active_registration_by_tg_id(update.effective_user.id)
    if not registered:
        await query.edit_message_text(
            text=fa("ℹ️ هنوز ثبت نشده‌ای. از منو روی «📝 ثبت‌نام» بزن."),
            reply_markup=back_home_markup(),
        )
        return

    await query.edit_message_text(
        text=fa(
            "📄 اطلاعات ثبت‌شده شما:\n"
            f"🎓 شماره دانشجویی: {registered['student_number']}\n"
            f"🧑‍🎓 نام کامل: {registered['full_name']}\n"
            f"📝 مشخصات: {registered['profile_text']}\n"
            f"🕒 تاریخ ثبت: {registered['registered_at']} UTC"
        ),
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
                "ابتدا با شماره دانشجویی نماینده اصلی ثبت‌نام کن:\n"
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
            fa("❌ ثبت نماینده پیدا نشد. ابتدا دوباره ثبت‌نام کن."),
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
            text=fa("ℹ️ ابتدا باید در ربات ثبت‌نام کرده باشی."),
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

    registered = get_active_registration_by_tg_id(update.effective_user.id)
    if not registered:
        await query.edit_message_text(
            text=fa("ℹ️ برای دیدن نمرات، اول باید ثبت‌نام انجام بدهی."),
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

    registered = get_active_registration_by_tg_id(update.effective_user.id)
    if registered:
        await query.edit_message_text(
            text=fa(
                "✅ قبلا ثبت شده‌ای.\n"
                f"🎓 شماره دانشجویی: {registered['student_number']}\n"
                f"🧑‍🎓 نام: {registered['full_name']}"
            ),
            reply_markup=back_home_markup(),
        )
        return ConversationHandler.END

    await query.edit_message_text(
        text=fa("🔢 شماره دانشجویی خودت رو ارسال کن."),
        reply_markup=cancel_markup(),
    )
    return WAITING_STUDENT_NUMBER


async def receive_student_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    student_number = normalize_numeric_input(update.message.text or "")
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
            fa("❌ خطا در فرآیند ثبت. دوباره از منو ثبت‌نام را شروع کن."),
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
        fa("🎉 ثبت با موفقیت انجام شد و فعال ماند تا ادمین حذف کند."),
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

    student_number = normalize_numeric_input(update.message.text or "")
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


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    init_db()

    app = ApplicationBuilder().token(bot_token).build()

    # Inline-first conversation router.
    # New user features must be wired here via callback entry_points + state handlers.
    conversation = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(begin_register, pattern=f"^{MENU_REGISTER}$"),
            CallbackQueryHandler(begin_remove_student, pattern=f"^{MENU_ADMIN_REMOVE}$"),
            CallbackQueryHandler(begin_rep_import_grades, pattern=f"^{MENU_REP_IMPORT_GRADES}$"),
            CallbackQueryHandler(begin_rep_broadcast, pattern=f"^{MENU_REP_BROADCAST}$"),
            CallbackQueryHandler(begin_rep_form_create, pattern=f"^{MENU_REP_FORM_CREATE}$"),
        ],
        states={
            WAITING_STUDENT_NUMBER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_student_number)
            ],
            WAITING_PROFILE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_profile)
            ],
            WAITING_REMOVE_STUDENT_NUMBER: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, receive_remove_student_number
                )
            ],
            WAITING_REP_COURSE_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_rep_course_title)
            ],
            WAITING_REP_GRADE_LIST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_rep_grade_list)
            ],
            WAITING_REP_BROADCAST_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_rep_broadcast_text)
            ],
            WAITING_REP_FORM_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_rep_form_title)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, pattern=f"^{MENU_CANCEL}$"),
            CallbackQueryHandler(back_to_menu, pattern=f"^{MENU_BACK}$"),
        ],
        per_message=False,
    )

    app.add_handler(conversation)
    app.add_handler(CallbackQueryHandler(back_to_menu, pattern=f"^{MENU_BACK}$"))
    app.add_handler(CallbackQueryHandler(menu_profile, pattern=f"^{MENU_PROFILE}$"))
    app.add_handler(CallbackQueryHandler(menu_grades, pattern=f"^{MENU_GRADES}$"))
    app.add_handler(CallbackQueryHandler(menu_help, pattern=f"^{MENU_HELP}$"))
    app.add_handler(CallbackQueryHandler(menu_admin_help, pattern=f"^{MENU_ADMIN_HELP}$"))
    app.add_handler(CallbackQueryHandler(menu_rep_panel, pattern=f"^{MENU_REP_PANEL}$"))
    app.add_handler(CallbackQueryHandler(menu_rep_help, pattern=f"^{MENU_REP_HELP}$"))
    app.add_handler(CallbackQueryHandler(menu_rep_forms, pattern=f"^{MENU_REP_FORMS}$"))
    app.add_handler(CallbackQueryHandler(menu_rep_form_list, pattern=f"^{MENU_REP_FORM_LIST}$"))
    app.add_handler(
        CallbackQueryHandler(menu_rep_form_view, pattern=f"^{PREFIX_REP_FORM_VIEW}\\d+$")
    )
    app.add_handler(
        CallbackQueryHandler(menu_rep_form_refresh, pattern=f"^{PREFIX_REP_FORM_REFRESH}\\d+$")
    )
    app.add_handler(
        CallbackQueryHandler(join_form_confirm, pattern=f"^{PREFIX_JOIN_FORM_CONFIRM}\\d+$")
    )
    app.add_handler(
        CallbackQueryHandler(join_form_cancel, pattern=f"^{PREFIX_JOIN_FORM_CANCEL}\\d+$")
    )
    # Keep command surface minimal. /start is the main recovery/bootstrap command.
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    app.run_polling()


if __name__ == "__main__":
    main()
