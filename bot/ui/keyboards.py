from __future__ import annotations

from aiogram.types import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

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
    PREFIX_ADMIN_REMOVE_CANCEL,
    PREFIX_ADMIN_CHANNEL_PICK,
    PREFIX_ADMIN_CHANNEL_SET,
    PREFIX_ADMIN_REMOVE_CONFIRM,
    PREFIX_ADMIN_REMOVE_SELECT,
    PREFIX_ADMIN_STUDENT_SEARCH,
    PREFIX_ADMIN_STUDENT_SORT,
    PREFIX_CHECKBOX_DONE,
    PREFIX_CHECKBOX_TOGGLE,
    PREFIX_CHOICE_PICK,
    PREFIX_DATE_PICKER,
    PREFIX_FORM_CLOSE,
    PREFIX_FORM_DUPLICATE,
    PREFIX_FORM_EXPORT,
    PREFIX_FORM_JOIN,
    PREFIX_FORM_CHANNELS,
    PREFIX_FORM_CHANNEL_PICK,
    PREFIX_FORM_DELETE,
    PREFIX_FORM_DELETE_CONFIRM,
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
from bot.services.date_picker import MONTH_NAMES, MINUTE_OPTIONS, days_in_month, shift_month
from bot.services.policies import is_admin, is_rep_candidate


def _button(
    text: str,
    *,
    callback_data: str | None = None,
    url: str | None = None,
    copy_text_value: str | None = None,
    kind: str = "primary",
) -> InlineKeyboardButton:
    payload = {"text": text}
    if kind in {"success", "danger"}:
        payload["style"] = kind
    if callback_data is not None:
        payload["callback_data"] = callback_data
    elif url is not None:
        payload["url"] = url
    elif copy_text_value is not None:
        payload["copy_text"] = CopyTextButton(text=copy_text_value)
    return InlineKeyboardButton(**payload)


def home_markup(user_id: int, verified: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if not verified:
        kb.row(_button("✅ شروع احراز هویت", callback_data=MENU_REGISTER, kind="success"))
    else:
        kb.row(
            _button("👤 پروفایل من", callback_data=MENU_PROFILE),
            _button("📊 کارنامه و تحلیل", callback_data=MENU_GRADES),
        )
        kb.row(_button("🔐 وضعیت احراز هویت", callback_data=MENU_REGISTER))
    if is_rep_candidate(user_id):
        kb.row(_button("🎓 پنل نماینده", callback_data=MENU_REP_PANEL))
    if is_admin(user_id):
        kb.row(_button("🛠 پنل مدیریت", callback_data=MENU_ADMIN_PANEL))
    return kb.as_markup()


def simple_back_home_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_button("↩️ منوی اصلی", callback_data=MENU_HOME)]])


def cancel_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_button("❌ لغو", callback_data=MENU_CANCEL, kind="danger")]])


def rep_panel_markup() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(_button("🟢 درخواست‌های احراز هویت", callback_data=MENU_REP_PENDING))
    kb.row(
        _button("🧾 ثبت گروهی نمره", callback_data=MENU_REP_IMPORT_GRADES),
        _button("📣 اطلاعیه همگانی", callback_data=MENU_REP_BROADCAST),
    )
    kb.row(
        _button("🗂 فرم‌ها و لیست‌ها", callback_data=MENU_REP_FORMS),
        _button("⏰ زمان‌بندی اعلان‌ها", callback_data=MENU_REP_SCHEDULES),
    )
    kb.row(_button("↩️ منوی اصلی", callback_data=MENU_HOME))
    return kb.as_markup()


def pending_requests_markup(page: int, total_pages: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    nav = []
    if total_pages > 1 and page > 1:
        nav.append(_button("◀️ قبلی", callback_data=f"{PREFIX_PAGE}pending:{page - 1}"))
    if total_pages > 1 and page < total_pages:
        nav.append(_button("▶️ بعدی", callback_data=f"{PREFIX_PAGE}pending:{page + 1}"))
    if nav:
        kb.row(*nav)
    kb.row(_button("↩️ پنل نماینده", callback_data=MENU_REP_PANEL))
    return kb.as_markup()


def admin_panel_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button("👥 دانشجوهای تاییدشده", callback_data=MENU_ADMIN_STUDENTS)],
            [_button("📡 کانال‌های سراسری", callback_data=MENU_ADMIN_CHANNELS)],
            [_button("🗜 بکاپ دیتابیس", callback_data=MENU_ADMIN_BACKUP)],
            [_button("🗑 حذف ثبت فعال", callback_data=MENU_ADMIN_REMOVE, kind="danger")],
            [_button("⌨️ حذف با شماره دانشجویی", callback_data=MENU_ADMIN_REMOVE_DIRECT, kind="danger")],
            [_button("↩️ منوی اصلی", callback_data=MENU_HOME)],
        ]
    )


