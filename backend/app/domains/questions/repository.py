"""Persistence operations for locally owned question-bank data.

Repositories persist editable source questions. Validation, version changes,
correct-answer rules, authorization, and transactions belong to services.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.questions.models import (
    Question,
    QuestionBank,
    QuestionOption,
    QuestionType,
)


class QuestionRepository:
    """Provide database operations for banks, questions, and options."""

    @staticmethod
    async def add_bank(db: AsyncSession, bank: QuestionBank) -> QuestionBank:
        db.add(bank)
        await db.flush()
        return bank

    @staticmethod
    async def get_bank_by_id(
        db: AsyncSession,
        bank_id: UUID,
        *,
        lock: bool = False,
    ) -> QuestionBank | None:
        query = select(QuestionBank).where(QuestionBank.id == bank_id)
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_bank_by_scope_and_name(
        db: AsyncSession,
        level_subject_id: UUID,
        name: str,
        *,
        lock: bool = False,
    ) -> QuestionBank | None:
        """Return a bank by canonical LevelSubject scope and name."""
        query = select(QuestionBank).where(
            QuestionBank.level_subject_id == level_subject_id,
            QuestionBank.name == name,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_banks(
        db: AsyncSession,
        *,
        level_subject_id: UUID | None = None,
        created_by_actor_id: UUID | None = None,
        active_only: bool = False,
    ) -> list[QuestionBank]:
        query = select(QuestionBank)
        if level_subject_id is not None:
            query = query.where(QuestionBank.level_subject_id == level_subject_id)
        if created_by_actor_id is not None:
            query = query.where(QuestionBank.created_by_actor_id == created_by_actor_id)
        if active_only:
            query = query.where(QuestionBank.is_active.is_(True))
        result = await db.execute(
            query.order_by(QuestionBank.name.asc(), QuestionBank.id.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def save_bank(db: AsyncSession, bank: QuestionBank) -> QuestionBank:
        db.add(bank)
        await db.flush()
        return bank

    @staticmethod
    async def add_question(
        db: AsyncSession,
        question: Question,
    ) -> Question:
        db.add(question)
        await db.flush()
        return question

    @staticmethod
    async def add_questions(
        db: AsyncSession,
        questions: Sequence[Question],
    ) -> list[Question]:
        rows = list(questions)
        if not rows:
            return []
        db.add_all(rows)
        await db.flush()
        return rows

    @staticmethod
    async def get_question_by_id(
        db: AsyncSession,
        question_id: UUID,
        *,
        lock: bool = False,
    ) -> Question | None:
        query = select(Question).where(Question.id == question_id)
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_questions_for_bank(
        db: AsyncSession,
        bank_id: UUID,
        *,
        question_type: QuestionType | None = None,
        created_by_actor_id: UUID | None = None,
        active_only: bool = False,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[Question]:
        query = select(Question).where(Question.bank_id == bank_id)
        if question_type is not None:
            query = query.where(Question.question_type == question_type)
        if created_by_actor_id is not None:
            query = query.where(Question.created_by_actor_id == created_by_actor_id)
        if active_only:
            query = query.where(Question.is_active.is_(True))
        query = query.order_by(Question.created_at.asc(), Question.id.asc()).offset(
            offset
        )
        if limit is not None:
            query = query.limit(limit)
        return list((await db.execute(query)).scalars().all())

    @staticmethod
    async def list_questions_by_ids(
        db: AsyncSession,
        question_ids: Sequence[UUID],
        *,
        active_only: bool = False,
    ) -> list[Question]:
        if not question_ids:
            return []
        query = select(Question).where(Question.id.in_(question_ids))
        if active_only:
            query = query.where(Question.is_active.is_(True))
        return list((await db.execute(query)).scalars().all())

    @staticmethod
    async def count_questions_for_bank(
        db: AsyncSession,
        bank_id: UUID,
        *,
        active_only: bool = False,
    ) -> int:
        query = select(func.count()).select_from(Question).where(
            Question.bank_id == bank_id,
        )
        if active_only:
            query = query.where(Question.is_active.is_(True))
        return int((await db.execute(query)).scalar_one() or 0)

    @staticmethod
    async def save_question(
        db: AsyncSession,
        question: Question,
    ) -> Question:
        db.add(question)
        await db.flush()
        return question

    @staticmethod
    async def save_questions(
        db: AsyncSession,
        questions: Sequence[Question],
    ) -> list[Question]:
        rows = list(questions)
        if not rows:
            return []
        db.add_all(rows)
        await db.flush()
        return rows

    @staticmethod
    async def add_option(
        db: AsyncSession,
        option: QuestionOption,
    ) -> QuestionOption:
        db.add(option)
        await db.flush()
        return option

    @staticmethod
    async def add_options(
        db: AsyncSession,
        options: Sequence[QuestionOption],
    ) -> list[QuestionOption]:
        rows = list(options)
        if not rows:
            return []
        db.add_all(rows)
        await db.flush()
        return rows

    @staticmethod
    async def get_option_by_id(
        db: AsyncSession,
        question_id: UUID,
        option_id: UUID,
        *,
        lock: bool = False,
    ) -> QuestionOption | None:
        query = select(QuestionOption).where(
            QuestionOption.question_id == question_id,
            QuestionOption.id == option_id,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_options_for_question(
        db: AsyncSession,
        question_id: UUID,
    ) -> list[QuestionOption]:
        result = await db.execute(
            select(QuestionOption)
            .where(QuestionOption.question_id == question_id)
            .order_by(QuestionOption.position.asc(), QuestionOption.id.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_options_for_questions(
        db: AsyncSession,
        question_ids: Sequence[UUID],
    ) -> list[QuestionOption]:
        if not question_ids:
            return []
        result = await db.execute(
            select(QuestionOption)
            .where(QuestionOption.question_id.in_(question_ids))
            .order_by(
                QuestionOption.question_id.asc(),
                QuestionOption.position.asc(),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def save_option(
        db: AsyncSession,
        option: QuestionOption,
    ) -> QuestionOption:
        db.add(option)
        await db.flush()
        return option

    @staticmethod
    async def save_options(
        db: AsyncSession,
        options: Sequence[QuestionOption],
    ) -> list[QuestionOption]:
        rows = list(options)
        if not rows:
            return []
        db.add_all(rows)
        await db.flush()
        return rows

    @staticmethod
    async def remove_option(db: AsyncSession, option: QuestionOption) -> None:
        await db.delete(option)
        await db.flush()
