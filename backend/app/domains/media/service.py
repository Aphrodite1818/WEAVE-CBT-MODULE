from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.models import LocalActor
from app.domains.media.models import (
    MEDIA_FILENAME_MAX_LENGTH,
    MediaAsset,
)
from app.domains.media.repository import MediaRepository
from app.domains.media.storage import local_media_storage


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MediaContent:
    """
    Physical media content returned by the storage layer.

    This is useful later when an authorized route needs to
    deliver an image to the frontend.
    """

    data: bytes
    mime_type: str
    original_filename: str


def _normalize_original_filename(
    filename: str | None,
) -> str:
    """
    Keep the original filename only as harmless metadata.

    The original filename is NEVER used as the actual
    filesystem path.
    """

    if filename is None:
        return "image"

    filename = filename.strip()

    # Browsers may sometimes submit things resembling:
    #
    # C:\\fakepath\\diagram.png
    #
    # Normalize both slash styles.
    filename = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()

    if not filename:
        return "image"

    return filename[:MEDIA_FILENAME_MAX_LENGTH]


class MediaService:
    @staticmethod
    async def upload_question_image(
        db: AsyncSession,
        *,
        actor: LocalActor,
        original_filename: str | None,
        data: bytes,
    ) -> MediaAsset:
        """
        Validate, normalize, store and register one question image.

        This operation creates an independent MediaAsset.

        The QuestionService will later decide whether the actor is
        academically authorized to attach this asset to a particular
        question.
        """

        # -----------------------------------------------------
        # 1. Basic staff authorization.
        # -----------------------------------------------------

        if not actor.is_active:
            raise ValueError("Active local actor is required")

        if actor.role not in {
            "admin",
            "teacher",
        }:
            raise ValueError("Only school staff may upload question media")

        filename = _normalize_original_filename(original_filename)

        # -----------------------------------------------------
        # 2. Store the physical image first.
        #
        # storage.py:
        # - validates the image
        # - fixes orientation
        # - preserves aspect ratio
        # - normalizes to the standard canvas
        # - converts to immutable WebP
        # - calculates SHA-256
        # -----------------------------------------------------

        stored = await local_media_storage.save_question_image(data)

        # -----------------------------------------------------
        # 3. Create corresponding database metadata.
        # -----------------------------------------------------

        asset = MediaAsset(
            storage_key=stored.storage_key,
            original_filename=filename,
            mime_type=stored.mime_type,
            size_bytes=stored.size_bytes,
            sha256=stored.sha256,
            created_by_actor_id=actor.id,
        )

        try:
            asset = await MediaRepository.add_asset(
                db,
                asset,
            )

            await db.commit()

        except Exception:
            await db.rollback()

            # The physical file was already created.
            # If PostgreSQL rejects the MediaAsset row, remove
            # that newly-created file immediately.
            try:
                await local_media_storage.delete(stored.storage_key)

            except Exception:
                logger.exception(
                    "Failed to remove orphaned media file %s "
                    "after database persistence failure",
                    stored.storage_key,
                )

            raise

        return asset

    @staticmethod
    async def get_asset(
        db: AsyncSession,
        *,
        asset_id: UUID,
    ) -> MediaAsset:
        """
        Resolve MediaAsset metadata.

        This method does NOT decide whether a student or teacher
        is authorized to view the image. That authorization belongs
        to the Question/Exam domain using the asset.
        """

        asset = await MediaRepository.get_asset_by_id(
            db,
            asset_id,
        )

        if asset is None:
            raise ValueError("Media asset does not exist")

        return asset

    @staticmethod
    async def load_asset_content(
        db: AsyncSession,
        *,
        asset_id: UUID,
    ) -> MediaContent:
        """
        Load the physical bytes for an already-authorized asset.

        Callers must perform question/exam authorization before
        using this method for HTTP delivery.
        """

        asset = await MediaService.get_asset(
            db,
            asset_id=asset_id,
        )

        try:
            data = await local_media_storage.read(asset.storage_key)

        except FileNotFoundError as exc:
            raise RuntimeError(
                "Media asset exists in the database but its physical file is missing"
            ) from exc

        return MediaContent(
            data=data,
            mime_type=asset.mime_type,
            original_filename=asset.original_filename,
        )

    @staticmethod
    async def delete_unreferenced_asset(
        db: AsyncSession,
        *,
        asset_id: UUID,
    ) -> bool:
        """
        Delete a MediaAsset only when neither Question nor
        ExamQuestion still references it.

        Returns:
            True:
                asset existed and was deleted.

            False:
                asset no longer existed.
        """

        asset = await MediaRepository.get_asset_by_id(
            db,
            asset_id,
        )

        if asset is None:
            return False

        is_referenced = await MediaRepository.is_referenced(
            db,
            asset.id,
        )

        if is_referenced:
            raise ValueError("Media asset is still referenced and cannot be deleted")

        storage_key = asset.storage_key

        # -----------------------------------------------------
        # Delete DB metadata FIRST.
        #
        # PostgreSQL's FK RESTRICT constraints provide another
        # safety layer if something concurrently references it.
        # -----------------------------------------------------

        try:
            await MediaRepository.delete_asset(
                db,
                asset,
            )

            await db.commit()

        except IntegrityError as exc:
            await db.rollback()

            raise ValueError(
                "Media asset became referenced and cannot be deleted"
            ) from exc

        except Exception:
            await db.rollback()
            raise

        # -----------------------------------------------------
        # Now remove the physical file.
        #
        # If this fails, we have an orphan FILE rather than a
        # broken Question/ExamQuestion pointing to a missing file.
        #
        # That is the safer failure direction.
        # -----------------------------------------------------

        try:
            await local_media_storage.delete(storage_key)

        except Exception:
            logger.exception(
                "Media metadata was deleted but physical file %s could not be removed",
                storage_key,
            )

        return True
