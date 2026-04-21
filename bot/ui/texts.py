from __future__ import annotations

import json
from typing import Iterable

from bot.services.date_picker import MONTH_NAMES, picker_summary
from bot.services.datetime_fa import build_deadline_lines, render_telegram_time
from bot.services.formatting import code, e, html_list, info_card, labeled_row, quote_lines, status_badge


def _username_text(username: str | None) -> str:
    return code(f"@{username}") if username else code("ندارد")


def _form_kind_label(form_kind: str | None) -> str:
    labels = {
        "custom": "سفارشی",
        "quick_list": "سریع / جمع‌آوری لیست",
    }
    return labels.get(form_kind or "custom", "سفارشی")


def _channel_kind_label(channel_kind: str | None) -> str:
    labels = {
        "class": "اطلاع‌رسانی",
        "notes": "جزوه‌نویسی",
    }
    return labels.get(channel_kind or "class", "اطلاع‌رسانی")


def _channel_value(channel_id) -> str:
    return code(channel_id) if channel_id else code("تنظیم نشده")


def _registered_sort_label(sort_by: str) -> str:
    labels = {
        "approved_at_desc": "جدیدترین تایید",
        "approved_at_asc": "قدیمی‌ترین تایید",
        "student_number": "شماره دانشجویی",
        "name": "نام دانشجو",
    }
    return labels.get(sort_by, "جدیدترین تایید")


def home_text(verified: bool) -> str:
    if verified:
        return (
            "👋 <b>پنل اصلی آماده است.</b>\n"
            "همه‌ی بخش‌های دانشجویی و مدیریتی از دکمه‌های زیر در دسترس تو هستند."
        )
    return (
        "👋 <b>به SketchDiary خوش آمدی.</b>\n"
        "برای فعال‌شدن امکانات دانشجویی، احراز هویت را از همین‌جا شروع کن."
    )


def verification_intro_text() -> str:
    return info_card(
        "🔐 احراز هویت دانشجو",
        [
            "در این مرحله فقط شماره دانشجویی و یک معرفی کوتاه لازم است.",
            "ابتدا شماره دانشجویی را بفرست تا اطلاعاتت پیدا شود.",
            "بعد از تایید نماینده، حساب تلگرام به شماره دانشجویی متصل می‌شود و امکانات دانشجویی فعال خواهد شد.",
        ],
    )


def verification_request_message(request_row) -> str:
    return (
        info_card(
            "📢 درخواست تایید حساب جدید",
            [
                labeled_row("👤", "نام و نام خانوادگی", e(request_row["full_name"])),
                labeled_row("🎓", "شماره دانشجویی", code(request_row["student_number"])),
                labeled_row("🆔", "آیدی عددی تلگرام", code(request_row["telegram_user_id"])),
                labeled_row("🔗", "یوزرنیم تلگرام", _username_text(request_row["username"])),
                labeled_row("📝", "معرفی کوتاه", e(request_row["profile_text"])),
                render_telegram_time(request_row["requested_at"], "زمان ثبت درخواست"),
            ],
        )
        + "\n\n⚠️ تایید یک نماینده کافی است و بعد از تصمیم نهایی، نتیجه به دانشجو هم اعلام می‌شود."
    )


def profile_text(registered) -> str:
    return info_card(
        "👤 پروفایل تاییدشده",
        [
            labeled_row("👤", "نام", e(registered["full_name"])),
            labeled_row("🎓", "شماره دانشجویی", code(registered["student_number"])),
            labeled_row("🆔", "آیدی عددی تلگرام", code(registered["telegram_user_id"])),
            labeled_row("🔗", "یوزرنیم", _username_text(registered["username"])),
            labeled_row("📝", "معرفی کوتاه", e(registered["profile_text"])),
            render_telegram_time(registered["approved_at"], "زمان تایید"),
        ],
    )