def verification_request_markup(request_id: int, student_number: str | None = None) -> InlineKeyboardMarkup:
    rows = [
        [
            _button("✅ تایید حساب", callback_data=f"{PREFIX_VERIFY_APPROVE}{request_id}", kind="success"),
            _button("❌ رد درخواست", callback_data=f"{PREFIX_VERIFY_REJECT}{request_id}", kind="danger"),
        ]
    ]
    if student_number:
        rows.append([_button("📋 کپی شماره دانشجویی", copy_text_value=student_number)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def forms_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button("🧩 فرم سفارشی", callback_data=MENU_REP_FORM_CREATE, kind="success"),
                _button("⚡ ساخت سریع لیست", callback_data=MENU_REP_FORM_CREATE_QUICK, kind="success"),
            ],
            [
                _button("📚 فرم‌های من", callback_data=MENU_REP_FORM_LIST),
            ],
            [_button("↩️ پنل نماینده", callback_data=MENU_REP_PANEL)],
        ]
    )


def form_list_markup(forms, page: int, total_pages: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for form in forms:
        kb.row(_button(f"🗂 {form['title']}", callback_data=f"{PREFIX_FORM_VIEW}{form['id']}"))
    nav = []
    if total_pages > 1 and page > 1:
        nav.append(_button("◀️ قبلی", callback_data=f"{PREFIX_PAGE}forms:{page - 1}"))
    if total_pages > 1 and page < total_pages:
        nav.append(_button("▶️ بعدی", callback_data=f"{PREFIX_PAGE}forms:{page + 1}"))
    if nav:
        kb.row(*nav)
    kb.row(_button("↩️ فرم‌ها", callback_data=MENU_REP_FORMS))
    return kb.as_markup()


def form_detail_markup(form_id: int, share_link: str | None = None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if share_link:
        kb.row(
            _button("📌 ورود دانشجو", url=share_link),
            _button("📋 کپی لینک", copy_text_value=share_link),
        )
    kb.row(
        _button("📤 خروجی نام‌ها", callback_data=f"{PREFIX_FORM_EXPORT}names:{form_id}"),
        _button("📤 خروجی نام-شماره", callback_data=f"{PREFIX_FORM_EXPORT}name_ids:{form_id}"),
    )
    kb.row(
        _button("📄 خروجی CSV", callback_data=f"{PREFIX_FORM_EXPORT}csv:{form_id}"),
        _button("📗 خروجی XLSX", callback_data=f"{PREFIX_FORM_EXPORT}xlsx:{form_id}"),
    )
    kb.row(
        _button("🧩 خروجی JSON", callback_data=f"{PREFIX_FORM_EXPORT}json:{form_id}"),
        _button("🔍 جستجوی پاسخ‌ها", callback_data=f"{PREFIX_FORM_SEARCH}{form_id}"),
    )
    kb.row(
        _button("➕ افزودن دستی دانشجو", callback_data=f"{PREFIX_FORM_MANUAL_ADD}{form_id}", kind="success"),
        _button("🗑 حذف ثبت دانشجو", callback_data=f"{PREFIX_FORM_REMOVE_SUBMISSION}{form_id}", kind="danger"),
    )
    kb.row(
        _button("📣 یادآوری به ثبت‌نکرده‌ها", callback_data=f"{PREFIX_FORM_REMIND}{form_id}"),
        _button("🧬 کپی ساختار فرم", callback_data=f"{PREFIX_FORM_DUPLICATE}{form_id}"),
    )
    kb.row(
        _button("📣 کانال انتشار", callback_data=f"{PREFIX_FORM_CHANNELS}{form_id}"),
        _button("⏰ زمان‌بندی انتشار", callback_data=f"{PREFIX_SCHEDULE_FORM}{form_id}"),
    )
    kb.row(
        _button("🔴 بستن فرم", callback_data=f"{PREFIX_FORM_CLOSE}{form_id}", kind="danger"),
        _button("🟢 بازگشایی فرم", callback_data=f"{PREFIX_FORM_REOPEN}{form_id}", kind="success"),
    )
    kb.row(
        _button("🗑 حذف فرم", callback_data=f"{PREFIX_FORM_DELETE}{form_id}", kind="danger"),
        _button("↩️ فرم‌ها", callback_data=MENU_REP_FORMS),
    )
    return kb.as_markup()


def form_join_markup(form_id: int, form_kind: str = "custom") -> InlineKeyboardMarkup:
    submit_label = "✅ تایید عضویت در لیست" if form_kind == "quick_list" else "✅ شروع پاسخ‌گویی"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button(submit_label, callback_data=f"{PREFIX_FORM_JOIN}{form_id}", kind="success")],
            [_button("↩️ منوی اصلی", callback_data=MENU_HOME)],
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
        kb.row(_button(f"🧩 {label}", callback_data=f"{PREFIX_QUESTION_TYPE}{value}"))
    kb.row(_button("❌ لغو", callback_data=MENU_CANCEL, kind="danger"))
    return kb.as_markup()


def required_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button("✅ اجباری", callback_data=f"{PREFIX_REQUIRED}yes", kind="success"),
                _button("➖ اختیاری", callback_data=f"{PREFIX_REQUIRED}no"),
            ]
        ]
    )


