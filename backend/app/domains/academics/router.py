from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.core.database import DbSession
from app.core.exceptions import AcademicAuthorizationError, AcademicScopeError
from app.domains.academics.repository import AcademicRepository
from app.domains.academics.schemas import (
    AcademicSessionResponse,
    AcademicTermResponse,
    AuthorableCurriculumSubjectResponse
)

from app.domains.academics.service import AcademicQueryService
from app.domains.auth.dependencies import CurrentLocalActor



router = APIRouter(
    prefix = "/academics",
    tags = ["Academics"]
)



@router.get(
    "/session/current",
    response_model=AcademicSessionResponse
)
async def get_current_academic_session(
    db : DbSession,
    _actor : CurrentLocalActor
) -> AcademicSessionResponse:
    academic_session = await AcademicRepository.get_current_session(
        db
    )

    if academic_session is None:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = "Current academic session is not available"
        )

    return AcademicSessionResponse.model_validate(academic_session)




@router.get(
    "/term/current",
    response_model=AcademicTermResponse
)
async def get_current_academic_term(
    db : DbSession,
    _actor : CurrentLocalActor
) -> AcademicTermResponse:


    academic_session = await AcademicRepository.get_current_session(db)
    if academic_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail = "Current academic session is not available"
        )

    
    academic_term = await AcademicRepository.get_current_term(
        db,
        session_id = academic_session.id
    )

    if academic_term is None:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = "Current academic Term is not available"
        )
    return AcademicTermResponse.model_validate(academic_term)




@router.get(
    "/curriculum-subjects/authorable",
    response_model = list[AuthorableCurriculumSubjectResponse]
)
async def list_authorable_curriculum_subject(
    db : DbSession,
    actor : CurrentLocalActor
):# -> list[Any] | list[AuthorableCurriculumSubjectResponse] | None:
    try:
        return await AcademicQueryService.list_authorable_curriculum_subjects(
            db,
            actor = actor
        )

    except AcademicAuthorizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail = str(exc)
        ) from exc

    except AcademicScopeError as exc:
        raise HTTPException(
            status_code = status.HTTP_409_CONFLICT,
            detail = str(exc)
        )from exc
