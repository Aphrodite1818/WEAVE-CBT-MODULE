from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.core.database import DbSession
from app.core.exceptions import AcademicAuthorizationError, AcademicScopeError
from app.domains.auth.dependencies import CurrentLocalActor
from app.domains.questions.models import Question
from app.domains.questions.repository import QuestionRepository
from app.domains.questions.schemas import QuestionOptionResponse, QuestionResponse
from app.domains.questions.service import QuestionService


router = APIRouter(prefix="/questions", tags=["Questions"])


async def _question_responses(
    db: DbSession,
    questions: list[Question],
) -> list[QuestionResponse]:
    if not questions:
        return []

    options = await QuestionRepository.list_options_for_questions(
        db,
        [question.id for question in questions],
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
            last_edited_by_actor_id=question.last_edited_by_actor_id,
            is_active=question.is_active,
            options=grouped[question.id],
        )
        for question in questions
    ]


@router.get(
    "/manageable",
    response_model=list[QuestionResponse],
)
async def list_manageable_questions(
    db: DbSession,
    actor: CurrentLocalActor,
    bank_id: UUID | None = Query(default=None),
    include_archived: bool = Query(default=True),
    offset: int = Query(default=0, ge=0),
    limit: int | None = Query(default=None, ge=1, le=1000),
) -> list[QuestionResponse]:
    """Return the question-management scope for the current actor.

    Administrators receive all questions on the local node. Teachers receive only
    questions they personally contributed, further constrained to question banks
    that remain inside their current synchronized teaching scope.

    ``offset`` and ``limit`` are available for server-side pagination. Omitting
    ``limit`` preserves the current workspace contract while callers migrate to a
    paginated management view.
    """

    try:
        questions = await QuestionService.list_actor_manageable_questions(
            db,
            actor=actor,
            bank_id=bank_id,
            active_only=not include_archived,
            offset=offset,
            limit=limit,
        )
    except AcademicAuthorizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except AcademicScopeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return await _question_responses(db, questions)