def grades_text(registered, grades: dict, insights) -> str:
    items = [f"<b>{e(key)}:</b> {code(value)}" for key, value in grades.items()]
    analytics = [
        f"میانگین شما: {code(f'{insights.personal_average:.2f}')}" if insights.personal_average is not None else "میانگین شما: ناموجود",
        f"رتبه شما: {code(insights.rank_position)} از {code(insights.rank_total)}" if insights.rank_position is not None else "رتبه شما: ناموجود",
        f"میانگین کلاس: {code(f'{insights.class_average:.2f}')}" if insights.class_average is not None else "میانگین کلاس: ناموجود",
        f"فاصله با میانگین کلاس: {code(f'{insights.delta_from_class_average:+.2f}')}" if insights.delta_from_class_average is not None else "فاصله با میانگین کلاس: ناموجود",
    ]
    return (
        info_card(
            "📊 کارنامه و تحلیل عملکرد",
            [
                labeled_row("👤", "نام", e(registered["full_name"])),
                labeled_row("🎓", "شماره دانشجویی", code(registered["student_number"])),
            ],
        )
        + "\n\n<b>نمره‌ها</b>\n"
        + (html_list(items) if items else "هنوز نمره‌ای ثبت نشده است.")
        + "\n\n<b>تحلیل</b>\n"
        + html_list(analytics)
    )


def representative_panel_text(pending_count: int, form_count: int, schedule_count: int) -> str:
    return info_card(
        "🎓 پنل نماینده کلاس",
        [
            labeled_row("🟢", "درخواست‌های در انتظار", code(pending_count)),
            labeled_row("🗂", "فرم‌های شما", code(form_count)),
            labeled_row("⏰", "زمان‌بندی‌های فعال", code(schedule_count)),
        ],
    )


def pending_requests_text(rows: Iterable, page: int, total_pages: int) -> str:
    rows = list(rows)
    lines = [f"🟢 <b>درخواست‌های در انتظار</b> — صفحه {code(page)} از {code(total_pages)}", ""]
    if not rows:
        lines.append("در حال حاضر درخواست بازی برای بررسی وجود ندارد.")
        return "\n".join(lines)
    for row in rows:
        lines.append(
            quote_lines(
                [
                    labeled_row("👤", "نام", e(row["full_name"])),
                    labeled_row("🎓", "شماره دانشجویی", code(row["student_number"])),
                    labeled_row("🆔", "آیدی عددی", code(row["telegram_user_id"])),
                    labeled_row("🔗", "یوزرنیم", _username_text(row["username"])),
                    render_telegram_time(row["requested_at"], "زمان ثبت"),
                ]
            )
        )
    return "\n\n".join(lines)


def form_summary_text(form_row, stats: dict, questions: list, share_link: str | None = None) -> str:
    question_lines = []
    for index, question in enumerate(questions, start=1):
        options = json.loads(question["options_json"] or "[]")
        suffix = f" | گزینه‌ها: {e(' / '.join(options))}" if options else ""
        question_lines.append(
            f"{code(index)}. <b>{e(question['label'])}</b>\n"
            f"• نوع: {code(question['field_type'])}\n"
            f"• وضعیت: {code('اجباری' if question['is_required'] else 'اختیاری')}{suffix}"
        )

    share_block = ""
    if share_link:
        share_block = "\n" + quote_lines(
            [
                labeled_row("🔗", "لینک ورود دانشجو", code(share_link)),
                labeled_row("🧷", "توکن اشتراک", code(form_row["share_token"])),
            ]
        )

    return (
        info_card(
            "🗂 جزئیات فرم",
            [
                labeled_row("🗂", "عنوان", e(form_row["title"])),
                labeled_row("📝", "توضیح", e(form_row["description"] or "بدون توضیح")),
                labeled_row("🧭", "نوع فرم", code(_form_kind_label(form_row["form_kind"]))),
                labeled_row("📦", "ظرفیت", code(form_row["capacity"] or "نامحدود")),
                labeled_row("🚦", "وضعیت", status_badge(form_row["status"])),
                labeled_row("🪪", "Waitlist", code("فعال" if form_row["waitlist_enabled"] else "غیرفعال")),
                labeled_row("📣", "کانال انتشار", _channel_value(form_row["announcement_channel_id"])),
                render_telegram_time(form_row["created_at"], "زمان ساخت"),
                *build_deadline_lines(form_row["deadline_at"]),
            ],
        )
        + share_block
        + "\n\n<b>آمار ثبت‌نام</b>\n"
        + html_list(
            [
                f"تاییدشده: {code(stats['submitted_count'])}",
                f"لیست انتظار: {code(stats['waitlist_count'])}",
                f"حذف‌شده: {code(stats['removed_count'])}",
                f"کل رکوردها: {code(stats['total_count'])}",
            ]
        )
        + "\n\n<b>سوال‌ها</b>\n"
        + ("\n\n".join(question_lines) if question_lines else "هنوز سوالی ثبت نشده است.")
    )