def add_another_question_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button("➕ سوال بعدی", callback_data=f"{PREFIX_ADD_ANOTHER_QUESTION}yes"),
                _button("✅ پایان و ساخت فرم", callback_data=f"{PREFIX_ADD_ANOTHER_QUESTION}no", kind="success"),
            ]
        ]
    )


def single_choice_markup(question_id: int, options: list[str], prefix: str = PREFIX_CHOICE_PICK) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for index, option in enumerate(options):
        kb.row(_button(option, callback_data=f"{prefix}{question_id}:{index}"))
    return kb.as_markup()


def checkbox_markup(question_id: int, options: list[str], selected: set[int]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for index, option in enumerate(options):
        marker = "✅" if index in selected else "⬜"
        kb.row(_button(f"{marker} {option}", callback_data=f"{PREFIX_CHECKBOX_TOGGLE}{question_id}:{index}"))
    kb.row(_button("✅ ثبت انتخاب‌ها", callback_data=f"{PREFIX_CHECKBOX_DONE}{question_id}", kind="success"))
    return kb.as_markup()


def schedule_recurring_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button("فقط یک‌بار", callback_data=f"{PREFIX_SCHEDULE_CANCEL}once", kind="success"),
                _button("هفتگی", callback_data=f"{PREFIX_SCHEDULE_CANCEL}weekly"),
                _button("ماهانه", callback_data=f"{PREFIX_SCHEDULE_CANCEL}monthly"),
            ]
        ]
    )


def schedule_channel_picker_markup(channel_ids: list[int]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for channel_id in channel_ids[:6]:
        kb.row(_button(f"📣 {channel_id}", callback_data=f"{PREFIX_SCHEDULE_CHANNEL_PICK}{channel_id}"))
    kb.row(_button("⌨️ واردکردن شناسه دیگر", callback_data=f"{PREFIX_SCHEDULE_CHANNEL_PICK}manual"))
    kb.row(_button("❌ لغو", callback_data=MENU_CANCEL, kind="danger"))
    return kb.as_markup()


def schedule_list_markup(rows, page: int, total_pages: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for row in rows:
        kb.row(_button(f"🗓 زمان‌بندی {row['id']}", callback_data=f"{PREFIX_SCHEDULE_VIEW}{row['id']}"))
    nav = []
    if total_pages > 1 and page > 1:
        nav.append(_button("◀️ قبلی", callback_data=f"{PREFIX_PAGE}schedules:{page - 1}"))
    if total_pages > 1 and page < total_pages:
        nav.append(_button("▶️ بعدی", callback_data=f"{PREFIX_PAGE}schedules:{page + 1}"))
    if nav:
        kb.row(*nav)
    kb.row(_button("↩️ پنل نماینده", callback_data=MENU_REP_PANEL))
    return kb.as_markup()


def schedule_detail_markup(schedule_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button("🛑 غیرفعال‌کردن زمان‌بندی", callback_data=f"{PREFIX_SCHEDULE_DEACTIVATE}{schedule_id}", kind="danger")],
            [_button("↩️ زمان‌بندی‌ها", callback_data=MENU_REP_SCHEDULES)],
        ]
    )


def form_channel_settings_markup(form_id: int, available_channels: list[tuple[str, int]]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    labels = {
        "class": "📣 اطلاع‌رسانی",
        "notes": "📝 جزوه",
    }
    for channel_kind, channel_id in available_channels:
        title = labels.get(channel_kind, "📣 کانال")
        kb.row(_button(f"{title} — {channel_id}", callback_data=f"{PREFIX_FORM_CHANNEL_PICK}{form_id}:{channel_kind}"))
    kb.row(_button("↩️ بازگشت به فرم", callback_data=f"{PREFIX_FORM_VIEW}{form_id}"))
    return kb.as_markup()


def form_delete_confirmation_markup(form_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button("🗑 حذف نهایی فرم", callback_data=f"{PREFIX_FORM_DELETE_CONFIRM}{form_id}", kind="danger"),
                _button("↩️ انصراف", callback_data=f"{PREFIX_FORM_VIEW}{form_id}"),
            ]
        ]
    )


