from __future__ import annotations

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import StudentRegistry, UserLink, AuthAttempt


class StudentRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_student(self, student_id: str, first_name: str, last_name: str) -> None:
        q = await self.session.execute(select(StudentRegistry).where(StudentRegistry.student_id == student_id))
        s = q.scalar_one_or_none()
        if s is None:
            self.session.add(StudentRegistry(student_id=student_id, first_name=first_name, last_name=last_name))
        else:
            s.first_name = first_name
            s.last_name = last_name
        await self.session.commit()

    async def get_student(self, student_id: str) -> StudentRegistry | None:
        q = await self.session.execute(select(StudentRegistry).where(StudentRegistry.student_id == student_id))
        return q.scalar_one_or_none()

    async def list_students(self) -> list[StudentRegistry]:
        q = await self.session.execute(select(StudentRegistry).order_by(StudentRegistry.last_name, StudentRegistry.first_name))
        return list(q.scalars().all())

    async def update_name(self, student_id: str, first_name: str, last_name: str) -> None:
        await self.session.execute(
            update(StudentRegistry)
            .where(StudentRegistry.student_id == student_id)
            .values(first_name=first_name, last_name=last_name)
        )
        await self.session.commit()


class LinkRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_link_by_telegram(self, telegram_id: int) -> UserLink | None:
        q = await self.session.execute(select(UserLink).where(UserLink.telegram_id == telegram_id))
        return q.scalar_one_or_none()

    async def get_link_by_student(self, student_id: str) -> UserLink | None:
        q = await self.session.execute(select(UserLink).where(UserLink.student_id == student_id))
        return q.scalar_one_or_none()

    async def create_link(self, telegram_id: int, student_id: str) -> None:
        self.session.add(UserLink(telegram_id=telegram_id, student_id=student_id, confirmed=True))
        await self.session.commit()

    async def unlink_student(self, student_id: str) -> None:
        await self.session.execute(delete(UserLink).where(UserLink.student_id == student_id))
        await self.session.commit()


class AttemptRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, telegram_id: int) -> AuthAttempt:
        q = await self.session.execute(select(AuthAttempt).where(AuthAttempt.telegram_id == telegram_id))
        a = q.scalar_one_or_none()
        if a is None:
            a = AuthAttempt(telegram_id=telegram_id, failures=0, locked=False)
            self.session.add(a)
            await self.session.commit()
        return a

    async def increment_failure(self, telegram_id: int, max_failures: int = 3) -> AuthAttempt:
        a = await self.get_or_create(telegram_id)
        if a.locked:
            return a
        a.failures += 1
        if a.failures >= max_failures:
            a.locked = True
        await self.session.commit()
        return a

    async def reset(self, telegram_id: int) -> None:
        a = await self.get_or_create(telegram_id)
        a.failures = 0
        a.locked = False
        await self.session.commit()