def submissions_text(form_row, submissions: list, title: str = "ثبت‌نام‌ها") -> str:
    lines = [f"📋 <b>{e(title)}</b> — {e(form_row['title'])}", ""]
    if not submissions:
        lines.append("هیچ رکوردی پیدا نشد.")
        return "\n".join(lines)
    for row in submissions[:30]:
        lines.append(
            quote_lines(
                [
                    labeled_row("👤", "نام", e(row["full_name"])),
                    labeled_row("🎓", "شماره دانشجویی", code(row["student_number"])),
                    labeled_row("🔗", "یوزرنیم", _username_text(row["username"])),
                    labeled_row("🔢", "ترتیب ثبت", code(row["registration_order"])),
                    labeled_row("🚦", "وضعیت", status_badge(row["status"])),
                    render_telegram_time(row["submitted_at"], "زمان ثبت"),
                ]
            )
        )
    if len(submissions) > 30:
        lines.append(f"... و {len(submissions) - 30} مورد دیگر")
    return "\n\n".join(lines)


def form_join_text(form_row, questions: list) -> str:
    lines = [
        labeled_row("🗂", "عنوان", e(form_row["title"])),
        labeled_row("📝", "توضیح", e(form_row["description"] or "بدون توضیح")),
        labeled_row("🧭", "نوع فرم", code(_form_kind_label(form_row["form_kind"]))),
        labeled_row("❓", "تعداد سوال", code(len(questions))),
        labeled_row("🚦", "وضعیت", status_badge(form_row["status"])),
        *build_deadline_lines(form_row["deadline_at"]),
    ]
    if (form_row["form_kind"] or "custom") == "quick_list":
        lines.append("با تایید این مرحله، نام و شماره دانشجویی شما بدون سوال اضافه در لیست ثبت می‌شود.")
    return info_card(
        "🗂 فرم آماده پاسخ‌گویی است",
        lines,
    )


def ask_question_text(index: int, total: int, question_row) -> str:
    options = json.loads(question_row["options_json"] or "[]")
    option_block = html_list(e(option) for option in options)
    lines = [
        labeled_row("🔢", "ترتیب", f"{code(index)} از {code(total)}"),
        labeled_row("🧩", "نوع", code(question_row["field_type"])),
        labeled_row("📌", "الزام", code("اجباری" if question_row["is_required"] else "اختیاری")),
    ]
    if option_block:
        lines.append("<b>گزینه‌ها</b>\n" + option_block)
    return f"❓ <b>{e(question_row['label'])}</b>\n\n{quote_lines(lines)}"