def admin_channel_settings_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button("📣 کانال اطلاع‌رسانی", callback_data=f"{PREFIX_ADMIN_CHANNEL_SET}class"),
                _button("📝 کانال جزوه", callback_data=f"{PREFIX_ADMIN_CHANNEL_SET}notes"),
            ],
            [_button("↩️ پنل مدیریت", callback_data=MENU_ADMIN_PANEL)],
        ]
    )


def admin_channel_picker_markup(channel_kind: str, channel_ids: list[int]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for channel_id in channel_ids[:6]:
        kb.row(_button(f"📣 {channel_id}", callback_data=f"{PREFIX_ADMIN_CHANNEL_PICK}{channel_kind}:{channel_id}"))
    kb.row(_button("⌨️ واردکردن شناسه دستی", callback_data=f"{PREFIX_ADMIN_CHANNEL_PICK}{channel_kind}:manual"))
    kb.row(_button("↩️ کانال‌های سراسری", callback_data=MENU_ADMIN_CHANNELS))
    return kb.as_markup()


def admin_student_list_markup(
    rows,
    page: int,
    total_pages: int,
    *,
    query: str | None = None,
    sort_by: str = "approved_at_desc",
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for row in rows:
        kb.row(
            _button(
                f"🗑 حذف {row['full_name']}",
                callback_data=f"{PREFIX_ADMIN_REMOVE_SELECT}{row['student_number']}",
                kind="danger",
            )
        )
    kb.row(_button("🔎 جستجو", callback_data=f"{PREFIX_ADMIN_STUDENT_SEARCH}prompt"))
    if query:
        kb.row(_button("🧹 پاک‌کردن جستجو", callback_data=f"{PREFIX_ADMIN_STUDENT_SEARCH}clear", kind="danger"))
    kb.row(
        _button(
            "🕒 جدیدترین",
            callback_data=f"{PREFIX_ADMIN_STUDENT_SORT}approved_at_desc",
            kind="success" if sort_by == "approved_at_desc" else "primary",
        ),
        _button(
            "🕰 قدیمی‌ترین",
            callback_data=f"{PREFIX_ADMIN_STUDENT_SORT}approved_at_asc",
            kind="success" if sort_by == "approved_at_asc" else "primary",
        ),
    )
    kb.row(
        _button(
            "🎓 شماره",
            callback_data=f"{PREFIX_ADMIN_STUDENT_SORT}student_number",
            kind="success" if sort_by == "student_number" else "primary",
        ),
        _button(
            "👤 نام",
            callback_data=f"{PREFIX_ADMIN_STUDENT_SORT}name",
            kind="success" if sort_by == "name" else "primary",
        ),
    )
    nav = []
    if total_pages > 1 and page > 1:
        nav.append(_button("◀️ قبلی", callback_data=f"{PREFIX_PAGE}admin_students:{page - 1}"))
    if total_pages > 1 and page < total_pages:
        nav.append(_button("▶️ بعدی", callback_data=f"{PREFIX_PAGE}admin_students:{page + 1}"))
    if nav:
        kb.row(*nav)
    kb.row(_button("⌨️ حذف با شماره دانشجویی", callback_data=MENU_ADMIN_REMOVE_DIRECT, kind="danger"))
    kb.row(_button("↩️ پنل مدیریت", callback_data=MENU_ADMIN_PANEL))
    return kb.as_markup()


def admin_remove_confirmation_markup(student_number: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button(
                    "✅ تایید حذف",
                    callback_data=f"{PREFIX_ADMIN_REMOVE_CONFIRM}{student_number}",
                    kind="danger",
                ),
                _button(
                    "❌ انصراف",
                    callback_data=f"{PREFIX_ADMIN_REMOVE_CANCEL}{student_number}",
                    kind="primary",
                ),
            ],
            [_button("📋 کپی شماره دانشجویی", copy_text_value=student_number)],
            [_button("↩️ پنل مدیریت", callback_data=MENU_ADMIN_PANEL)],
        ]
    )


