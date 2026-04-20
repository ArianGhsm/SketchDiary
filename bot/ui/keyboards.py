from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

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
from bot.services.policies import is_admin, is_rep_candidate


def home_markup(user_id: int, verified: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if not verified:
        kb.button(text="✅ شروع احراز هویت", callback_data=MENU_REGISTER)
    else:
        kb.button(text="👤 پروفایل من", callback_data=MENU_PROFILE)
        kb.button(text="📊 کارنامه و تحلیل", callback_data=MENU_GRADES)
        kb.adjust(2)
        kb.button(text="🔐 وضعیت احراز هویت", callback_data=MENU_REGISTER)
    if is_rep_candidate(user_id):
        kb.button(text="🎓 پنل نماینده", callback_data=MENU_REP_PANEL)
    if is_admin(user_id):
        kb.button(text="🛠 پنل مدیریت", callback_data=MENU_ADMIN_PANEL)
    kb.adjust(1)
    return kb.as_markup()


def simple_back_home_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ منوی اصلی", callback_data=MENU_HOME)]])


def cancel_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ لغو", callback_data=MENU_CANCEL)]])


def rep_panel_markup() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🟢 درخواست‌های احراز هویت", callback_data=MENU_REP_PENDING)
    kb.button(text="🧾 ثبت گروهی نمره", callback_data=MENU_REP_IMPORT_GRADES)
    kb.button(text="📣 اطلاعیه همگانی", callback_data=MENU_REP_BROADCAST)
    kb.button(text="🗂 فرم‌ها و لیست‌ها", callback_data=MENU_REP_FORMS)
    kb.button(text="⏰ زمان‌بندی اعلان‌ها", callback_data=MENU_REP_SCHEDULES)
    kb.button(text="↩️ منوی اصلی", callback_data=MENU_HOME)
    kb.adjust(1, 2, 1, 1, 1)
    return kb.as_markup()


def admin_panel_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑 حذف ثبت فعال دانشجو", callback_data=MENU_ADMIN_REMOVE)],
            [InlineKeyboardButton(text="↩️ منوی اصلی", callback_data=MENU_HOME)],
        ]
    )


def verification_request_markup(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ تایید حساب", callback_data=f"{PREFIX_VERIFY_APPROVE}{request_id}"),
                InlineKeyboardButton(text="❌ رد درخواست", callback_data=f"{PREFIX_VERIFY_REJECT}{request_id}"),
            ]
        ]
    )


def forms_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ ساخت فرم جدید", callback_data=MENU_REP_FORM_CREATE),
                InlineKeyboardButton(text="📚 فرم‌های من", callback_data=MENU_REP_FORM_LIST),
            ],
            [InlineKeyboardButton(text="↩️ پنل نماینده", callback_data=MENU_REP_PANEL)],
        ]
    )


