"""Batch exam-start and timetable-impact routes."""

from __future__ import annotations

from collections import Counter
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.database import DbSession
from app.domains.auth.dependencies import CurrentLocalActor
from app.domains.exams.exceptions import ExamNotFound, ExamStateError
from app.domains.exams.repository import ExamRepository
from app.domains.exams.service import ExamService
from app.domains.exams.timetable_schemas import (
    BatchExamStartItemResponse,
    BatchExamStartRequest,
    BatchExamStartResponse,
    TimetableImpactResponse,
)
from app.domains.exams.timetable_service import ExamTimetableService


router = APIRouter(prefix="/exams", tags=["Exam Timetable"])


def _require_admin(actor) -> None:
    if not actor.is_active or actor.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="School administrator access required.",
        )


@router.get("/{exam_id}/timetable-impact", response_model=list[TimetableImpactResponse])
async def timetable_impact(
    exam_id: UUID,
    db: DbSession,
    actor: CurrentLocalActor,
) -> list[TimetableImpactResponse]:
    _require_admin(actor)
    try:
        rows = await ExamTimetableService.impact_after_start(db, exam_id=exam_id)
    except ExamNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [TimetableImpactResponse(**row.__dict__) for row in rows]


@router.post("/start-batch", response_model=BatchExamStartResponse)
async def start_exam_batch(
    payload: BatchExamStartRequest,
    db: DbSession,
    actor: CurrentLocalActor,
) -> BatchExamStartResponse:
    _require_admin(actor)

    exams = {}
    levels = {}
    for exam_id in payload.exam_ids:
        exam = await ExamRepository.get_exam_by_id(db, exam_id=exam_id)
        if exam is not None:
            exams[exam_id] = exam
            levels[exam_id] = await ExamTimetableService.level_id(
                db, exam.curriculum_subject_id
            )
    level_counts = Counter(levels.values())

    results: list[BatchExamStartItemResponse] = []
    for exam_id in payload.exam_ids:
        exam = exams.get(exam_id)
        if exam is None:
            results.append(
                BatchExamStartItemResponse(
                    exam_id=exam_id,
                    started=False,
                    error="Examination does not exist",
                )
            )
            continue
        if level_counts[levels[exam_id]] > 1:
            results.append(
                BatchExamStartItemResponse(
                    exam_id=exam_id,
                    started=False,
                    error="Select at most one examination per academic level in a batch",
                )
            )
            continue
        try:
            await ExamService.activate_exam(db, actor=actor, exam_id=exam_id)
            impacts = await ExamTimetableService.impact_after_start(
                db, exam_id=exam_id
            )
            results.append(
                BatchExamStartItemResponse(
                    exam_id=exam_id,
                    started=True,
                    impacts=[
                        TimetableImpactResponse(**impact.__dict__)
                        for impact in impacts
                    ],
                )
            )
        except (ExamNotFound, ExamStateError, ValueError) as exc:
            results.append(
                BatchExamStartItemResponse(
                    exam_id=exam_id,
                    started=False,
                    error=str(exc),
                )
            )

    return BatchExamStartResponse(results=results)
