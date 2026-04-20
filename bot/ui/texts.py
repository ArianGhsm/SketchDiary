from __future__ import annotations

import json
from typing import Iterable

from bot.services.datetime_fa import build_deadline_lines, render_telegram_time
from bot.services.formatting import code, e, labeled_row, quote_lines


def home_text(verified: bool) -> str:
    if verified:
        return "👋 <b>پنل اصلی آماده است.</b>\nاز دکمه‌های زیر استفاده کن."
    return "👋 <b>خوش آمدی.</b>\nبرای ورود کامل، احراز هویت را شروع کن."


def verification_intro_text() -> str:
    return (
        "🔐 <b>احراز هویت دانشجو</b>\n"
        "شماره دانشجویی را می‌گیریم، سپس یک معرفی کوتاه از شما دریافت می‌کنیم و درخواست برای نماینده ارسال می‌شود."
    )


def verification_request_message(request_row) -> str:
    username_text = code(f"@{request_row['username']}") if request_row["username"] else code("ندارد")
    return (
        "📢 <b>درخواست تایید حساب جدید</b>\n\n"
        + quote_lines(
            [
                labeled_row("👤", "نام", e(request_row["full_name"])),
                labeled_row("🎓", "شماره دانشجویی", code(request_row["student_number"])),
                labeled_row("🆔", "آیدی عددی", code(request_row["telegram_user_id"])),
                labeled_row("🔗", "یوزرنیم", username_text),
                labeled_row("📝", "معرفی", e(request_row["profile_text"])),
                render_telegram_time(request_row["requested_at"], "زمان درخواست"),
            ]
        )
        + "\n\n⚠️ تایید یک نماینده کافی است."
    )


def profile_text(registered) -> str:
    username_text = code(f"@{registered['username']}") if registered["username"] else code("ندارد")
    return (
        "👤 <b>پروفایل تاییدشده</b>\n\n"
        + quote_lines(
            [
                labeled_row("👤", "نام", e(registered["full_name"])),
                labeled_row("🎓", "شماره دانشجویی", code(registered["student_number"])),
                labeled_row("🆔", "آیدی عددی", code(registered["telegram_user_id"])),
                labeled_row("🔗", "یوزرنیم", username_text),
                labeled_row("📝", "معرفی", e(registered["profile_text"])),
                render_telegram_time(registered["approved_at"], "زمان تایید"),
            ]
        )
    )


def grades_text(registered, grades: dict, insights) -> str:
    items = [f"• <b>{e(key)}:</b> {code(value)}" for key, value in grades.items()]
    analytics = [
        f"• میانگین شما: {code(f'{insights.personal_average:.2f}')}" if insights.personal_average is not None else "• میانگین شما: ناموجود",
        f"• رتبه شما: {code(insights.rank_position)} از {code(insights.rank_total)}" if insights.rank_position is not None else "• رتبه شما: ناموجود",
        f"• میانگین کلاس: {code(f'{insights.class_average:.2f}')}" if insights.class_average is not None else "• میانگین کلاس: ناموجود",
        f"• فاصله با میانگین کلاس: {code(f'{insights.delta_from_class_average:+.2f}')}" if insights.delta_from_class_average is not None else "• فاصله با میانگین کلاس: ناموجود",
    ]
    return (
        "📊 <b>کارنامه و تحلیل عملکرد</b>\n\n"
        + quote_lines(
            [
                labeled_row("👤", "نام", e(registered["full_name"])),
                labeled_row("🎓", "شماره دانشجویی", code(registered["student_number"])),
            ]
        )
        + "\n\n<b>نمره‌ها</b>\n"
        + ("\n".join(items) if items else "هنوز نمره‌ای ثبت نشده است.")
        + "\n\n<b>تحلیل</b>\n"
        + "\n".join(analytics)
    )


def representative_panel_text(pending_count: int, form_count: int, schedule_count: int) -> str:
    return (
        "🎓 <b>پنل نماینده کلاس</b>\n\n"
        + quote_lines(
            [
                labeled_row("🟢", "درخواست‌های در انتظار", code(pending_count)),
                labeled_row("🗂", "فرم‌های شما", code(form_count)),
                labeled_row("⏰", "زمان‌بندی‌های فعال", code(schedule_count)),
            ]
        )
    )


