"""
Inline-First Telegram Bot bootstrap.
All inline flows, handlers, keyboards and text logic live under the `bot/` package.
"""

import logging

from bot.application import build_application
from config import bot_token
from db import ensure_students_seeded_from_default_csv, init_db


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    init_db()
    seed_result = ensure_students_seeded_from_default_csv()
    logging.info("students seed result: %s", seed_result)

    app = build_application(bot_token)
    app.run_polling()


if __name__ == "__main__":
    main()
