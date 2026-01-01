from __future__ import annotations

import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.core.config import settings
from app.core.logging import setup_logging

from app.db.session import engine, SessionLocal
from app.db.base import Base
from app.db.repo import StudentRepo, LinkRepo, AttemptRepo

from app.features.registration.router import router as registration_router
from app.features.grades.router import router as grades_router
from app.features.admin.router import router as admin_router


async def _init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _run() -> None:
    setup_logging()
    await _init_db()

    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    async def _inject(handler, event, data):
        async with SessionLocal() as session:
            data["student_repo"] = StudentRepo(session)
            data["link_repo"] = LinkRepo(session)
            data["attempt_repo"] = AttemptRepo(session)
            data["owner_student_id"] = settings.OWNER_STUDENT_ID
            return await handler(event, data)

    dp.update.outer_middleware(_inject)

    dp.include_router(registration_router)
    dp.include_router(grades_router)
    dp.include_router(admin_router)

    await dp.start_polling(bot)


def main() -> None:
    try:
        asyncio.run(_run())
    except (KeyboardInterrupt, SystemExit):
        pass