def date_picker_markup(data: dict) -> InlineKeyboardMarkup:
    step = data["step"]
    kb = InlineKeyboardBuilder()

    if step == "year":
        base = data.get("year_base", data["year"] - 1)
        years = [base + offset for offset in range(5)]
        kb.row(
            _button("◀️ سال‌های قبل", callback_data=f"{PREFIX_DATE_PICKER}year_base:{base - 4}"),
            _button("سال‌های بعد ▶️", callback_data=f"{PREFIX_DATE_PICKER}year_base:{base + 4}"),
        )
        for index in range(0, len(years), 2):
            row_buttons = [
                _button(
                    f"📅 {years[index]}",
                    callback_data=f"{PREFIX_DATE_PICKER}set_year:{years[index]}",
                    kind="success" if years[index] == data["year"] else "primary",
                )
            ]
            if index + 1 < len(years):
                year_value = years[index + 1]
                row_buttons.append(
                    _button(
                        f"📅 {year_value}",
                        callback_data=f"{PREFIX_DATE_PICKER}set_year:{year_value}",
                        kind="success" if year_value == data["year"] else "primary",
                    )
                )
            kb.row(*row_buttons)
    elif step == "month":
        for index, month_name in enumerate(MONTH_NAMES, start=1):
            kb.row(
                _button(
                    f"{index:02d} | {month_name}",
                    callback_data=f"{PREFIX_DATE_PICKER}set_month:{index}",
                    kind="success" if index == data["month"] else "primary",
                )
            )
        kb.row(_button("↩️ بازگشت به سال", callback_data=f"{PREFIX_DATE_PICKER}back:year"))
    elif step == "day":
        current_year = data["year"]
        current_month = data["month"]
        prev_year, prev_month = shift_month(current_year, current_month, -1)
        next_year, next_month = shift_month(current_year, current_month, 1)
        kb.row(
            _button("◀️ ماه قبل", callback_data=f"{PREFIX_DATE_PICKER}nav_month:-1"),
            _button("ماه بعد ▶️", callback_data=f"{PREFIX_DATE_PICKER}nav_month:1"),
        )
        days = days_in_month(current_year, current_month)
        row_buffer = []
        for day in range(1, days + 1):
            row_buffer.append(
                _button(
                    f"{day:02d}",
                    callback_data=f"{PREFIX_DATE_PICKER}set_day:{day}",
                    kind="success" if day == data["day"] else "primary",
                )
            )
            if len(row_buffer) == 5:
                kb.row(*row_buffer)
                row_buffer = []
        if row_buffer:
            kb.row(*row_buffer)
        kb.row(
            _button("امروز", callback_data=f"{PREFIX_DATE_PICKER}today:1", kind="success"),
            _button("↩️ بازگشت به ماه", callback_data=f"{PREFIX_DATE_PICKER}back:month"),
        )
    elif step == "hour":
        for start in range(0, 24, 4):
            kb.row(
                *[
                    _button(
                        f"{hour:02d}",
                        callback_data=f"{PREFIX_DATE_PICKER}set_hour:{hour}",
                        kind="success" if hour == data["hour"] else "primary",
                    )
                    for hour in range(start, min(start + 4, 24))
                ]
            )
        kb.row(_button("↩️ بازگشت به روز", callback_data=f"{PREFIX_DATE_PICKER}back:day"))
    elif step == "minute":
        for start in range(0, len(MINUTE_OPTIONS), 4):
            options = MINUTE_OPTIONS[start : start + 4]
            kb.row(
                *[
                    _button(
                        f"{minute:02d}",
                        callback_data=f"{PREFIX_DATE_PICKER}set_minute:{minute}",
                        kind="success" if minute == data["minute"] else "primary",
                    )
                    for minute in options
                ]
            )
        kb.row(_button("↩️ بازگشت به ساعت", callback_data=f"{PREFIX_DATE_PICKER}back:hour"))
    elif step == "confirm":
        kb.row(_button("✅ تایید نهایی", callback_data=f"{PREFIX_DATE_PICKER}confirm:1", kind="success"))
        kb.row(
            _button("↩️ تغییر دقیقه", callback_data=f"{PREFIX_DATE_PICKER}back:minute"),
            _button("پاک‌کردن", callback_data=f"{PREFIX_DATE_PICKER}clear:1", kind="danger"),
        )

    extra_row = []
    if data.get("allow_none"):
        extra_row.append(_button("⏭ بدون مقدار", callback_data=f"{PREFIX_DATE_PICKER}skip:1", kind="danger"))
    extra_row.append(_button("❌ لغو", callback_data=MENU_CANCEL, kind="danger"))
    kb.row(*extra_row)
    return kb.as_markup()
