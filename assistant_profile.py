from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class AssistantProfile:
    code_name: str
    display_name: str
    target_group: str
    mission_statement: str
    active_modules: Tuple[str, ...]
    upcoming_modules: Tuple[str, ...]


PROFILE = AssistantProfile(
    code_name="dent-1402-assistant",
    display_name="دستیار دانشجویان دندان‌پزشکی ورودی ۱۴۰۲",
    target_group="دانشجویان دندان‌پزشکی ورودی ۱۴۰۲",
    mission_statement=(
        "یک دستیار آموزشی-دانشجویی برای مدیریت ثبت هویت، مشاهده نمرات، "
        "تحلیل عملکرد و توسعه تدریجی خدمات دانشجویی."
    ),
    active_modules=(
        "ثبت‌نام دانشجو",
        "پروفایل کاربر",
        "نمایش نمرات",
        "تحلیل میانگین و رتبه",
        "مدیریت ادمین برای حذف ثبت فعال",
        "پنل نماینده کلاس (ثبت گروهی نمره، اطلاعیه همگانی، فرم/لیست ثبت‌نام)",
    ),
    upcoming_modules=(
        "تقویم آموزشی و امتحانات",
        "منابع و جزوات",
        "پرسش و پاسخ متداول",
    ),
)