def schedule_list_text(rows: Iterable, page: int, total_pages: int) -> str:
    rows = list(rows)
    lines = [f"⏰ <b>زمان‌بندی‌های ثبت‌شده</b> — صفحه {code(page)} از {code(total_pages)}", ""]
    if not rows:
        lines.append("هنوز زمان‌بندی فعالی ثبت نشده است.")
        return "\n".join(lines)
    for row in rows:
        lines.append(
            quote_lines(
                [
                    labeled_row("🆔", "شناسه", code(row["id"])),
                    labeled_row("📣", "کانال", code(row["channel_id"])),
                    labeled_row("🏷", "نوع کانال", code(_channel_kind_label(row["channel_kind"]))),
                    labeled_row("🔁", "تکرار", code(row["recurring_rule"] or "فقط یک‌بار")),
                    labeled_row("🚦", "وضعیت", code("فعال" if row["is_active"] else "غیرفعال")),
                    render_telegram_time(row["post_at"], "زمان انتشار"),
                    render_telegram_time(row["last_run_at"], "آخرین اجرا") if row["last_run_at"] else "",
                ]
            )
        )
    return "\n\n".join(lines)


def schedule_detail_text(schedule_row, template_form) -> str:
    return info_card(
        "⏰ جزئیات زمان‌بندی",
        [
            labeled_row("🆔", "شناسه", code(schedule_row["id"])),
            labeled_row("🗂", "فرم الگو", e(template_form["title"]) if template_form else code(schedule_row["template_form_id"])),
            labeled_row("📣", "کانال", code(schedule_row["channel_id"])),
            labeled_row("🏷", "نوع کانال", code(_channel_kind_label(schedule_row["channel_kind"]))),
            labeled_row("🔁", "تکرار", code(schedule_row["recurring_rule"] or "فقط یک‌بار")),
            labeled_row("🚦", "وضعیت", code("فعال" if schedule_row["is_active"] else "غیرفعال")),
            render_telegram_time(schedule_row["post_at"], "انتشار بعدی"),
            *build_deadline_lines(schedule_row["registration_deadline_at"]),
            render_telegram_time(schedule_row["last_run_at"], "آخرین اجرا") if schedule_row["last_run_at"] else "",
        ],
    )


def form_channel_settings_text(form_row, available_channels: list[tuple[str, int]]) -> str:
    lines = [
        labeled_row("🗂", "فرم", e(form_row["title"])),
        labeled_row("📣", "کانال انتخاب‌شده", _channel_value(form_row["announcement_channel_id"])),
    ]
    if available_channels:
        lines.append("<b>کانال‌های سراسری ذخیره‌شده</b>")
        for channel_kind, channel_id in available_channels:
            lines.append(f"• {_channel_kind_label(channel_kind)} — {code(channel_id)}")
    else:
        lines.append("هنوز کانال سراسری ثبت نشده است.")
    return (
        info_card(
            "📣 انتخاب کانال انتشار فرم",
            lines,
        )
        + "\n\nبرای هر فرم فقط مقصد انتشار را از بین کانال‌های سراسری انتخاب کن."
    )


def bot_channels_settings_text(channels: dict[str, int | None]) -> str:
    return (
        info_card(
            "📡 کانال‌های سراسری ربات",
            [
                labeled_row("📣", "اطلاع‌رسانی", _channel_value(channels.get("class"))),
                labeled_row("📝", "جزوه", _channel_value(channels.get("notes"))),
            ],
        )
        + "\n\nاین کانال‌ها یک‌بار برای کل ربات ذخیره می‌شوند و فرم‌ها فقط مقصد خود را از بین همین‌ها انتخاب می‌کنند."
    )


def form_delete_confirmation_text(form_row) -> str:
    return (
        info_card(
            "🗑 تایید حذف کامل فرم",
            [
                labeled_row("🗂", "عنوان", e(form_row["title"])),
                labeled_row("🧭", "نوع فرم", code(_form_kind_label(form_row["form_kind"]))),
                labeled_row("🚦", "وضعیت", status_badge(form_row["status"])),
                render_telegram_time(form_row["created_at"], "زمان ساخت"),
            ],
        )
        + "\n\n⚠️ با حذف فرم، سوال‌ها، پاسخ‌ها و زمان‌بندی‌های وابسته هم حذف می‌شوند."
    )