def form_list_markup(forms, page: int, total_pages: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for form in forms:
        kb.button(text=f"🗂 {form['title']}", callback_data=f"{PREFIX_FORM_VIEW}{form['id']}")
    if total_pages > 1:
        if page > 1:
            kb.button(text="◀️ قبلی", callback_data=f"{PREFIX_PAGE}forms:{page - 1}")
        if page < total_pages:
            kb.button(text="▶️ بعدی", callback_data=f"{PREFIX_PAGE}forms:{page + 1}")
    kb.button(text="↩️ فرم‌ها", callback_data=MENU_REP_FORMS)
    kb.adjust(1)
    return kb.as_markup()


def form_detail_markup(form_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📤 خروجی متنی نام‌ها", callback_data=f"{PREFIX_FORM_EXPORT}names:{form_id}")
    kb.button(text="📤 خروجی نام-شماره", callback_data=f"{PREFIX_FORM_EXPORT}name_ids:{form_id}")
    kb.button(text="📄 خروجی CSV", callback_data=f"{PREFIX_FORM_EXPORT}csv:{form_id}")
    kb.button(text="📗 خروجی XLSX", callback_data=f"{PREFIX_FORM_EXPORT}xlsx:{form_id}")
    kb.button(text="🧩 خروجی JSON", callback_data=f"{PREFIX_FORM_EXPORT}json:{form_id}")
    kb.button(text="🔍 جستجوی پاسخ‌ها", callback_data=f"{PREFIX_FORM_SEARCH}{form_id}")
    kb.button(text="➕ افزودن دستی دانشجو", callback_data=f"{PREFIX_FORM_MANUAL_ADD}{form_id}")
    kb.button(text="🗑 حذف ثبت دانشجو", callback_data=f"{PREFIX_FORM_REMOVE_SUBMISSION}{form_id}")
    kb.button(text="📣 یادآوری به ثبت‌نکرده‌ها", callback_data=f"{PREFIX_FORM_REMIND}{form_id}")
    kb.button(text="🧬 کپی ساختار فرم", callback_data=f"{PREFIX_FORM_DUPLICATE}{form_id}")
    kb.button(text="⏰ زمان‌بندی انتشار", callback_data=f"{PREFIX_SCHEDULE_FORM}{form_id}")
    kb.button(text="🔴 بستن فرم", callback_data=f"{PREFIX_FORM_CLOSE}{form_id}")
    kb.button(text="🟢 بازگشایی فرم", callback_data=f"{PREFIX_FORM_REOPEN}{form_id}")
    kb.button(text="↩️ فرم‌ها", callback_data=MENU_REP_FORMS)
    kb.adjust(2, 2, 2, 2, 2, 1, 1, 1)
    return kb.as_markup()


def form_join_markup(form_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ شروع پاسخ‌گویی", callback_data=f"{PREFIX_FORM_JOIN}{form_id}")],
            [InlineKeyboardButton(text="↩️ منوی اصلی", callback_data=MENU_HOME)],
        ]
    )


def question_type_markup() -> InlineKeyboardMarkup:
    types = [
        ("متن کوتاه", "text"),
        ("متن بلند", "long_text"),
        ("عدد", "number"),
        ("تک‌گزینه‌ای", "multiple_choice"),
        ("چندگزینه‌ای", "checkboxes"),
        ("منوی کشویی", "dropdown"),
        ("تاریخ/زمان", "date_time"),
    ]
    kb = InlineKeyboardBuilder()
    for label, value in types:
        kb.button(text=f"🧩 {label}", callback_data=f"{PREFIX_QUESTION_TYPE}{value}")
    kb.button(text="❌ لغو", callback_data=MENU_CANCEL)
    kb.adjust(1)
    return kb.as_markup()


def required_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ اجباری", callback_data=f"{PREFIX_REQUIRED}yes"),
                InlineKeyboardButton(text="➖ اختیاری", callback_data=f"{PREFIX_REQUIRED}no"),
            ]
        ]
    )


def add_another_question_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ سوال بعدی", callback_data=f"{PREFIX_ADD_ANOTHER_QUESTION}yes"),
                InlineKeyboardButton(text="✅ پایان و ساخت فرم", callback_data=f"{PREFIX_ADD_ANOTHER_QUESTION}no"),
            ]
        ]
    )


def single_choice_markup(question_id: int, options: list[str], prefix: str = PREFIX_CHOICE_PICK) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for index, option in enumerate(options):
        kb.button(text=option, callback_data=f"{prefix}{question_id}:{index}")
    kb.adjust(1)
    return kb.as_markup()


def checkbox_markup(question_id: int, options: list[str], selected: set[int]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for index, option in enumerate(options):
        marker = "✅" if index in selected else "⬜"
        kb.button(text=f"{marker} {option}", callback_data=f"{PREFIX_CHECKBOX_TOGGLE}{question_id}:{index}")
    kb.button(text="✅ ثبت انتخاب‌ها", callback_data=f"{PREFIX_CHECKBOX_DONE}{question_id}")
    kb.adjust(1)
    return kb.as_markup()


def schedule_recurring_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="فقط یک‌بار", callback_data=f"{PREFIX_SCHEDULE_CANCEL}once"),
                InlineKeyboardButton(text="هفتگی", callback_data=f"{PREFIX_SCHEDULE_CANCEL}weekly"),
                InlineKeyboardButton(text="ماهانه", callback_data=f"{PREFIX_SCHEDULE_CANCEL}monthly"),
            ]
        ]
    )
