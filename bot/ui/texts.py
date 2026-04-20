from __future__ import annotations

from typing import Iterable

from bot.services.datetime_fa import build_deadline_lines, render_telegram_time
from bot.services.formatting import bold, code, e, html_list, labeled_row, quote_lines


def welcome_text(verified: bool) -> str:
    if verified:
        return (
            "👋 <b>پنل دانشجویی آماده است.</b>\n"
            "از دکمه‌های زیر استفاده کن و هر زمان خواستی به منوی اصلی برگرد."
        )
    return (
        "👋 <b>خوش آمدی.</b>\n"
        "برای فعال‌شدن قابلیت‌های دانشجویی، احراز هویت را از همین‌جا شروع کن."
    )


def verification_intro_text() -> str:
    return (
        "🔐 <b>شروع احراز هویت</b>\n"
        "در این مرحله فقط شماره دانشجویی‌ات را می‌گیریم. بعد از آن یک معرفی کوتاه می‌فرستی "
        "تا برای نماینده کلاس جهت تایید ارسال شود."
    )


def already_verified_text(registered) -> str:
    return (
        "✅ <b>حساب شما قبلا تایید شده است.</b>\n\n"
        + quote_lines(
            [
                labeled_row("👤", "نام", e(registered["full_name"])),
                labeled_row("🎓", "شماره دانشجویی", code(registered["student_number"])),
                labeled_row("🆔", "آیدی عددی", code(registered["telegram_user_id"])),
                labeled_row("🔗", "یوزرنیم", code("@" + registered["username"]) if registered["username"] else code("ندارد")),
                render_telegram_time(registered["approved_at"], "زمان تایید"),
            ]
        )
    )


def verification_request_submitted_text(student, request_id: int) -> str:
    return (
        "📨 <b>درخواست احراز هویت ثبت شد.</b>\n"
        "درخواست شما برای نماینده کلاس ارسال شده و بعد از بررسی نتیجه همین‌جا اعلام می‌شود.\n\n"
        + quote_lines(
            [
                labeled_row("👤", "نام", e(student["full_name"])),
                labeled_row("🎓", "شماره دانشجویی", code(student["student_number"])),
                labeled_row("🧾", "کد درخواست", code(request_id)),
            ]
        )
    )


def verification_request_message(request_row) -> str:
    username_text = code(f"@{request_row['username']}") if request_row["username"] else code("ندارد")
    return (
        "📢 <b>درخواست تایید حساب جدید</b>\n"
        "آیا این حساب را برای این دانشجو تایید می‌کنی؟\n\n"
        + quote_lines(
            [
                labeled_row("👤", "نام و نام خانوادگی", e(request_row["full_name"])),
                labeled_row("🎓", "شماره دانشجویی", code(request_row["student_number"])),
                labeled_row("🆔", "آیدی عددی تلگرام", code(request_row["telegram_user_id"])),
                labeled_row("🔗", "یوزرنیم تلگرام", username_text),
                labeled_row("📝", "معرفی", e(request_row["profile_text"])),
                render_telegram_time(request_row["requested_at"], "زمان درخواست"),
            ]
        )
        + "\n\n⚠️ تایید یک نماینده کافی است و پس از آن حساب دانشجو فعال می‌شود."
    )


def verification_approved_student_text(request_row) -> str:
    return (
        "✅ <b>احراز هویت شما تایید شد.</b>\n"
        "اکنون می‌توانی از امکانات دانشجویی ربات استفاده کنی.\n\n"
        + quote_lines(
            [
                labeled_row("👤", "نام", e(request_row["full_name"])),
                labeled_row("🎓", "شماره دانشجویی", code(request_row["student_number"])),
                render_telegram_time(request_row["reviewed_at"], "زمان تایید"),
            ]
        )
    )


def verification_rejected_student_text(request_row) -> str:
    note = request_row["reviewer_note"] or "برای بررسی مجدد، احراز هویت را دوباره از منوی اصلی شروع کن."
    return (
        "❌ <b>درخواست احراز هویت رد شد.</b>\n"
        f"{e(note)}\n\n"
        + quote_lines(
            [
                labeled_row("👤", "نام", e(request_row["full_name"])),
                labeled_row("🎓", "شماره دانشجویی", code(request_row["student_number"])),
                render_telegram_time(request_row["reviewed_at"], "زمان بررسی"),
            ]
        )
    )


def profile_text(registered) -> str:
    username_text = code(f"@{registered['username']}") if registered["username"] else code("ندارد")
    return (
        "👤 <b>پروفایل ثبت‌شده</b>\n\n"
        + quote_lines(
            [
                labeled_row("👤", "نام کامل", e(registered["full_name"])),
                labeled_row("🎓", "شماره دانشجویی", code(registered["student_number"])),
                labeled_row("🆔", "آیدی عددی تلگرام", code(registered["telegram_user_id"])),
                labeled_row("🔗", "یوزرنیم", username_text),
                labeled_row("📝", "معرفی", e(registered["profile_text"])),
                render_telegram_time(registered["approved_at"], "زمان تایید"),
            ]
        )
    )


