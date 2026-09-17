"""Build question API read models with current author display information."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.models import LocalActor
from app.domains.questions.models import Question
from app.domains.questions.repository import QuestionRepository
from app.domains.questions.schemas import QuestionOptionResponse, QuestionResponse


def _author_name(actor: LocalActor | None) -> str:
    """Return the current display label for a question author.

    Administrators are intentionally anonymized to the role label while teacher
    questions follow the actor's current display name. The question keeps only
    the immutable actor ID; names are presentation data and are resolved at read
    time so profile corrections or name changes are reflected automatically.
    """

    if actor is None:
        return "Unknown author"
    if actor.role == "admin":
        return "Admin"

    display_name = (actor.display_name or "").strip()
    return display_name or "Teacher"


async def _load_author_map(
    db: AsyncSession,
    actor_ids: Sequence[UUID],
    *,
    request_actor: LocalActor | None = None,
) -> dict[UUID, LocalActor]:
    """Resolve unique authors in one query, reusing the authenticated actor."""

    unique_ids = set(actor_ids)
    if not unique_ids:
        return {}

    actors: dict[UUID, LocalActor] = {}
    request_actor_id = getattr(request_actor, "id", None)
    if request_actor_id in unique_ids:
        actors[request_actor_id] = request_actor

    remaining_ids = unique_ids - actors.keys()
    if remaining_ids:
        result = await db.execute(select(LocalActor).where(LocalActor.id.in_(remaining_ids)))
        actors.update({actor.id: actor for actor in result.scalars().all()})

    return actors


async def build_question_response(
    db: AsyncSession,
    question: Question,
    *,
    request_actor: LocalActor | None = None,
) -> QuestionResponse:
    options = await QuestionRepository.list_options_for_question(db, question.id)
    authors = await _load_author_map(
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
        author_name=_author_name(authors.get(question.created_by_actor_id)),
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
    authors = await _load_author_map(
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
            author_name=_author_name(authors.get(question.created_by_actor_id)),
            last_edited_by_actor_id=question.last_edited_by_actor_id,
            is_active=question.is_active,
            options=grouped[question.id],
        )
        for question in questions
    ]
