"""Read-oriented academic query services."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AcademicScopeError
from app.domains.academics.authorization import AcademicAuthorizationService
from app.domains.academics.repository import AcademicRepository
from app.domains.academics.schemas import (
    AuthorableCurriculumSubjectResponse,
    TeacherAssignmentResponse,
)
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

        subjects_by_id = {subject.id: subject for subject in subjects}

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

    @staticmethod
    async def list_effective_teacher_assignments(
        db: AsyncSession,
        *,
        actor: LocalActor,
    ) -> list[TeacherAssignmentResponse]:
        assignments = (
            await AcademicAuthorizationService.list_actor_effective_teacher_assignments(
                db,
                actor=actor,
            )
        )

        if not assignments:
            return []

        teachers = await AcademicRepository.list_teachers_by_ids(
            db,
            [assignment.teacher_membership_id for assignment in assignments],
            active_only=False,
        )

        classes = await AcademicRepository.list_classes_by_ids(
            db,
            [assignment.class_id for assignment in assignments],
        )

        curriculum_subjects = (
            await AcademicRepository.list_curriculum_subjects_by_ids(
                db,
                [assignment.curriculum_subject_id for assignment in assignments],
            )
        )

        subjects = await AcademicRepository.list_subjects_by_ids(
            db,
            [
                curriculum_subject.subject_id
                for curriculum_subject in curriculum_subjects
            ],
        )

        teachers_by_id = {
            teacher.id: teacher
            for teacher in teachers
        }

        classes_by_id = {
            classroom.id: classroom
            for classroom in classes
        }

        curriculum_subjects_by_id = {
            curriculum_subject.id: curriculum_subject
            for curriculum_subject in curriculum_subjects
        }

        subjects_by_id = {
            subject.id: subject
            for subject in subjects
        }

        response: list[TeacherAssignmentResponse] = []

        for assignment in assignments:
            teacher = teachers_by_id.get(assignment.teacher_membership_id)

            classroom = classes_by_id.get(assignment.class_id)

            curriculum_subject = curriculum_subjects_by_id.get(
                assignment.curriculum_subject_id
            )

            if teacher is None:
                raise AcademicScopeError(
                    "Teacher assignment references an unavailable teacher"
                )

            if classroom is None:
                raise AcademicScopeError(
                    "Teacher assignment references an unavailable class"
                )

            if curriculum_subject is None:
                raise AcademicScopeError(
                    "Teacher assignment references an unavailable curriculum subject"
                )

            subject = subjects_by_id.get(curriculum_subject.subject_id)

            if subject is None:
                raise AcademicScopeError(
                    "Curriculum subject references an unavailable academic subject"
                )

            teacher_name = " ".join(
                part
                for part in (
                    teacher.first_name,
                    teacher.last_name,
                )
                if part
            ).strip()

            if not teacher_name:
                teacher_name = teacher.staff_id or "Unnamed teacher"

            response.append(
                TeacherAssignmentResponse(
                    id=assignment.id,
                    teacher_membership_id=assignment.teacher_membership_id,
                    teacher_name=teacher_name,
                    class_id=assignment.class_id,
                    class_name=classroom.display_name,
                    curriculum_subject_id=assignment.curriculum_subject_id,
                    subject_id=subject.id,
                    subject_name=subject.name,
                    subject_code=subject.code,
                    effective_from=assignment.effective_from,
                    effective_to=assignment.effective_to,
                )
            )

        return response
