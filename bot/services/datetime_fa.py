from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
from zoneinfo import ZoneInfo

import jdatetime

from bot.services.formatting import code, e
from bot.services.localization import fa


TEHRAN_TZ = ZoneInfo("Asia/Tehran")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat(timespec="seconds")


def parse_db_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_tehran(dt: datetime) -> datetime:
    return ensure_utc(dt).astimezone(TEHRAN_TZ)


def _jalali_parts(dt: datetime) -> tuple[str, str]:
    tehran_dt = to_tehran(dt)
    jalali_dt = jdatetime.datetime.fromgregorian(datetime=tehran_dt)
    return (
        fa(f"{jalali_dt.year:04d}/{jalali_dt.month:02d}/{jalali_dt.day:02d}"),
        fa(f"{jalali_dt.hour:02d}:{jalali_dt.minute:02d}"),
    )


def format_datetime_fa(value: str | datetime | None) -> str:
    if value is None:
        return "نامشخص"
    dt = parse_db_datetime(value) if isinstance(value, str) else ensure_utc(value)
    if dt is None:
        return "نامشخص"
    date_text, time_text = _jalali_parts(dt)
    return f"{date_text} - {time_text}"


def render_telegram_time(value: str | datetime | None, label: str = "زمان") -> str:
    if value is None:
        return f"🕒 <b>{e(label)}:</b> نامشخص"
    dt = parse_db_datetime(value) if isinstance(value, str) else ensure_utc(value)
    if dt is None:
        return f"🕒 <b>{e(label)}:</b> نامشخص"
    date_text, time_text = _jalali_parts(dt)
    visible = code(f"{date_text} - {time_text}")
    return (
        f"🕒 <b>{e(label)}:</b> "
        f"<tg-time unix=\"{int(dt.timestamp())}\">{visible}</tg-time> "
        f"به وقت تهران"
    )


def format_datetime_block(value: str | datetime | None, label: str = "زمان") -> str:
    if value is None:
        return f"🕒 <b>{e(label)}:</b> نامشخص"
    dt = parse_db_datetime(value) if isinstance(value, str) else ensure_utc(value)
    if dt is None:
        return f"🕒 <b>{e(label)}:</b> نامشخص"
    date_text, time_text = _jalali_parts(dt)
    return (
        f"🗓 <b>تاریخ:</b> {code(date_text)}\n"
        f"🕒 <b>ساعت:</b> {code(time_text)}\n"
        f"📍 <b>منطقه زمانی:</b> {code('تهران')}"
    )


def format_relative_time_fa(value: str | datetime | None, now: datetime | None = None) -> str:
    if value is None:
        return "نامشخص"
    dt = parse_db_datetime(value) if isinstance(value, str) else ensure_utc(value)
    if dt is None:
        return "نامشخص"
    baseline = ensure_utc(now or utc_now())
    delta = dt - baseline
    total_seconds = int(delta.total_seconds())
    if total_seconds <= 0:
        return "پایان‌یافته"

    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60

    parts: list[str] = []
    if days:
        parts.append(f"{fa(days)} روز")
    if hours:
        parts.append(f"{fa(hours)} ساعت")
    if minutes and not days:
        parts.append(f"{fa(minutes)} دقیقه")
    return " و ".join(parts) if parts else "کمتر از یک دقیقه"


def build_deadline_lines(value: str | datetime | None) -> list[str]:
    if value is None:
        return []
    return [
        f"⏳ <b>زمان باقی‌مانده:</b> {e(format_relative_time_fa(value))}",
        f"🗓 <b>مهلت نهایی:</b> {render_telegram_time(value, 'مهلت ثبت‌نام')}",
    ]
