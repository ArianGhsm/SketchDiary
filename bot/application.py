from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.handlers import publish_scheduled_form, router
from bot.services.scheduler import build_scheduler, load_schedule_jobs


def build_application(bot_token: str) -> tuple[Bot, Dispatcher]:
    bot = Bot(
        token=bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )
    dp = Dispatcher()
    scheduler = build_scheduler()
    dp["scheduler"] = scheduler
    dp.include_router(router)

    async def schedule_runner(schedule_id: int) -> None:
        await publish_scheduled_form(bot, scheduler, schedule_id)

    dp["schedule_runner"] = schedule_runner

    async def on_startup(bot: Bot) -> None:
        load_schedule_jobs(scheduler, callback=schedule_runner)
        scheduler.start()

    async def on_shutdown(bot: Bot) -> None:
        scheduler.shutdown(wait=False)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    return bot, dp
