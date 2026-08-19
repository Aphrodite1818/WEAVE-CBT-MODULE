# =====================================#
# backend.app.domains.media.repository
# ====================================#

from __future__ import annotations

from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.exams.models import ExamQuestion
from app.domains.media.models import MediaAsset
from app.domains.questions.models import Question


class MediaRepository:
    @staticmethod
    async def add_asset(
        db: AsyncSession,
        asset: MediaAsset,
    ) -> MediaAsset:
        """
        Persist MediaAsset metadata.

        Does not commit.
        Transaction boundaries belong to the service layer.
        """

        db.add(asset)

        await db.flush()
        await db.refresh(asset)

        return asset

    @staticmethod
    async def get_asset_by_id(
        db: AsyncSession,
        asset_id: UUID,
    ) -> MediaAsset | None:
        result = await db.execute(select(MediaAsset).where(MediaAsset.id == asset_id))

        return result.scalar_one_or_none()

    @staticmethod
    async def get_asset_by_storage_key(
        db: AsyncSession,
        storage_key: str,
    ) -> MediaAsset | None:
        result = await db.execute(
            select(MediaAsset).where(MediaAsset.storage_key == storage_key)
        )

        return result.scalar_one_or_none()

    @staticmethod
    async def is_referenced_by_question(
        db: AsyncSession,
        asset_id: UUID,
    ) -> bool:
        """
        Return True when a source Question currently references
        this media asset.
        """

        result = await db.execute(
            select(exists().where(Question.image_asset_id == asset_id))
        )

        return bool(result.scalar())

    @staticmethod
    async def is_referenced_by_exam_question(
        db: AsyncSession,
        asset_id: UUID,
    ) -> bool:
        """
        Return True when a historical/sealed ExamQuestion
        references this media asset.
        """

        result = await db.execute(
            select(exists().where(ExamQuestion.image_asset_id == asset_id))
        )

        return bool(result.scalar())

    @staticmethod
    async def is_referenced(
        db: AsyncSession,
        asset_id: UUID,
    ) -> bool:
        """
        Return True if either a Question or ExamQuestion still
        needs this media asset.
        """

        if await MediaRepository.is_referenced_by_question(
            db,
            asset_id,
        ):
            return True

        return await MediaRepository.is_referenced_by_exam_question(
            db,
            asset_id,
        )

    @staticmethod
    async def delete_asset(
        db: AsyncSession,
        asset: MediaAsset,
    ) -> None:
        """
        Delete MediaAsset metadata.

        The service must verify references and handle physical-file
        deletion before/after calling this method.
        """

        await db.delete(asset)
        await db.flush()
