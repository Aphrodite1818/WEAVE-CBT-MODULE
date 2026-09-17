"""Build question API read models with current author display information."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academics.repository import AcademicRepository
from app.domains.auth.models import LocalActor
from app.domains.questions.models import Question
from app.domains.questions.repository import QuestionRepository
from app.domains.questions.schemas import QuestionOptionResponse, QuestionResponse


def _membership_uuid(actor: LocalActor) -> UUID | None:
    if actor.role != "teacher" or not actor.weave_membership_id:
        return None
    try:
        return UUID(actor.weave_membership_id)
    except (TypeError, ValueError):
        return None


async def _load_author_names(
    db: AsyncSession,
    actor_ids: Sequence[UUID],
    *,
    request_actor: LocalActor | None = None,
) -> dict[UUID, str]:
    """Resolve current author labels without creating an N+1 query pattern.

    Question authorship itself is historical through ``created_by_actor_id``.
    The human-readable name is intentionally current presentation data. Active
    synchronized teacher projections provide the current first/last name; the
    durable local actor display name is the fallback for teachers no longer in
    the live projection. Administrators are always displayed simply as ``Admin``.
    """

    unique_ids = set(actor_ids)
    if not unique_ids:
        return {}

    actors: dict[UUID, LocalActor] = {}
    request_actor_id = getattr(request_actor, "id", None)
    if request_actor_id in unique_ids:
        actors[request_actor_id] = request_actor

    remaining_ids = unique_ids - set(actors)
    if remaining_ids:
        result = await db.execute(select(LocalActor).where(LocalActor.id.in_(remaining_ids)))
        actors.update({actor.id: actor for actor in result.scalars().all()})

    membership_to_actor_id: dict[UUID, UUID] = {}
    for actor_id, actor in actors.items():
        membership_id = _membership_uuid(actor)
        if membership_id is not None:
            membership_to_actor_id[membership_id] = actor_id

    current_teacher_names: dict[UUID, str] = {}
    if membership_to_actor_id:
        teachers = await AcademicRepository.list_teachers_by_ids(
            db,
            list(membership_to_actor_id),
            active_only=False,
        )
        for teacher in teachers:
            parts = [
                value.strip()
                for value in (teacher.first_name, teacher.last_name)
                if value and value.strip()
            ]
            if parts:
                current_teacher_names[membership_to_actor_id[teacher.id]] = " ".join(parts)

    author_names: dict[UUID, str] = {}
    for actor_id, actor in actors.items():
        if actor.role == "admin":
            author_names[actor_id] = "Admin"
            continue

        current_name = current_teacher_names.get(actor_id)
        if current_name:
            author_names[actor_id] = current_name
            continue

        display_name = (actor.display_name or "").strip()
        author_names[actor_id] = display_name or "Teacher"

    return author_names


async def build_question_response(
    db: AsyncSession,
    question: Question,
    *,
    request_actor: LocalActor | None = None,
) -> QuestionResponse:
    options = await QuestionRepository.list_options_for_question(db, question.id)
    author_names = await _load_author_names(
        db,
        [question.created_by_actor_id],
        request_actor=request_actor,
    )
    return QuestionResponse(
        id=question.id,
        bank_id=question.bank_id,
        question_type=question.question_type,
        prompt=question.prompt,
        instruction=question.instruction,
        image_asset_id=question.image_asset_id,
        version=question.version,
        created_by_actor_id=question.created_by_actor_id,
        author_name=author_names.get(question.created_by_actor_id, "Unknown author"),
        last_edited_by_actor_id=question.last_edited_by_actor_id,
        is_active=question.is_active,
        options=[QuestionOptionResponse.model_validate(option) for option in options],
    )


async def build_question_responses(
    db: AsyncSession,
    questions: list[Question],
    *,
    request_actor: LocalActor | None = None,
) -> list[QuestionResponse]:
    if not questions:
        return []

    options = await QuestionRepository.list_options_for_questions(
        db,
        [question.id for question in questions],
    )
    author_names = await _load_author_names(
        db,
        [question.created_by_actor_id for question in questions],
        request_actor=request_actor,
    )

    grouped: dict[UUID, list[QuestionOptionResponse]] = defaultdict(list)
    for option in options:
        grouped[option.question_id].append(
            QuestionOptionResponse.model_validate(option)
        )

    return [
        QuestionResponse(
            id=question.id,
            bank_id=question.bank_id,
            question_type=question.question_type,
            prompt=question.prompt,
            instruction=question.instruction,
            image_asset_id=question.image_asset_id,
            version=question.version,
            created_by_actor_id=question.created_by_actor_id,
            author_name=author_names.get(question.created_by_actor_id, "Unknown author"),
            last_edited_by_actor_id=question.last_edited_by_actor_id,
            is_active=question.is_active,
            options=grouped[question.id],
        )
        for question in questions
    ]