def admin_panel_text(recent_rows: Iterable, total_students: int) -> str:
    recent_rows = list(recent_rows)
    lines = [labeled_row("👥", "دانشجوهای تاییدشده", code(total_students))]
    if recent_rows:
        lines.append("<b>ثبت‌های اخیر</b>")
        for row in recent_rows:
            lines.append(
                f"• <b>{e(row['full_name'])}</b> — {code(row['student_number'])} — {render_telegram_time(row['approved_at'], 'زمان تایید')}"
            )
    else:
        lines.append("هنوز ثبت تاییدشده‌ای وجود ندارد.")
    return "🛠 <b>پنل مدیریت</b>\n\n" + "\n".join(lines)


def registered_students_text(
    rows: Iterable,
    page: int,
    total_pages: int,
    total_students: int,
    *,
    query: str | None = None,
    sort_by: str = "approved_at_desc",
) -> str:
    rows = list(rows)
    lines = [
        f"👥 <b>دانشجوهای تاییدشده</b> — صفحه {code(page)} از {code(total_pages)}",
        f"مجموع فعال: {code(total_students)}",
        f"↕️ مرتب‌سازی: {code(_registered_sort_label(sort_by))}",
    ]
    if query:
        lines.append(f"🔎 جستجو: {code(query)}")
    lines.append("")
    if not rows:
        lines.append("دانشجوی فعالی برای نمایش وجود ندارد.")
        return "\n".join(lines)
    for row in rows:
        lines.append(
            quote_lines(
                [
                    labeled_row("👤", "نام", e(row["full_name"])),
                    labeled_row("🎓", "شماره دانشجویی", code(row["student_number"])),
                    labeled_row("🆔", "آیدی عددی", code(row["telegram_user_id"])),
                    labeled_row("🔗", "یوزرنیم", _username_text(row["username"])),
                    render_telegram_time(row["approved_at"], "زمان تایید"),
                ]
            )
        )
    return "\n\n".join(lines)


def admin_remove_confirmation_text(registered) -> str:
    return (
        info_card(
            "🗑 تایید غیرفعال‌سازی ثبت فعال",
            [
                labeled_row("👤", "نام", e(registered["full_name"])),
                labeled_row("🎓", "شماره دانشجویی", code(registered["student_number"])),
                labeled_row("🆔", "آیدی عددی", code(registered["telegram_user_id"])),
                labeled_row("🔗", "یوزرنیم", _username_text(registered["username"])),
                render_telegram_time(registered["approved_at"], "زمان تایید فعلی"),
            ],
        )
        + "\n\n⚠️ این عملیات دسترسی فعال این حساب را قطع می‌کند و دانشجو باید دوباره احراز هویت را طی کند."
    )


def date_picker_text(data: dict) -> str:
    step_titles = {
        "year": "انتخاب سال",
        "month": "انتخاب ماه",
        "day": "انتخاب روز",
        "hour": "انتخاب ساعت",
        "minute": "انتخاب دقیقه",
        "confirm": "تایید نهایی",
    }
    month_label = MONTH_NAMES[data["month"] - 1]
    selection_lines = [
        labeled_row("🗂", "فیلد", e(data["label"])),
        labeled_row("📅", "سال", code(data["year"])),
        labeled_row("🗓", "ماه", code(f"{data['month']:02d} | {month_label}")),
        labeled_row("📌", "روز", code(f"{data['day']:02d}")),
        labeled_row("🕒", "ساعت", code(f"{data['hour']:02d}:{data['minute']:02d}")),
        labeled_row("📍", "منطقه زمانی", code("تهران")),
        labeled_row("✅", "انتخاب فعلی", code(picker_summary(data))),
    ]
    return (
        f"🧭 <b>{step_titles.get(data['step'], 'انتخاب زمان')}</b>\n\n"
        + quote_lines(selection_lines)
        + "\n\nاز دکمه‌های زیر استفاده کن. تا جای ممکن نیازی به تایپ نیست."
    )
