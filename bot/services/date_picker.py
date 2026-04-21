from __future__ import annotations

from datetime import datetime, timezone

import jdatetime

from bot.services.datetime_fa import TEHRAN_TZ, format_datetime_fa


MONTH_NAMES = [
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
]

MINUTE_OPTIONS = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]


def now_jalali() -> jdatetime.datetime:
    tehran_now = datetime.now(TEHRAN_TZ)
    return jdatetime.datetime.fromgregorian(datetime=tehran_now)


def default_picker_state(target: str, label: str, allow_none: bool) -> dict:
    now = now_jalali()
    return {
        "target": target,
        "label": label,
        "allow_none": allow_none,
        "step": "year",
        "year": now.year,
        "month": now.month,
        "day": now.day,
        "hour": now.hour,
        "minute": (now.minute // 5) * 5,
        "year_base": now.year - 1,
    }


def days_in_month(year: int, month: int) -> int:
    if month <= 6:
        return 31
    if month <= 11:
        return 30
    return 30 if jdatetime.date(year, month, 1).isleap() else 29


def clamp_day(year: int, month: int, day: int) -> int:
    return max(1, min(day, days_in_month(year, month)))


def shift_month(year: int, month: int, offset: int) -> tuple[int, int]:
    month_index = (year * 12 + (month - 1)) + offset
    new_year = month_index // 12
    new_month = month_index % 12 + 1
    return new_year, new_month


def picker_summary(data: dict) -> str:
    selection = jalali_selection_to_utc_iso(data["year"], data["month"], data["day"], data["hour"], data["minute"])
    return format_datetime_fa(selection)


def jalali_selection_to_utc_iso(year: int, month: int, day: int, hour: int, minute: int) -> str:
    gregorian = jdatetime.datetime(year, month, day, hour, minute).togregorian()
    tehran_dt = gregorian.replace(tzinfo=TEHRAN_TZ)
    return tehran_dt.astimezone(timezone.utc).isoformat(timespec="seconds")
