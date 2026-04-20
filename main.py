"""
Aiogram bootstrap for the Inline-First Telegram bot.
"""

import asyncio
import logging

from bot.application import build_application
from config import bot_token
from db import ensure_students_seeded_from_default_csv, init_db


async def main() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    init_db()
    seed_result = ensure_students_seeded_from_default_csv()
    logging.info("students seed result: %s", seed_result)

    bot, dp = build_application(bot_token)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
