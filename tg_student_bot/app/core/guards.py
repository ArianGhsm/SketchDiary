from __future__ import annotations
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from app.db.repo import LinkRepo


class IsRegistered(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery, link_repo: LinkRepo) -> bool:
        user = getattr(event, "from_user", None)
        if not user:
            return False
        return (await link_repo.get_link_by_telegram(user.id)) is not None


class IsOwner(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery, link_repo: LinkRepo, owner_student_id: str) -> bool:
        user = getattr(event, "from_user", None)
        if not user:
            return False
        link = await link_repo.get_link_by_telegram(user.id)
        return bool(link and link.student_id == owner_student_id)
