"""Persistence operations for locally owned question-bank data.

Repositories persist editable source questions. Validation, version changes,
correct-answer rules, authorization, and transactions belong to services.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from app.domains.questions.models import (
    Question,
    QuestionBank,
    QuestionOption,
    QuestionType,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class QuestionRepository:
    """Provide database operations for banks, questions, and options."""

    @staticmethod
    async def add_bank(db: AsyncSession, bank: QuestionBank) -> QuestionBank:
        """Add a question bank and flush pending changes."""
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
        """Return a question bank by local ID."""
        query = select(QuestionBank).where(QuestionBank.id == bank_id)
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_bank_by_scope_and_name(
        db: AsyncSession,
        level_id: UUID,
        subject_id: UUID,
        name: str,
        *,
        lock: bool = False,
    ) -> QuestionBank | None:
        """Return the uniquely named bank within a level-subject scope."""
        query = select(QuestionBank).where(
            QuestionBank.level_id == level_id,
            QuestionBank.subject_id == subject_id,
            QuestionBank.name == name,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_banks(
        db: AsyncSession,
        *,
        level_id: UUID | None = None,
        subject_id: UUID | None = None,
        active_only: bool = False,
    ) -> list[QuestionBank]:
        """Return question banks matching the supplied academic filters."""
        query = select(QuestionBank)
        if level_id is not None:
            query = query.where(QuestionBank.level_id == level_id)
        if subject_id is not None:
            query = query.where(QuestionBank.subject_id == subject_id)
        if active_only:
            query = query.where(QuestionBank.is_active.is_(True))

        result = await db.execute(
            query.order_by(QuestionBank.name.asc(), QuestionBank.id.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def save_bank(db: AsyncSession, bank: QuestionBank) -> QuestionBank:
        """Attach a question bank and flush pending changes."""
        db.add(bank)
        await db.flush()
        return bank

    @staticmethod
    async def add_question(
        db: AsyncSession,
        question: Question,
    ) -> Question:
        """Add a source question and flush pending changes."""
        db.add(question)
        await db.flush()
        return question

    @staticmethod
    async def add_questions(
        db: AsyncSession,
        questions: Sequence[Question],
    ) -> list[Question]:
        """Add source questions and return the flushed rows."""
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
        """Return a source question by local ID."""
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
        active_only: bool = False,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[Question]:
        """Return source questions belonging to a question bank."""
        query = select(Question).where(Question.bank_id == bank_id)
        if question_type is not None:
            query = query.where(Question.question_type == question_type)
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
        """Return source questions matching the supplied IDs."""
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
        """Return the number of source questions in a bank."""
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
        """Attach a source question and flush pending changes."""
        db.add(question)
        await db.flush()
        return question

    @staticmethod
    async def save_questions(
        db: AsyncSession,
        questions: Sequence[Question],
    ) -> list[Question]:
        """Attach source questions and return the flushed rows."""
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
        """Add a source question option and flush pending changes."""
        db.add(option)
        await db.flush()
        return option

    @staticmethod
    async def add_options(
        db: AsyncSession,
        options: Sequence[QuestionOption],
    ) -> list[QuestionOption]:
        """Add source question options and return the flushed rows."""
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
        """Return an option belonging to a source question."""
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
        """Return a question's options in canonical order."""
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
        """Return options for multiple source questions without N+1 queries."""
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
        """Attach a source question option and flush pending changes."""
        db.add(option)
        await db.flush()
        return option

    @staticmethod
    async def save_options(
        db: AsyncSession,
        options: Sequence[QuestionOption],
    ) -> list[QuestionOption]:
        """Attach source options and return the flushed rows."""
        rows = list(options)
        if not rows:
            return []

        db.add_all(rows)
        await db.flush()
        return rows

    @staticmethod
    async def remove_option(db: AsyncSession, option: QuestionOption) -> None:
        """Remove a source option and flush pending changes."""
        await db.delete(option)
        await db.flush()