def admin_panel_text(recent_rows: Iterable) -> str:
    lines = ["🛠 <b>پنل مدیریت</b>", "برای حذف ثبت فعال، شماره دانشجویی را در مرحله بعد می‌فرستی."]
    if recent_rows:
        lines.append("")
        lines.append("<b>آخرین ثبت‌های فعال</b>")
        for row in recent_rows:
            lines.append(
                f"• {e(row['full_name'])} — {code(row['student_number'])} — "
                f"{render_telegram_time(row['approved_at'], 'تایید')}"
            )
    return "\n".join(lines)


def representative_panel_text(pending_count: int) -> str:
    return (
        "🎓 <b>پنل نماینده کلاس</b>\n"
        "اقدام موردنظرت را از همین‌جا انتخاب کن.\n\n"
        + quote_lines([labeled_row("🟢", "درخواست‌های در انتظار", code(pending_count))])
    )


def pending_requests_text(rows: Iterable) -> str:
    rows = list(rows)
    lines = ["🟢 <b>درخواست‌های در انتظار بررسی</b>"]
    if not rows:
        lines.append("در حال حاضر درخواست بازی وجود ندارد.")
        return "\n".join(lines)
    for row in rows:
        lines.append(
            "• "
            + e(row["full_name"])
            + " — "
            + code(row["student_number"])
            + " — "
            + render_telegram_time(row["requested_at"], "درخواست")
        )
    return "\n".join(lines)


def grade_report_text(registered, grades: dict, insights) -> str:
    grade_lines = [f"• <b>{e(key)}:</b> {code(value)}" for key, value in grades.items()]
    rank_text = (
        f"{code(insights.rank_position)} از {code(insights.rank_total)}"
        if insights.rank_position is not None
        else "ناموجود"
    )
    return (
        "📊 <b>کارنامه و تحلیل</b>\n\n"
        + quote_lines(
            [
                labeled_row("👤", "نام", e(registered["full_name"])),
                labeled_row("🎓", "شماره دانشجویی", code(registered["student_number"])),
            ]
        )
        + "\n\n<b>نمره‌ها</b>\n"
        + ("\n".join(grade_lines) if grade_lines else "هنوز نمره‌ای ثبت نشده است.")
        + "\n\n<b>تحلیل عملکرد</b>\n"
        + html_list(
            [
                f"میانگین شما: {code(f'{insights.personal_average:.2f}')}" if insights.personal_average is not None else "میانگین شما: ناموجود",
                f"رتبه در کلاس: {rank_text}",
                f"میانگین کلاس: {code(f'{insights.class_average:.2f}')}" if insights.class_average is not None else "میانگین کلاس: ناموجود",
                f"اختلاف با میانگین کلاس: {code(f'{insights.delta_from_class_average:+.2f}')}" if insights.delta_from_class_average is not None else "اختلاف با میانگین کلاس: ناموجود",
                f"دانشجوی برتر: {e(insights.top_student_name)} با میانگین {code(f'{insights.top_student_average:.2f}')}" if insights.top_student_name and insights.top_student_average is not None else "دانشجوی برتر: ناموجود",
            ]
        )
    )


def form_created_text(title: str, description: str, form_id: int, join_url: str, deadline_at: str | None) -> str:
    lines = [
        "✅ <b>فرم/لیست جدید ساخته شد.</b>",
        "",
        quote_lines(
            [
                labeled_row("🗂", "عنوان", e(title)),
                labeled_row("🆔", "شناسه فرم", code(form_id)),
                labeled_row("📝", "توضیح", e(description or "بدون توضیح")),
                *build_deadline_lines(deadline_at),
            ]
        ),
        "",
        f"🔗 <b>لینک عضویت:</b> {code(join_url)}",
    ]
    return "\n".join(lines)


def form_join_confirm_text(form_row) -> str:
    return (
        "🗂 <b>درخواست عضویت در فرم</b>\n\n"
        + quote_lines(
            [
                labeled_row("🗂", "عنوان", e(form_row["title"])),
                labeled_row("📝", "توضیح", e(form_row["description"] or "بدون توضیح")),
                render_telegram_time(form_row["created_at"], "زمان ساخت"),
                *build_deadline_lines(form_row["deadline_at"]),
            ]
        )
        + "\n\nآیا عضویت در این فرم را تایید می‌کنی؟"
    )


def format_rep_form_members(form_row, entries) -> str:
    lines = [
        "📚 <b>نمای فرم</b>",
        "",
        quote_lines(
            [
                labeled_row("🗂", "عنوان", e(form_row["title"])),
                labeled_row("🆔", "شناسه فرم", code(form_row["id"])),
                labeled_row("📝", "توضیح", e(form_row["description"] or "بدون توضیح")),
                render_telegram_time(form_row["created_at"], "زمان ساخت"),
                *build_deadline_lines(form_row["deadline_at"]),
                labeled_row("👥", "تعداد اعضا", code(len(entries))),
            ]
        ),
        "",
        "<b>اعضای فعلی</b>",
    ]

    if not entries:
        lines.append("هنوز عضوی ثبت نشده است.")
        return "\n".join(lines)

    for index, entry in enumerate(entries, start=1):
        username_text = f" — {code('@' + entry['username'])}" if entry["username"] else ""
        lines.append(
            f"{e(index)}. {bold(entry['full_name'])} — {code(entry['student_number'])}{username_text}\n"
            f"{render_telegram_time(entry['joined_at'], 'زمان عضویت')}"
        )
    return "\n".join(lines)
