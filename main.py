"""
Aiogram bootstrap for the Inline-First Telegram bot.
"""

import asyncio
import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from aiogram.exceptions import TelegramConflictError

from bot.application import build_application
from config import DATA_DIR, bot_token
from db import ensure_students_seeded_from_default_csv, init_db


POLLING_LOCK_PATH = DATA_DIR / "bot.polling.lock"


def _is_process_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


@contextmanager
def polling_instance_lock(lock_path: Path) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:
                existing_pid = int(lock_path.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                existing_pid = None

            if existing_pid and _is_process_running(existing_pid):
                raise RuntimeError(
                    f"Polling lock is already held by PID {existing_pid}. "
                    "Only one local bot instance can use getUpdates at a time."
                )

            try:
                lock_path.unlink()
            except FileNotFoundError:
                continue

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as lock_file:
            lock_file.write(str(os.getpid()))
        yield
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


async def main() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    init_db()
    seed_result = ensure_students_seeded_from_default_csv()
    logging.info("students seed result: %s", seed_result)

    bot, dp = build_application(bot_token)
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        with polling_instance_lock(POLLING_LOCK_PATH):
            await dp.start_polling(bot)
    except RuntimeError as exc:
        logging.error("%s", exc)
        raise
    except TelegramConflictError:
        logging.error(
            "Telegram polling conflict detected. Another bot instance is already "
            "calling getUpdates for this token. Stop the other instance before "
            "starting this process."
        )
        raise
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
