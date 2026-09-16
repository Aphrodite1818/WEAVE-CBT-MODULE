"""Read-oriented academic query services."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AcademicScopeError
from app.domains.academics.authorization import AcademicAuthorizationService
from app.domains.academics.repository import AcademicRepository
from app.domains.academics.schemas import AuthorableCurriculumSubjectResponse
from app.domains.auth.models import LocalActor


class AcademicQueryService:
    """Read-oriented operations over synchronized academic projections"""

    @staticmethod
    async def list_authorable_curriculum_subjects(
        db: AsyncSession,
        *,
        actor: LocalActor,
    ) -> list[AuthorableCurriculumSubjectResponse]:
        curriculum_subjects = (
            await AcademicAuthorizationService.list_actor_authorable_curriculum_subjects(
                db,
                actor=actor,
            )
        )

        if not curriculum_subjects:
            return []

        subjects = await AcademicRepository.list_subjects_by_ids(
            db,
            subject_ids=[
                curriculum_subject.subject_id
                for curriculum_subject in curriculum_subjects
            ],
        )

        subjects_by_id = {
            subject.id: subject
            for subject in subjects
        }

        response: list[AuthorableCurriculumSubjectResponse] = []
        for curriculum_subject in curriculum_subjects:
            subject = subjects_by_id.get(curriculum_subject.subject_id)
            if subject is None:
                raise AcademicScopeError(
                    "Curriculum subject references an unavailable academic subject"
                )

            response.append(
                AuthorableCurriculumSubjectResponse(
                    id=curriculum_subject.id,
                    curriculum_id=curriculum_subject.curriculum_id,
                    subject_id=subject.id,
                    subject_name=subject.name,
                    subject_code=subject.code,
                    is_elective=curriculum_subject.is_elective,
                    is_active=curriculum_subject.is_active,
                )
            )

        return response
