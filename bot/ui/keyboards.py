from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app_callbacks import (
    MENU_ADMIN_PANEL,
    MENU_ADMIN_REMOVE,
    MENU_BACK,
    MENU_CANCEL,
    MENU_GRADES,
    MENU_PROFILE,
    MENU_REGISTER,
    MENU_REP_BROADCAST,
    MENU_REP_FORMS,
    MENU_REP_FORM_CREATE,
    MENU_REP_FORM_LIST,
    MENU_REP_IMPORT_GRADES,
    MENU_REP_PANEL,
    MENU_REP_PENDING,
    PREFIX_JOIN_FORM_CANCEL,
    PREFIX_JOIN_FORM_CONFIRM,
    PREFIX_REP_FORM_REFRESH,
    PREFIX_VERIFY_APPROVE,
    PREFIX_VERIFY_REJECT,
)
from bot.services.policies import is_admin, is_rep_candidate, is_verified_user


def main_menu_markup(user_id: int, verified: bool | None = None) -> InlineKeyboardMarkup:
    if verified is None:
        verified = is_verified_user(user_id)

    if not verified:
        rows = [[InlineKeyboardButton("✅ شروع احراز هویت", callback_data=MENU_REGISTER)]]
        if is_admin(user_id):
            rows.append([InlineKeyboardButton("🛠 پنل مدیریت", callback_data=MENU_ADMIN_PANEL)])
        if is_rep_candidate(user_id):
            rows.append([InlineKeyboardButton("🎓 پنل نماینده", callback_data=MENU_REP_PANEL)])
        return InlineKeyboardMarkup(rows)

    rows = [
        [
            InlineKeyboardButton("👤 پروفایل من", callback_data=MENU_PROFILE),
            InlineKeyboardButton("📊 کارنامه و تحلیل", callback_data=MENU_GRADES),
        ],
        [InlineKeyboardButton("🔐 وضعیت احراز هویت", callback_data=MENU_REGISTER)],
    ]

    if is_rep_candidate(user_id):
        rows.append([InlineKeyboardButton("🎓 پنل نماینده", callback_data=MENU_REP_PANEL)])
    if is_admin(user_id):
        rows.append([InlineKeyboardButton("🛠 پنل مدیریت", callback_data=MENU_ADMIN_PANEL)])
    return InlineKeyboardMarkup(rows)


def rep_panel_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🟢 درخواست‌های احراز هویت", callback_data=MENU_REP_PENDING)],
            [
                InlineKeyboardButton("🧾 ثبت گروهی نمره", callback_data=MENU_REP_IMPORT_GRADES),
                InlineKeyboardButton("📣 اطلاعیه همگانی", callback_data=MENU_REP_BROADCAST),
            ],
            [InlineKeyboardButton("🗂 فرم‌ها و لیست‌ها", callback_data=MENU_REP_FORMS)],
            [InlineKeyboardButton("↩️ بازگشت به منوی اصلی", callback_data=MENU_BACK)],
        ]
    )


def admin_panel_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🗑 حذف ثبت فعال دانشجو", callback_data=MENU_ADMIN_REMOVE)],
            [InlineKeyboardButton("↩️ بازگشت به منوی اصلی", callback_data=MENU_BACK)],
        ]
    )


def rep_forms_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("➕ ساخت فرم جدید", callback_data=MENU_REP_FORM_CREATE),
                InlineKeyboardButton("📚 فرم‌های من", callback_data=MENU_REP_FORM_LIST),
            ],
            [InlineKeyboardButton("↩️ بازگشت به پنل نماینده", callback_data=MENU_REP_PANEL)],
        ]
    )


def rep_form_view_markup(form_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔄 بروزرسانی", callback_data=f"{PREFIX_REP_FORM_REFRESH}{form_id}")],
            [InlineKeyboardButton("🗂 فرم‌ها و لیست‌ها", callback_data=MENU_REP_FORMS)],
            [InlineKeyboardButton("↩️ بازگشت به پنل نماینده", callback_data=MENU_REP_PANEL)],
        ]
    )


def join_form_confirm_markup(form_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ تایید عضویت", callback_data=f"{PREFIX_JOIN_FORM_CONFIRM}{form_id}"),
                InlineKeyboardButton("❌ انصراف", callback_data=f"{PREFIX_JOIN_FORM_CANCEL}{form_id}"),
            ],
            [InlineKeyboardButton("↩️ بازگشت به منوی اصلی", callback_data=MENU_BACK)],
        ]
    )


def verification_request_markup(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ تایید حساب", callback_data=f"{PREFIX_VERIFY_APPROVE}{request_id}"),
                InlineKeyboardButton("❌ رد درخواست", callback_data=f"{PREFIX_VERIFY_REJECT}{request_id}"),
            ]
        ]
    )


def back_home_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("↩️ بازگشت به منوی اصلی", callback_data=MENU_BACK)]]
    )


def cancel_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ لغو", callback_data=MENU_CANCEL)]]
    )
