from __future__ import annotations

from datetime import timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

from bot.services.datetime_fa import TEHRAN_TZ, parse_db_datetime
from db import get_schedule, list_form_schedules


def build_scheduler() -> AsyncIOScheduler:
    return AsyncIOScheduler(timezone=TEHRAN_TZ)


def load_schedule_jobs(scheduler: AsyncIOScheduler, callback) -> None:
    for row in list_form_schedules(active_only=True):
        schedule_job(scheduler, row["id"], row["post_at"], callback)


def schedule_job(scheduler: AsyncIOScheduler, schedule_id: int, post_at: str, callback) -> None:
    run_at = parse_db_datetime(post_at)
    if run_at is None:
        return
    scheduler.add_job(
        callback,
        trigger=DateTrigger(run_date=run_at),
        args=[schedule_id],
        id=f"schedule:{schedule_id}",
        replace_existing=True,
    )


def next_recurring_post(post_at: str, recurring_rule: str | None) -> str | None:
    if not recurring_rule:
        return None
    current = parse_db_datetime(post_at)
    if current is None:
        return None
    if recurring_rule == "weekly":
        return (current + timedelta(days=7)).isoformat(timespec="seconds")
    if recurring_rule == "monthly":
        return (current + timedelta(days=30)).isoformat(timespec="seconds")
    return None
