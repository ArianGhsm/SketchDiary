from assistant_profile import PROFILE


def help_text(admin: bool, rep: bool, verified: bool) -> str:
    active_modules = "\n".join(f"• {module}" for module in PROFILE.active_modules)
    upcoming_modules = "\n".join(f"• {module}" for module in PROFILE.upcoming_modules)

    text = (
        f"📌 {PROFILE.display_name}\n\n"
        f"🎯 گروه هدف: {PROFILE.target_group}\n"
        f"🧭 ماموریت: {PROFILE.mission_statement}\n\n"
        "✅ مسیر فعلی:\n"
        "۱) روی «🔐 احراز هویت» بزن\n"
        "۲) شماره دانشجویی را بفرست\n"
        "۳) مشخصات تکمیلی را ارسال کن\n"
        "۴) بعد از احراز هویت، منوی کامل فعال می‌شود\n\n"
        "🧩 ماژول‌های فعال:\n"
        f"{active_modules}\n\n"
        "🚀 ماژول‌های برنامه‌ریزی‌شده:\n"
        f"{upcoming_modules}"
    )

    if admin:
        text += "\n\n🛠️ دسترسی ادمین:\n• پنل ادمین\n• حذف دانشجو"
    if rep:
        text += "\n\n🎓 دسترسی نماینده:\n• پنل نماینده کلاس"
    if not verified:
        text += "\n\n🔒 تا قبل از احراز هویت، فقط مسیر احراز و راهنما فعال است."

    return text


def admin_help_text() -> str:
    return (
        "🛠️ راهنمای ادمین\n\n"
        "• با «🗑️ حذف دانشجو» ثبت فعال یک شماره دانشجویی غیرفعال می‌شود.\n"
        "• بعد از حذف، دانشجو می‌تواند دوباره احراز هویت کند."
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
        "• هر لحظه با دکمه بروزرسانی، لیست اعضا را لحظه‌ای می‌بینی."
    )


def welcome_text(verified: bool) -> str:
    if verified:
        return (
            f"👋 به {PROFILE.display_name} خوش آمدی.\n"
            "از منوی زیر گزینه موردنظرت را انتخاب کن:"
        )

    return (
        f"👋 به {PROFILE.display_name} خوش آمدی.\n"
        "🔐 برای ورود به امکانات ربات، ابتدا احراز هویت را انجام بده."
    )


def profile_text(registered) -> str:
    return (
        "📄 اطلاعات ثبت‌شده شما:\n"
        f"🎓 شماره دانشجویی: {registered['student_number']}\n"
        f"🧑‍🎓 نام کامل: {registered['full_name']}\n"
        f"📝 مشخصات: {registered['profile_text']}\n"
        f"🕒 تاریخ ثبت: {registered['registered_at']} UTC"
    )


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
        lines.append(f"{idx}) {entry['full_name']} - {entry['student_number']}")

    if len(entries) > max_show:
        lines.append(f"... و {len(entries) - max_show} نفر دیگر")

    return "\n".join(lines)