def pending_requests_text(rows: Iterable, page: int) -> str:
    rows = list(rows)
    lines = [f"🟢 <b>درخواست‌های در انتظار - صفحه {code(page)}</b>"]
    if not rows:
        lines.append("در حال حاضر درخواست بازی وجود ندارد.")
        return "\n".join(lines)
    for row in rows:
        lines.append(
            f"• {e(row['full_name'])} — {code(row['student_number'])} — {render_telegram_time(row['requested_at'], 'ثبت')}"
        )
    return "\n".join(lines)


def form_summary_text(form_row, stats: dict, questions: list) -> str:
    question_lines = []
    for index, question in enumerate(questions, start=1):
        options = json.loads(question["options_json"] or "[]")
        suffix = f" ({', '.join(options)})" if options else ""
        question_lines.append(f"{index}. {question['label']} — {question['field_type']}{suffix}")
    return (
        "🗂 <b>جزئیات فرم</b>\n\n"
        + quote_lines(
            [
                labeled_row("🗂", "عنوان", e(form_row["title"])),
                labeled_row("📝", "توضیح", e(form_row["description"] or "بدون توضیح")),
                labeled_row("🔗", "توکن اشتراک", code(form_row["share_token"])),
                labeled_row("📦", "ظرفیت", code(form_row["capacity"] or "نامحدود")),
                labeled_row("🪪", "Waitlist", code("فعال" if form_row["waitlist_enabled"] else "غیرفعال")),
                render_telegram_time(form_row["created_at"], "زمان ساخت"),
                *build_deadline_lines(form_row["deadline_at"]),
            ]
        )
        + "\n\n<b>آمار ثبت‌نام</b>\n"
        + "\n".join(
            [
                f"• تاییدشده: {code(stats['submitted_count'])}",
                f"• لیست انتظار: {code(stats['waitlist_count'])}",
                f"• حذف‌شده: {code(stats['removed_count'])}",
                f"• کل رکوردها: {code(stats['total_count'])}",
            ]
        )
        + "\n\n<b>سوال‌ها</b>\n"
        + ("\n".join(question_lines) if question_lines else "هنوز سوالی ثبت نشده است.")
    )


def submissions_text(form_row, submissions: list, title: str = "ثبت‌نام‌ها") -> str:
    lines = [f"📋 <b>{title}</b> — {e(form_row['title'])}", ""]
    if not submissions:
        lines.append("هیچ رکوردی پیدا نشد.")
        return "\n".join(lines)
    for row in submissions[:30]:
        username = f" — {code('@' + row['username'])}" if row["username"] else ""
        lines.append(
            f"{code(row['registration_order'])}. <b>{e(row['full_name'])}</b> — {code(row['student_number'])}{username}\n"
            f"• وضعیت: {code(row['status'])}\n"
            f"• زمان ثبت: {render_telegram_time(row['submitted_at'], 'ثبت')}"
        )
    if len(submissions) > 30:
        lines.append(f"... و {len(submissions) - 30} مورد دیگر")
    return "\n".join(lines)


def form_join_text(form_row, questions: list) -> str:
    return (
        "🗂 <b>فرم آماده پاسخ‌گویی است</b>\n\n"
        + quote_lines(
            [
                labeled_row("🗂", "عنوان", e(form_row["title"])),
                labeled_row("📝", "توضیح", e(form_row["description"] or "بدون توضیح")),
                labeled_row("❓", "تعداد سوال", code(len(questions))),
                *build_deadline_lines(form_row["deadline_at"]),
            ]
        )
    )


def ask_question_text(index: int, total: int, question_row) -> str:
    options = json.loads(question_row["options_json"] or "[]")
    option_block = "\n".join(f"• {e(option)}" for option in options)
    text = (
        f"❓ <b>سوال {code(index)} از {code(total)}</b>\n\n"
        f"{e(question_row['label'])}\n"
        f"• نوع: {code(question_row['field_type'])}\n"
        f"• وضعیت: {code('اجباری' if question_row['is_required'] else 'اختیاری')}"
    )
    if option_block:
        text += "\n\n<b>گزینه‌ها</b>\n" + option_block
    return text


def schedule_list_text(rows: Iterable) -> str:
    rows = list(rows)
    lines = ["⏰ <b>زمان‌بندی‌های ثبت‌شده</b>"]
    if not rows:
        lines.append("هنوز زمان‌بندی فعالی ثبت نشده است.")
        return "\n".join(lines)
    for row in rows:
        lines.append(
            f"• شناسه {code(row['id'])} — کانال {code(row['channel_id'])} — {render_telegram_time(row['post_at'], 'ارسال')}"
        )
    return "\n".join(lines)
