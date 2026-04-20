from telegram import InlineKeyboardButton, InlineKeyboardMarkup

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
from bot.services.policies import is_admin, is_rep_candidate, is_verified_user


def main_menu_markup(user_id: int, verified: bool | None = None) -> InlineKeyboardMarkup:
    if verified is None:
        verified = is_verified_user(user_id)

    if not verified:
        rows = [
            [InlineKeyboardButton("🔐 احراز هویت", callback_data=MENU_REGISTER)],
            [InlineKeyboardButton("❓ راهنما", callback_data=MENU_HELP)],
        ]

        if is_admin(user_id):
            rows.append(
                [
                    InlineKeyboardButton("🛠️ پنل ادمین", callback_data=MENU_ADMIN_HELP),
                    InlineKeyboardButton("🗑️ حذف دانشجو", callback_data=MENU_ADMIN_REMOVE),
                ]
            )
        return InlineKeyboardMarkup(rows)

    rows = [
        [
            InlineKeyboardButton("🔐 وضعیت احراز هویت", callback_data=MENU_REGISTER),
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
