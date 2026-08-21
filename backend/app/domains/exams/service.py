"""Application services for examination authoring and lifecycle management"""

from __future__ import annotations

from datetime import UTC, datetime
from secrets import SystemRandom
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AcademicAuthorizationError, AcademicScopeError
from app.domains.academics.authorization import AcademicAuthorizationService
from app.domains.academics.repository import AcademicRepository
from app.domains.auth.models import LocalActor
from app.domains.exams.exceptions import (
    ExamNotFound,
    ExamStateError,
)
from app.domains.exams.models import (
    Exam,
    ExamInvigilator,
    ExamQuestion,
    ExamQuestionOption,
    ExamQuestionSelection,
    ExamQuestionSelectionMode,
    ExamRosterStatus,
    ExamStatus,
    ExamSuspension,
    ExamSuspensionSource,
    ExamTargetClass,
)
from app.domains.exams.repository import ExamRepository
from app.domains.exams.schemas import (
    ExamCreate,
    ExamQuestionConfiguration,
    ExamUpdate,
    ManualQuestionAdd,
    ManualQuestionRemove,
    ManualQuestionReorder,
)
from app.domains.questions.models import QuestionType
from app.domains.questions.repository import QuestionRepository
from app.domains.runtime.models import RealtimeOutboxEvent
from app.domains.runtime.repository import RuntimeRepository


def _normalize_optional_text(value: str | None) -> None | str:
    """
    Convert blank optional text into None.

    An empty string is represented as NULL for optional examination instructions.
    """

    if value is None:
        return None

    value = value.strip()

    if not value:
        return None

    return value


class ExamService:
    """Business operations for locally owned CBT examinations."""

    @staticmethod
    def _require_admin(actor: LocalActor) -> None:
        if not actor.is_active:
            raise AcademicAuthorizationError("Active local actor is required")
        if actor.role != "admin":
            raise AcademicAuthorizationError(
                "Only school administrators can perform this exam operation"
            )

    @staticmethod
    def _normalize_required_text(value: str | None, field_name: str = "reason") -> str:
        normalized = _normalize_optional_text(value)
        if normalized is None:
            raise ValueError(f"{field_name} is required")
        return normalized

    @staticmethod
    async def _add_lifecycle_event(
        db: AsyncSession,
        *,
        exam: Exam,
        event_type: str,
        actor: LocalActor,
        occurred_at: datetime,
        extra_payload: dict | None = None,
    ) -> None:
        payload = {
            "exam_id": str(exam.id),
            "status": exam.status.value,
            "revision_number": exam.revision_number,
            "actor_id": str(actor.id),
            "occurred_at": occurred_at.isoformat(),
        }
        if extra_payload:
            payload.update(extra_payload)
        await RuntimeRepository.add_outbox_event(
            db,
            RealtimeOutboxEvent(
                aggregate_type="exam",
                aggregate_id=exam.id,
                event_type=event_type,
                payload=payload,
            ),
        )

    @staticmethod
    async def _latest_revision_in_lineage(
        db: AsyncSession,
        exam: Exam,
    ) -> Exam:
        current = exam
        while True:
            child = await ExamRepository.get_latest_child_revision(
                db,
                current.id,
                lock=True,
            )
            if child is None:
                return current
            current = child

    @staticmethod
    async def _validate_random_question_capacity(
        db: AsyncSession,
        *,
        question_bank_id: UUID,
        question_count: int,
    ) -> None:
        """
        Ensure a RANDOM configuration can be satisfied by its question bank.

        Both creation and later question reconfiguration use this helper so
        the RANDOM-capacity business rule has one implementation.
        """

        active_question_count = await QuestionRepository.count_questions_for_bank(
            db,
            question_bank_id,
            active_only=True,
        )

        if active_question_count < question_count:
            raise ValueError(
                "Question bank does not contain enough active questions "
                "for the requested question count"
            )

    @staticmethod
    async def create_exam(
        db: AsyncSession,
        *,
        actor: LocalActor,
        payload: ExamCreate,
    ) -> Exam:
        """
        Create a new revision-1 examination in DRAFT state.

        This operation validates:
        - the actor may author the curriculum subject
        - the session exists
        - the term belongs to that session
        - the assessment scheme exists
        - the assessment component belongs to that scheme
        - the question bank exists and is active
        - the question bank belongs to the curriculum subject
        - another revision-1 exam with the same logical identity does
          not already exist

        This operation intentionally does NOT:
        - select or freeze questions
        - resolve target classes
        - build the candidate roster
        - freeze the assessment component maximum
        - submit or seal the examination

        Those operations belong to later lifecycle methods.
        """

        # check if actor has authoring rights
        await AcademicAuthorizationService.require_can_author_curriculum_subject(
            db,
            actor=actor,
            curriculum_subject_id=payload.curriculum_subject_id,
        )

        # grab the session the author is trying to author for
        session = await AcademicRepository.get_session_by_id(
            db,
            session_id=payload.session_id,
        )

        if session is None:
            raise AcademicScopeError(
                "Academic session does not exist or is no longer available"
            )

        # grab the term the author is trying to author for
        term = await AcademicRepository.get_term_by_id(
            db,
            term_id=payload.term_id,
        )

        if term is None:
            raise AcademicScopeError(
                "Academic term does not exist or is no longer available"
            )

        # check if the academic term being authored for belongs in the
        # correct session chosen by author
        if term.academic_session_id != session.id:
            raise AcademicScopeError(
                "Academic term does not belong to the selected academic session"
            )

        # validate assessment scheme and component
        assessment_scheme = await AcademicRepository.get_assessment_scheme_by_id(
            db,
            scheme_id=payload.assessment_scheme_id,
        )

        if assessment_scheme is None:
            raise AcademicScopeError(
                "Assessment scheme does not exist or is no longer available"
            )

        assessment_component = await AcademicRepository.get_component_by_id(
            db,
            component_id=payload.assessment_component_id,
        )

        if assessment_component is None:
            raise AcademicScopeError(
                "Assessment component does not exist or is no longer available"
            )

        if assessment_component.assessment_scheme_id != assessment_scheme.id:
            raise AcademicScopeError(
                "Assessment component does not belong to the selected assessment scheme"
            )

        # validate and make sure question bank exists for the target subject
        question_bank = await QuestionRepository.get_bank_by_id(
            db,
            bank_id=payload.question_bank_id,
        )

        if question_bank is None:
            raise ValueError("Question bank does not exist")

        if not question_bank.is_active:
            raise ValueError("Question bank is inactive")

        if question_bank.curriculum_subject_id != payload.curriculum_subject_id:
            raise ValueError(
                "Question bank does not belong to the selected curriculum subject"
            )

        question_selection_mode = ExamQuestionSelectionMode(
            payload.question_selection_mode
        )

        if question_selection_mode == ExamQuestionSelectionMode.RANDOM:
            await ExamService._validate_random_question_capacity(
                db,
                question_bank_id=question_bank.id,
                question_count=payload.question_count,
            )

        # prevent duplicate revision-1 exam
        existing_exam = await ExamRepository.get_exam_revision(
            db,
            term_id=payload.term_id,
            curriculum_subject_id=payload.curriculum_subject_id,
            assessment_component_id=payload.assessment_component_id,
            title=payload.title,
            revision_number=1,
        )

        if existing_exam is not None:
            raise ValueError(
                "An examination with this title already exists for "
                "the selected term, curriculum subject and assessment "
                "component"
            )

        # build draft exam
        exam = Exam(
            session_id=session.id,
            term_id=term.id,
            curriculum_subject_id=payload.curriculum_subject_id,
            assessment_scheme_id=assessment_scheme.id,
            assessment_component_id=assessment_component.id,
            question_bank_id=question_bank.id,
            question_selection_mode=question_selection_mode,
            question_count=payload.question_count,
            title=payload.title,
            instructions=_normalize_optional_text(payload.instructions),
            duration_minutes=payload.duration_minutes,
            shuffle_questions=payload.shuffle_questions,
            shuffle_options=payload.shuffle_options,
            scheduled_start_at=payload.scheduled_start_at,
            latest_normal_start_at=payload.latest_normal_start_at,
            # lifecycle-owned values
            status=ExamStatus.DRAFT,
            roster_status=ExamRosterStatus.NOT_PREPARED,
            roster_version=0,
            roster_candidate_count=0,
            revision_number=1,
            revision_of_exam_id=None,
            created_by_actor_id=actor.id,
            # intentionally frozen later during sealing
            component_maximum_score=None,
        )

        try:
            exam = await ExamRepository.add_exam(
                db,
                exam,
            )

            await db.commit()

        except IntegrityError as exc:
            await db.rollback()

            raise ValueError(
                "The examination could not be created because its "
                "configuration conflicts with existing examination data"
            ) from exc

        return exam

    @staticmethod
    async def update_exam(
        db: AsyncSession,
        *,
        actor: LocalActor,
        payload: ExamUpdate,
        exam_id: UUID,
    ) -> Exam:
        """
        Update an existing examination while it is still in DRAFT state.

        This operation validates:
        - the examination exists
        - the examination is still in DRAFT state
        - the actor may author the examination's curriculum subject
        - the final term belongs to the final session
        - the final assessment component belongs to the final scheme
        - the current question bank remains valid
        - the final scheduling window is valid
        - the update does not create a duplicate examination identity

        Only the fields explicitly supplied by the PATCH payload are changed.
        """

        # grab and lock exam so two updates cannot modify
        # the same examination at the same time
        exam = await ExamRepository.get_exam_by_id(
            db,
            exam_id=exam_id,
            lock=True,
        )

        if exam is None:
            raise ExamNotFound("Examination does not exist")

        # only draft exams can be modified
        if exam.status != ExamStatus.DRAFT:
            raise ExamStateError("Only examinations in DRAFT state can be edited")

        # make sure actor can manage examinations for the current
        # curriculum-subject scope
        await AcademicAuthorizationService.require_can_author_curriculum_subject(
            db,
            actor=actor,
            curriculum_subject_id=exam.curriculum_subject_id,
        )

        # grab only fields actually supplied by PATCH request
        fields = payload.model_fields_set

        if not fields:
            await db.commit()
            return exam

        # required model fields may be omitted from PATCH but cannot
        # explicitly be changed to NULL
        required_fields = {
            "session_id",
            "term_id",
            "assessment_scheme_id",
            "assessment_component_id",
            "title",
            "duration_minutes",
            "shuffle_questions",
            "shuffle_options",
        }

        for field_name in required_fields:
            if field_name in fields and getattr(payload, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")

        # build final academic scope
        next_session_id = (
            payload.session_id if "session_id" in fields else exam.session_id
        )

        next_term_id = payload.term_id if "term_id" in fields else exam.term_id

        next_assessment_scheme_id = (
            payload.assessment_scheme_id
            if "assessment_scheme_id" in fields
            else exam.assessment_scheme_id
        )

        next_assessment_component_id = (
            payload.assessment_component_id
            if "assessment_component_id" in fields
            else exam.assessment_component_id
        )

        next_title = payload.title if "title" in fields else exam.title

        next_duration_minutes = (
            payload.duration_minutes
            if "duration_minutes" in fields
            else exam.duration_minutes
        )

        next_shuffle_questions = (
            payload.shuffle_questions
            if "shuffle_questions" in fields
            else exam.shuffle_questions
        )

        next_shuffle_options = (
            payload.shuffle_options
            if "shuffle_options" in fields
            else exam.shuffle_options
        )

        assert next_session_id is not None
        assert next_term_id is not None
        assert next_assessment_scheme_id is not None
        assert next_assessment_component_id is not None
        assert next_title is not None
        assert next_duration_minutes is not None
        assert next_shuffle_questions is not None
        assert next_shuffle_options is not None

        # validate final academic session
        session = await AcademicRepository.get_session_by_id(
            db,
            session_id=next_session_id,
        )

        if session is None:
            raise AcademicScopeError(
                "Academic session does not exist or is no longer available"
            )

        # validate final academic term
        term = await AcademicRepository.get_term_by_id(
            db,
            term_id=next_term_id,
        )

        if term is None:
            raise AcademicScopeError(
                "Academic term does not exist or is no longer available"
            )

        if term.academic_session_id != session.id:
            raise AcademicScopeError(
                "Academic term does not belong to the selected academic session"
            )

        # validate final assessment scheme
        assessment_scheme = await AcademicRepository.get_assessment_scheme_by_id(
            db,
            scheme_id=next_assessment_scheme_id,
        )

        if assessment_scheme is None:
            raise AcademicScopeError(
                "Assessment scheme does not exist or is no longer available"
            )

        # validate final assessment component
        assessment_component = await AcademicRepository.get_component_by_id(
            db,
            component_id=next_assessment_component_id,
        )

        if assessment_component is None:
            raise AcademicScopeError(
                "Assessment component does not exist or is no longer available"
            )

        if assessment_component.assessment_scheme_id != assessment_scheme.id:
            raise AcademicScopeError(
                "Assessment component does not belong to the selected assessment scheme"
            )

        # validate current question bank
        question_bank = await QuestionRepository.get_bank_by_id(
            db,
            bank_id=exam.question_bank_id,
        )

        if question_bank is None:
            raise ValueError("The examination question bank no longer exists")

        if not question_bank.is_active:
            raise ValueError("The examination question bank is inactive")

        if question_bank.curriculum_subject_id != exam.curriculum_subject_id:
            raise ValueError(
                "The examination question bank does not belong to "
                "the examination curriculum subject"
            )

        # build final scheduling values
        next_scheduled_start_at = (
            payload.scheduled_start_at
            if "scheduled_start_at" in fields
            else exam.scheduled_start_at
        )

        next_latest_normal_start_at = (
            payload.latest_normal_start_at
            if "latest_normal_start_at" in fields
            else exam.latest_normal_start_at
        )

        if (
            next_scheduled_start_at is not None
            and next_latest_normal_start_at is not None
            and next_latest_normal_start_at < next_scheduled_start_at
        ):
            raise ValueError(
                "latest_normal_start_at cannot be earlier than scheduled_start_at"
            )

        # prevent duplicate final identity
        existing_exam = await ExamRepository.get_exam_revision(
            db,
            term_id=next_term_id,
            curriculum_subject_id=exam.curriculum_subject_id,
            assessment_component_id=next_assessment_component_id,
            title=next_title,
            revision_number=exam.revision_number,
        )

        if existing_exam is not None and existing_exam.id != exam.id:
            raise ValueError(
                "An examination with this title already exists for "
                "the selected term, curriculum subject and assessment "
                "component"
            )

        # apply academic scope changes
        if "session_id" in fields:
            exam.session_id = session.id

        if "term_id" in fields:
            exam.term_id = term.id

        if "assessment_scheme_id" in fields:
            exam.assessment_scheme_id = assessment_scheme.id

        if "assessment_component_id" in fields:
            exam.assessment_component_id = assessment_component.id

        # apply ordinary examination changes
        if "title" in fields:
            exam.title = next_title

        if "instructions" in fields:
            exam.instructions = _normalize_optional_text(payload.instructions)

        if "duration_minutes" in fields:
            exam.duration_minutes = next_duration_minutes

        if "shuffle_questions" in fields:
            exam.shuffle_questions = next_shuffle_questions

        if "shuffle_options" in fields:
            exam.shuffle_options = next_shuffle_options

        if "scheduled_start_at" in fields:
            exam.scheduled_start_at = payload.scheduled_start_at

        if "latest_normal_start_at" in fields:
            exam.latest_normal_start_at = payload.latest_normal_start_at

        try:
            exam = await ExamRepository.save_exam(
                db,
                exam,
            )

            await db.commit()

        except IntegrityError as exc:
            await db.rollback()

            raise ValueError(
                "The examination could not be updated because its "
                "configuration conflicts with existing examination data"
            ) from exc

        return exam

    @staticmethod
    async def configure_questions(
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
        payload: ExamQuestionConfiguration,
    ) -> Exam:
        """
        Configure how a DRAFT examination obtains its questions.

        This operation configures:
        - question bank
        - RANDOM or MANUAL selection mode
        - required question count

        Existing manual selections are preserved when:
        - the exam remains in MANUAL mode
        - the question bank does not change

        Existing manual selections may be cleared when:
        - the question bank changes
        - MANUAL mode changes to RANDOM
        - stale manual selections exist while changing RANDOM to MANUAL

        Destructive changes to valid MANUAL work require explicit
        clear_existing_manual_selections confirmation from the caller.

        This operation does NOT add manual questions.
        Manual questions are managed incrementally by dedicated services.
        """

        # grab and lock exam so question configuration cannot race
        # with another update or lifecycle transition
        exam = await ExamRepository.get_exam_by_id(
            db,
            exam_id=exam_id,
            lock=True,
        )

        if exam is None:
            raise ExamNotFound("Examination does not exist")

        if exam.status != ExamStatus.DRAFT:
            raise ExamStateError(
                "Questions can only be configured while the examination "
                "is in DRAFT state"
            )

        # authorize against the immutable curriculum-subject scope
        await AcademicAuthorizationService.require_can_author_curriculum_subject(
            db,
            actor=actor,
            curriculum_subject_id=exam.curriculum_subject_id,
        )

        # validate and lock selected question bank
        question_bank = await QuestionRepository.get_bank_by_id(
            db,
            bank_id=payload.question_bank_id,
            lock=True,
        )

        if question_bank is None:
            raise ValueError("Question bank does not exist")

        if not question_bank.is_active:
            raise ValueError("Question bank is inactive")

        if question_bank.curriculum_subject_id != exam.curriculum_subject_id:
            raise ValueError(
                "Question bank does not belong to the examination curriculum subject"
            )

        question_selection_mode = ExamQuestionSelectionMode(
            payload.question_selection_mode
        )

        existing_selections = await ExamRepository.list_question_selections(
            db,
            exam.id,
        )

        bank_changed = question_bank.id != exam.question_bank_id

        preserve_manual_selections = (
            exam.question_selection_mode == ExamQuestionSelectionMode.MANUAL
            and question_selection_mode == ExamQuestionSelectionMode.MANUAL
            and not bank_changed
        )

        # Existing MANUAL work is only destroyed when the caller explicitly
        # acknowledges the destructive transition. This prevents an accidental
        # mode or bank change from silently wiping authored question choices.
        destructive_manual_change = (
            bool(existing_selections)
            and exam.question_selection_mode == ExamQuestionSelectionMode.MANUAL
            and (
                question_selection_mode != ExamQuestionSelectionMode.MANUAL
                or bank_changed
            )
        )

        if destructive_manual_change and not payload.clear_existing_manual_selections:
            raise ValueError(
                "This question configuration change would remove existing "
                "manual question selections. Set "
                "clear_existing_manual_selections=true to confirm the change"
            )

        should_clear_manual_selections = False

        if question_selection_mode == ExamQuestionSelectionMode.RANDOM:
            await ExamService._validate_random_question_capacity(
                db,
                question_bank_id=question_bank.id,
                question_count=payload.question_count,
            )

            # RANDOM exams must not retain manual selection references.
            # For valid MANUAL work, destructive confirmation was checked above.
            if existing_selections:
                should_clear_manual_selections = True

        elif question_selection_mode == ExamQuestionSelectionMode.MANUAL:
            if preserve_manual_selections:
                # Existing selections survive configuration changes on the
                # same MANUAL bank, but the required count cannot be reduced
                # below the amount already selected.
                if len(existing_selections) > payload.question_count:
                    raise ValueError(
                        "Question count cannot be lower than the number "
                        "of manually selected questions"
                    )

            else:
                # The bank changed or stale selections survived a previous
                # non-MANUAL state. They cannot belong to this configuration.
                # Valid MANUAL work requires confirmation before reaching here.
                if existing_selections:
                    should_clear_manual_selections = True

        else:
            raise ValueError("Unsupported question selection mode")

        try:
            if should_clear_manual_selections:
                await ExamRepository.clear_question_selections(
                    db,
                    exam.id,
                )

            exam.question_bank_id = question_bank.id
            exam.question_selection_mode = question_selection_mode
            exam.question_count = payload.question_count

            exam = await ExamRepository.save_exam(
                db,
                exam,
            )

            await db.commit()

        except IntegrityError as exc:
            await db.rollback()

            raise ValueError(
                "The examination question configuration could not be "
                "saved because it conflicts with existing examination data"
            ) from exc

        return exam

    @staticmethod
    async def _require_manual_draft_exam(
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
    ) -> Exam:
        """
        Load and authorize a DRAFT examination configured for MANUAL selection.

        The examination row is locked so all manual-selection mutations
        serialize through the same examination.
        """

        exam = await ExamRepository.get_exam_by_id(
            db,
            exam_id=exam_id,
            lock=True,
        )

        if exam is None:
            raise ExamNotFound("Examination does not exist")

        if exam.status != ExamStatus.DRAFT:
            raise ExamStateError(
                "Manual questions can only be changed while the "
                "examination is in DRAFT state"
            )

        if exam.question_selection_mode != ExamQuestionSelectionMode.MANUAL:
            raise ExamStateError(
                "Manual questions can only be managed when the "
                "examination question selection mode is MANUAL"
            )

        await AcademicAuthorizationService.require_can_author_curriculum_subject(
            db,
            actor=actor,
            curriculum_subject_id=exam.curriculum_subject_id,
        )

        return exam

    @staticmethod
    async def add_manual_questions(
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
        payload: ManualQuestionAdd,
    ) -> Exam:
        """
        Add one or more questions to a MANUAL DRAFT examination.

        This operation is incremental.

        Existing selections remain intact. New questions are appended
        after the current final position.

        This allows multiple authorized teachers to contribute questions
        to the same shared examination over time.
        """

        exam = await ExamService._require_manual_draft_exam(
            db,
            actor=actor,
            exam_id=exam_id,
        )

        question_ids = payload.question_ids

        if not question_ids:
            raise ValueError("At least one question must be selected")

        if len(question_ids) != len(set(question_ids)):
            raise ValueError("Question selections cannot contain duplicate questions")

        # make sure current bank still exists and remains valid
        question_bank = await QuestionRepository.get_bank_by_id(
            db,
            bank_id=exam.question_bank_id,
            lock=True,
        )

        if question_bank is None:
            raise ValueError("The examination question bank no longer exists")

        if not question_bank.is_active:
            raise ValueError("The examination question bank is inactive")

        if question_bank.curriculum_subject_id != exam.curriculum_subject_id:
            raise ValueError(
                "The examination question bank does not belong to "
                "the examination curriculum subject"
            )

        existing_selections = await ExamRepository.list_question_selections(
            db,
            exam.id,
        )

        existing_question_ids = {
            selection.question_id for selection in existing_selections
        }

        duplicate_existing_ids = existing_question_ids & set(question_ids)

        if duplicate_existing_ids:
            raise ValueError(
                "One or more selected questions have already been "
                "added to this examination"
            )

        final_selection_count = len(existing_selections) + len(question_ids)

        if final_selection_count > exam.question_count:
            raise ValueError(
                "Adding these questions would exceed the examination question count"
            )

        questions = await QuestionRepository.list_questions_by_ids(
            db,
            question_ids,
            active_only=True,
        )

        questions_by_id = {question.id: question for question in questions}

        # incoming IDs are already unique, therefore a count mismatch
        # means at least one question does not exist or is inactive
        if len(questions_by_id) != len(question_ids):
            raise ValueError(
                "One or more selected questions do not exist or are inactive"
            )

        for question_id in question_ids:
            question = questions_by_id[question_id]

            if question.bank_id != question_bank.id:
                raise ValueError(
                    "All selected questions must belong to the "
                    "examination question bank"
                )

        current_final_position = max(
            (selection.position for selection in existing_selections),
            default=0,
        )

        selections = [
            ExamQuestionSelection(
                exam_id=exam.id,
                question_id=question_id,
                position=current_final_position + offset,
            )
            for offset, question_id in enumerate(
                question_ids,
                start=1,
            )
        ]

        try:
            await ExamRepository.add_question_selections(
                db,
                selections,
            )

            await db.commit()

        except IntegrityError as exc:
            await db.rollback()

            raise ValueError(
                "The selected questions could not be added because "
                "they conflict with the current examination selection"
            ) from exc

        return exam

    @staticmethod
    async def remove_manual_question(
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
        payload: ManualQuestionRemove,
    ) -> Exam:
        """
        Remove one selected question from a MANUAL DRAFT examination.

        The source Question row is NOT deleted.

        Remaining ExamQuestionSelection rows are compacted so their
        positions remain continuous.
        """

        exam = await ExamService._require_manual_draft_exam(
            db,
            actor=actor,
            exam_id=exam_id,
        )

        question_id = payload.question_id

        selection = await ExamRepository.get_question_selection(
            db,
            exam_id=exam.id,
            question_id=question_id,
            lock=True,
        )

        if selection is None:
            raise ValueError("Question is not selected for this examination")

        current_selections = await ExamRepository.list_question_selections(
            db,
            exam.id,
        )

        remaining_question_ids = [
            current_selection.question_id
            for current_selection in current_selections
            if current_selection.question_id != question_id
        ]

        try:
            # rebuild only the exam-owned selection references.
            # source Question rows remain untouched.
            await ExamRepository.clear_question_selections(
                db,
                exam.id,
            )

            if remaining_question_ids:
                await ExamRepository.add_question_selections(
                    db,
                    [
                        ExamQuestionSelection(
                            exam_id=exam.id,
                            question_id=remaining_question_id,
                            position=position,
                        )
                        for position, remaining_question_id in enumerate(
                            remaining_question_ids,
                            start=1,
                        )
                    ],
                )

            await db.commit()

        except IntegrityError as exc:
            await db.rollback()

            raise ValueError(
                "The manual question selection could not be updated "
                "because it conflicts with existing examination data"
            ) from exc

        return exam

    @staticmethod
    async def reorder_manual_questions(
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
        payload: ManualQuestionReorder,
    ) -> Exam:
        """
        Reorder the currently selected questions for a MANUAL DRAFT exam.

        This operation does not add or remove questions.

        The supplied IDs must represent exactly the current selected set.
        Their list order becomes the new canonical manual question order.
        """

        exam = await ExamService._require_manual_draft_exam(
            db,
            actor=actor,
            exam_id=exam_id,
        )
        question_ids = payload.question_ids

        if len(question_ids) != len(set(question_ids)):
            raise ValueError("Question order cannot contain duplicate questions")

        current_selections = await ExamRepository.list_question_selections(
            db,
            exam.id,
        )

        current_question_ids = [
            selection.question_id for selection in current_selections
        ]

        if len(question_ids) != len(current_question_ids) or set(question_ids) != set(
            current_question_ids
        ):
            raise ValueError(
                "Question order must contain exactly the questions "
                "currently selected for this examination"
            )

        # no persistence required when order is already correct
        if question_ids == current_question_ids:
            await db.commit()
            return exam

        try:
            # clear and recreate avoids temporary unique-position collisions
            # while changing canonical positions
            await ExamRepository.clear_question_selections(
                db,
                exam.id,
            )

            if question_ids:
                await ExamRepository.add_question_selections(
                    db,
                    [
                        ExamQuestionSelection(
                            exam_id=exam.id,
                            question_id=question_id,
                            position=position,
                        )
                        for position, question_id in enumerate(
                            question_ids,
                            start=1,
                        )
                    ],
                )

            await db.commit()

        except IntegrityError as exc:
            await db.rollback()

            raise ValueError(
                "The manual question order could not be updated because "
                "it conflicts with existing examination data"
            ) from exc

        return exam

    @staticmethod
    async def submit_exam(db: AsyncSession, *, actor: LocalActor, exam_id: UUID):
        """
        submit a completed DRAFT examination for administrative review

        Submission means authoring is complete

        This operation:
        -validates the examination still has a valid academic scope
        -validates the configured question bank
        -validates te scheduling window
        -validates the question configuration is complete
        -records who submitted the examination and when
        -transisions DRAFT - > SUBMITTED

        This operation intentionally does NOT:
        -randomly choose questions
        - freeze Question rows into ExamQuestion rows
        -freeze question options
        -freeze the assessment-component maximum
        -resolve target classes
        -build the candidate roster
        -make the examination available to candidates
        This operations belong to sealing and later lifecycle stages
        """

        exam = await ExamRepository.get_exam_by_id(db, exam_id=exam_id, lock=True)

        if exam is None:
            raise ExamNotFound("Examination does not exist")

        if exam.status != ExamStatus.DRAFT:
            raise ExamStateError("Only examination in DRAFT state can be submitted")

        await AcademicAuthorizationService.require_can_author_curriculum_subject(
            db, actor=actor, curriculum_subject_id=exam.curriculum_subject_id
        )

        session = await AcademicRepository.get_session_by_id(
            db, session_id=exam.session_id
        )

        if session is None:
            raise AcademicScopeError(
                "Academic session does not exist or is no longer available"
            )

        term = await AcademicRepository.get_term_by_id(db, term_id=exam.term_id)

        if term is None:
            raise AcademicScopeError(
                "Academic term does not exist or is no longer available"
            )

        if term.academic_session_id != session.id:
            raise AcademicScopeError(
                "Academic term does not belong to the examination academic session"
            )

        assessment_scheme = await AcademicRepository.get_assessment_scheme_by_id(
            db, scheme_id=exam.assessment_scheme_id
        )

        if assessment_scheme is None:
            raise AcademicScopeError(
                "Assessment scheme does not exist or is no longer available"
            )

        assessment_component = await AcademicRepository.get_component_by_id(
            db, component_id=exam.assessment_component_id
        )

        if assessment_component is None:
            raise AcademicScopeError(
                "Assessment component does not exist or is no longer available"
            )

        if assessment_component.assessment_scheme_id != assessment_scheme.id:
            raise AcademicScopeError(
                "Assessment component does not belong to "
                "the examination assessment scheme"
            )

        question_bank = await QuestionRepository.get_bank_by_id(
            db, bank_id=exam.question_bank_id
        )

        if question_bank is None:
            raise ValueError("The examination question bank no longer exists")

        if not question_bank.is_active:
            raise ValueError("The examination question bank is inactive")

        if question_bank.curriculum_subject_id != exam.curriculum_subject_id:
            raise ValueError(
                "The examination question bank does not belong to "
                "the examination curriculum subject"
            )

        if (
            exam.scheduled_start_at is not None
            and exam.latest_normal_start_at is not None
            and exam.latest_normal_start_at < exam.scheduled_start_at
        ):
            raise ValueError(
                "latest_normal_start_at cannot be eariler than_scheduled_start_at"
            )

        question_selection_mode = ExamQuestionSelectionMode(
            exam.question_selection_mode
        )

        if question_selection_mode == ExamQuestionSelectionMode.RANDOM:
            await ExamService._validate_random_question_capacity(
                db,
                question_bank_id=question_bank.id,
                question_count=exam.question_count,
            )

            existing_selections = await ExamRepository.list_question_selections(
                db, exam.id
            )

            if existing_selections:
                raise ValueError(
                    "RANDOM mode examinations cannot contain manual question selections"
                )

        elif question_selection_mode == ExamQuestionSelectionMode.MANUAL:
            selections = await ExamRepository.list_question_selections(db, exam.id)

            if len(selections) != exam.question_count:
                raise ValueError(
                    "This MANUAL mode examination must contain exactly "
                    f"{exam.question_count}  selected questions before submission"
                )

            expected_positions = list(range(1, exam.question_count + 1))

            actual_positions = [selection.position for selection in selections]

            if actual_positions != expected_positions:
                raise ValueError(
                    "MANUAL mode question selections must have continuous "
                    "positions before submission"
                )

            selected_question_ids = [selection.question_id for selection in selections]

            questions = await QuestionRepository.list_questions_by_ids(
                db, selected_question_ids, active_only=True
            )

            questions_by_id = {question.id: question for question in questions}

            if len(questions_by_id) != len(selected_question_ids):
                raise ValueError(
                    "One or more manually selected questions "
                    "no longer exist or are inactive"
                )

            for question_id in selected_question_ids:
                question = questions_by_id[question_id]

                if question.bank_id != question_bank.id:
                    raise ValueError(
                        "All manually selected questions must belong "
                        "to the examination question bank"
                    )

        else:
            raise ValueError("Unsupported question selection mode")

        exam.status = ExamStatus.SUBMITTED
        exam.submitted_by_actor_id = actor.id
        exam.submitted_at = datetime.now(UTC)

        try:
            exam = await ExamRepository.save_exam(db, exam)

            await db.commit()

        except IntegrityError as exc:
            await db.rollback()
            raise ValueError(
                "The examination could not be submitted because "
                "its current state conflicts with existing examination data"
            ) from exc

        return exam

    @staticmethod
    async def _resolve_questions_for_sealing(
        db: AsyncSession,
        *,
        exam: Exam,
    ) -> list:
        """
        Resolve and lock the exact source Questions that will form
        the sealed paper.

        RANDOM:
            randomly selects exactly exam.question_count active questions.

        MANUAL:
            uses exactly the author's ExamQuestionSelection rows
            in canonical position order.
        """

        if exam.question_selection_mode == ExamQuestionSelectionMode.RANDOM:
            available_questions = await QuestionRepository.list_questions_for_bank(
                db,
                exam.question_bank_id,
                active_only=True,
            )

            if len(available_questions) < exam.question_count:
                raise ValueError(
                    "Question bank no longer contains enough active questions "
                    "to seal this examination"
                )

            selected_ids = SystemRandom().sample(
                [question.id for question in available_questions],
                exam.question_count,
            )

            # Re-read the exact selected rows under locks.
            selected_questions = await QuestionRepository.list_questions_by_ids(
                db,
                selected_ids,
                active_only=True,
                lock=True,
            )

            questions_by_id = {question.id: question for question in selected_questions}

            if len(questions_by_id) != exam.question_count:
                raise ValueError(
                    "One or more randomly selected questions became "
                    "unavailable while sealing the examination"
                )

            # SystemRandom.sample determines the canonical frozen order.
            return [questions_by_id[question_id] for question_id in selected_ids]

        if exam.question_selection_mode == ExamQuestionSelectionMode.MANUAL:
            selections = await ExamRepository.list_question_selections(
                db,
                exam.id,
            )

            if len(selections) != exam.question_count:
                raise ValueError(
                    "A MANUAL examination must contain exactly "
                    f"{exam.question_count} selected questions before sealing"
                )

            expected_positions = list(range(1, exam.question_count + 1))

            actual_positions = [selection.position for selection in selections]

            if actual_positions != expected_positions:
                raise ValueError(
                    "Manual question selections must have continuous "
                    "positions before sealing"
                )

            selected_ids = [selection.question_id for selection in selections]

            selected_questions = await QuestionRepository.list_questions_by_ids(
                db,
                selected_ids,
                active_only=True,
                lock=True,
            )

            questions_by_id = {question.id: question for question in selected_questions}

            if len(questions_by_id) != exam.question_count:
                raise ValueError(
                    "One or more manually selected questions "
                    "no longer exist or are inactive"
                )

            # Preserve the author's canonical manual order.
            return [questions_by_id[question_id] for question_id in selected_ids]

        raise ValueError("Unsupported question selection mode")

    @staticmethod
    async def _validate_questions_for_sealing(
        db: AsyncSession,
        *,
        exam: Exam,
        questions: list,
    ) -> dict[UUID, list]:
        """
        Validate that every selected source question is still executable.

        Returns source options grouped by source Question.id so sealing
        can snapshot them without re-querying.
        """

        question_ids = [question.id for question in questions]

        options = await QuestionRepository.list_options_for_questions(
            db,
            question_ids,
        )

        options_by_question_id: dict[UUID, list] = {
            question_id: [] for question_id in question_ids
        }

        for option in options:
            options_by_question_id[option.question_id].append(option)

        for question in questions:
            if question.bank_id != exam.question_bank_id:
                raise ValueError(
                    "All examination questions must belong to "
                    "the examination question bank"
                )

            question_options = options_by_question_id[question.id]

            if len(question_options) < 2:
                raise ValueError(
                    "Every examination question must contain "
                    "at least two answer options"
                )

            expected_positions = list(range(1, len(question_options) + 1))

            actual_positions = [option.position for option in question_options]

            if actual_positions != expected_positions:
                raise ValueError(
                    "Question options must have continuous positions "
                    "before the examination can be sealed"
                )

            comparable_text = [
                option.text.strip().casefold() for option in question_options
            ]

            if len(comparable_text) != len(set(comparable_text)):
                raise ValueError(
                    "Question options must be unique before "
                    "the examination can be sealed"
                )

            correct_count = sum(1 for option in question_options if option.is_correct)

            if question.question_type == QuestionType.SINGLE_CHOICE:
                if correct_count != 1:
                    raise ValueError(
                        "A single-choice examination question must "
                        "have exactly one correct option"
                    )

            elif question.question_type == QuestionType.MULTIPLE_CHOICE:
                if correct_count < 2:
                    raise ValueError(
                        "A multiple-choice examination question must "
                        "have at least two correct options"
                    )

                if correct_count == len(question_options):
                    raise ValueError(
                        "A multiple-choice examination question must "
                        "have at least one incorrect option"
                    )

            else:
                raise ValueError("Unsupported examination question type")

        return options_by_question_id

    @staticmethod
    async def seal_exam(db: AsyncSession, *, actor: LocalActor, exam_id: UUID):
        """
        Permanently freeze a SUBMITTED examination

        Only a school administrator may seal an examination


        Sealing:
        -revalidates the academic scope
        -resolves the final source questions
        - snapshots questions and answer options
        - freezes the assessment-component maximum
        -resolves and freezes eligible target classes
        - transitions SUBMITTED -> SEALED
        - marks candidate-roster preparation as PENDING
        - records a durable exam.sealed outbox event

        A SEALED examination must never become editable again
        """

        exam = await ExamRepository.get_exam_by_id(db, exam_id=exam_id, lock=True)

        if exam is None:
            raise ExamNotFound("Examination does not exist")

        if exam.status != ExamStatus.SUBMITTED:
            raise ExamStateError("Only examinations in SUBMITTED state can be sealed")

        if not actor.is_active:
            raise AcademicAuthorizationError("Active local actor is required")

        if actor.role != "admin":
            raise AcademicAuthorizationError(
                "Only school administrators can seal examinations"
            )

        await AcademicAuthorizationService.require_can_author_curriculum_subject(
            db, actor=actor, curriculum_subject_id=exam.curriculum_subject_id
        )

        session = await AcademicRepository.get_session_by_id(
            db, session_id=exam.session_id
        )

        if session is None:
            raise AcademicScopeError(
                "Academic Session does not exist or is no longer available"
            )

        term = await AcademicRepository.get_term_by_id(db, term_id=exam.term_id)

        if term is None:
            raise AcademicScopeError(
                "Academic term does not exist or is no longer available"
            )

        if term.academic_session_id != session.id:
            raise AcademicScopeError(
                "Academic term does not belong to the examination academic session"
            )

        assessment_scheme = await AcademicRepository.get_assessment_scheme_by_id(
            db, scheme_id=exam.assessment_scheme_id
        )

        if assessment_scheme is None:
            raise AcademicScopeError(
                "Assessment scheme does not exist or is no longer available"
            )

        if assessment_scheme.status != "active":
            raise AcademicScopeError("Assessment scheme is no longer active")

        assessment_component = await AcademicRepository.get_component_by_id(
            db, component_id=exam.assessment_component_id
        )

        if assessment_component is None:
            raise AcademicScopeError(
                "Assessment component does not exist or is no longer available"
            )

        if not assessment_component.is_active:
            raise AcademicScopeError("Assessment component is no longer active")

        if assessment_component.assessment_scheme_id != assessment_scheme.id:
            raise AcademicScopeError(
                "Assessment component does not belong to "
                "the examination assessment scheme"
            )

        question_bank = await QuestionRepository.get_bank_by_id(
            db, bank_id=exam.question_bank_id, lock=True
        )

        if question_bank is None:
            raise ValueError("The examination question bank no longer exists")

        if not question_bank.is_active:
            raise ValueError("The examination question bank is inactive")

        if question_bank.curriculum_subject_id != exam.curriculum_subject_id:
            raise ValueError(
                "The examination question bank does not belong to "
                "the examination curriculum subject"
            )

        if await ExamRepository.count_exam_questions(db, exam.id):
            raise ExamStateError(
                "submitted examination already contains frozen questions"
            )

        questions = await ExamService._resolve_questions_for_sealing(db, exam=exam)

        if len(questions) != exam.question_count:
            raise ValueError(
                "Resolved examination question count does not match "
                "the configured question count"
            )

        options_by_question_id = await ExamService._validate_questions_for_sealing(
            db, exam=exam, questions=questions
        )

        # target classes
        classes = await AcademicRepository.list_classes_for_curriculum_subject(
            db, curriculum_subject_id=exam.curriculum_subject_id
        )

        target_classes: list[ExamTargetClass] = []

        # determine if class is eligible for curriculum subject
        # handles both general and department-specific offerings
        for classroom in classes:
            offering = await AcademicRepository.get_offering_for_class_scope(
                db,
                academic_term_id=exam.term_id,
                curriculum_subject_id=exam.curriculum_subject_id,
                class_id=classroom.id,
            )

            if offering is None:
                continue

            assignment = await AcademicRepository.get_active_assignment_for_class_curriculum_subject(
                db,
                classroom.id,
                exam.curriculum_subject_id,
            )

            target_classes.append(
                ExamTargetClass(
                    exam_id=exam.id,
                    class_id=classroom.id,
                    subject_offering_id=offering.id,
                    teacher_assignment_id=(
                        assignment.id if assignment is not None else None
                    ),
                )
            )

        if not target_classes:
            raise AcademicScopeError(
                "Examination has no academically eligible target classes "
                "for the selected term"
            )

        # build frozen snapshot

        frozen_questions = [
            ExamQuestion(
                exam_id=exam.id,
                source_question_id=question.id,
                source_question_version=question.version,
                question_type=question.question_type,
                position=position,
                prompt=question.prompt,
                instruction=question.instruction,
                image_asset_id=question.image_asset_id,
            )
            for position, question in enumerate(questions, start=1)
        ]

        sealed_at = datetime.now(UTC)

        try:
            frozen_questions = await ExamRepository.add_exam_questions(
                db, frozen_questions
            )

            frozen_questions_by_source_id = {
                frozen_question.source_question_id: frozen_question
                for frozen_question in frozen_questions
            }

            frozen_options: list[ExamQuestionOption] = []

            for source_question in questions:
                frozen_question = frozen_questions_by_source_id[source_question.id]

                for source_option in options_by_question_id[source_question.id]:
                    frozen_options.append(
                        ExamQuestionOption(
                            exam_question_id=frozen_question.id,
                            position=source_option.position,
                            text=source_option.text,
                            is_correct=source_option.is_correct,
                        )
                    )

            await ExamRepository.add_exam_question_options(
                db,
                frozen_options,
            )

            # Freeze the concrete delivery scope.
            await ExamRepository.add_target_classes(
                db,
                target_classes,
            )

            # Manual selection rows are DRAFT authoring state only.
            #
            # ExamQuestion now permanently preserves both the selected
            # source question and its canonical position.
            if exam.question_selection_mode == ExamQuestionSelectionMode.MANUAL:
                await ExamRepository.clear_question_selections(
                    db,
                    exam.id,
                )

            # Freeze the Weave assessment-component maximum at the exact
            # point the paper becomes immutable.
            exam.component_maximum_score = assessment_component.maximum_score

            # Lifecycle state.
            exam.status = ExamStatus.SEALED
            exam.sealed_by_actor_id = actor.id
            exam.sealed_at = sealed_at

            # Candidate roster is intentionally not built inside this request.
            exam.roster_status = ExamRosterStatus.PENDING
            exam.roster_candidate_count = 0
            exam.roster_prepared_at = None
            exam.roster_error = None

            exam = await ExamRepository.save_exam(
                db,
                exam,
            )

            # Transactional outbox:
            #
            # If the exam commits, this event commits.
            # If the exam rolls back, the event disappears too.
            await RuntimeRepository.add_outbox_event(
                db,
                RealtimeOutboxEvent(
                    aggregate_type="exam",
                    aggregate_id=exam.id,
                    event_type="exam.sealed",
                    payload={
                        "exam_id": str(exam.id),
                        "status": ExamStatus.SEALED.value,
                        "revision_number": exam.revision_number,
                        "question_count": exam.question_count,
                        "target_class_count": len(target_classes),
                        "roster_status": ExamRosterStatus.PENDING.value,
                        "sealed_by_actor_id": str(actor.id),
                        "sealed_at": sealed_at.isoformat(),
                    },
                ),
            )

            await db.commit()

        except IntegrityError as exc:
            await db.rollback()

            raise ValueError(
                "The examination could not be sealed because its "
                "final configuration conflicts with existing examination data"
            ) from exc

        return exam

    @staticmethod
    async def return_exam_to_draft(
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
    ) -> Exam:
        ExamService._require_admin(actor)
        exam = await ExamRepository.get_exam_by_id(db, exam_id=exam_id, lock=True)
        if exam is None:
            raise ExamNotFound("Examination does not exist")
        if exam.status != ExamStatus.SUBMITTED:
            raise ExamStateError(
                "Only examinations in SUBMITTED state can return to draft"
            )
        exam.status = ExamStatus.DRAFT
        exam.submitted_by_actor_id = None
        exam.submitted_at = None
        try:
            exam = await ExamRepository.save_exam(db, exam)
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ValueError(
                "The examination could not return to draft because its "
                "current state conflicts with existing examination data"
            ) from exc
        return exam

    @staticmethod
    async def delete_draft_exam(
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
    ) -> None:
        exam = await ExamRepository.get_exam_by_id(db, exam_id=exam_id, lock=True)
        if exam is None:
            raise ExamNotFound("Examination does not exist")
        if exam.status != ExamStatus.DRAFT:
            raise ExamStateError("Only DRAFT examinations can be deleted")
        if actor.role == "admin":
            if not actor.is_active:
                raise AcademicAuthorizationError("Active local actor is required")
        elif exam.created_by_actor_id == actor.id:
            await AcademicAuthorizationService.require_can_author_curriculum_subject(
                db,
                actor=actor,
                curriculum_subject_id=exam.curriculum_subject_id,
            )
        else:
            raise AcademicAuthorizationError(
                "Only an administrator or the current authorized exam author "
                "can delete this draft examination"
            )
        try:
            await ExamRepository.delete_exam(db, exam)
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ValueError(
                "The draft examination could not be deleted because it is "
                "referenced by existing examination data"
            ) from exc

    @staticmethod
    async def list_available_invigilators(db: AsyncSession, *, actor: LocalActor):
        ExamService._require_admin(actor)
        return await AcademicRepository.list_teachers(db, active_only=True)

    @staticmethod
    async def list_invigilators(
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
    ) -> list[ExamInvigilator]:
        ExamService._require_admin(actor)
        exam = await ExamRepository.get_exam_by_id(db, exam_id=exam_id)
        if exam is None:
            raise ExamNotFound("Examination does not exist")
        return await ExamRepository.list_invigilators_for_exam(db, exam.id)

    @staticmethod
    async def assign_invigilators(
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
        teacher_ids: list[UUID],
    ) -> list[ExamInvigilator]:
        ExamService._require_admin(actor)
        unique_teacher_ids = list(dict.fromkeys(teacher_ids))
        exam = await ExamRepository.get_exam_by_id(db, exam_id=exam_id, lock=True)
        if exam is None:
            raise ExamNotFound("Examination does not exist")
        if exam.status in {ExamStatus.CLOSED, ExamStatus.CANCELLED}:
            raise ExamStateError(
                "Invigilators cannot be changed after an examination is closed "
                "or cancelled"
            )
        teachers = await AcademicRepository.list_teachers_by_ids(
            db,
            unique_teacher_ids,
            active_only=True,
        )
        found_teacher_ids = {teacher.id for teacher in teachers}
        missing_ids = [
            teacher_id
            for teacher_id in unique_teacher_ids
            if teacher_id not in found_teacher_ids
        ]
        if missing_ids:
            raise AcademicScopeError(
                "One or more teachers do not exist, are inactive, or have been deleted"
            )
        existing = await ExamRepository.list_invigilators_for_exam_and_teachers(
            db,
            exam_id=exam.id,
            teacher_ids=unique_teacher_ids,
            lock=True,
        )
        existing_teacher_ids = {row.teacher_id for row in existing}
        new_rows = [
            ExamInvigilator(exam_id=exam.id, teacher_id=teacher_id)
            for teacher_id in unique_teacher_ids
            if teacher_id not in existing_teacher_ids
        ]
        try:
            created = await ExamRepository.add_invigilators(db, new_rows)
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ValueError(
                "Invigilators could not be assigned because the assignment "
                "conflicts with existing examination data"
            ) from exc
        return [*existing, *created]

    @staticmethod
    async def remove_invigilators(
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
        teacher_ids: list[UUID],
    ) -> list[ExamInvigilator]:
        ExamService._require_admin(actor)
        unique_teacher_ids = list(dict.fromkeys(teacher_ids))
        exam = await ExamRepository.get_exam_by_id(db, exam_id=exam_id, lock=True)
        if exam is None:
            raise ExamNotFound("Examination does not exist")
        if exam.status in {ExamStatus.CLOSED, ExamStatus.CANCELLED}:
            raise ExamStateError(
                "Invigilators cannot be changed after an examination is closed "
                "or cancelled"
            )
        try:
            await ExamRepository.remove_invigilators_by_teacher_ids(
                db,
                exam_id=exam.id,
                teacher_ids=unique_teacher_ids,
            )
            remaining = await ExamRepository.list_invigilators_for_exam(db, exam.id)
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ValueError(
                "Invigilators could not be removed because the assignment "
                "conflicts with existing examination data"
            ) from exc
        return remaining

    @staticmethod
    async def create_revision(
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
    ) -> Exam:
        ExamService._require_admin(actor)
        exam = await ExamRepository.get_exam_by_id(db, exam_id=exam_id, lock=True)
        if exam is None:
            raise ExamNotFound("Examination does not exist")
        if exam.status in {ExamStatus.DRAFT, ExamStatus.SUBMITTED}:
            raise ExamStateError(
                "Only SEALED or later examinations require a new revision"
            )
        latest = await ExamService._latest_revision_in_lineage(db, exam)
        if latest.status in {ExamStatus.DRAFT, ExamStatus.SUBMITTED}:
            raise ExamStateError("The latest examination revision is still editable")
        await AcademicAuthorizationService.require_can_author_curriculum_subject(
            db,
            actor=actor,
            curriculum_subject_id=latest.curriculum_subject_id,
        )
        revision = Exam(
            session_id=latest.session_id,
            term_id=latest.term_id,
            curriculum_subject_id=latest.curriculum_subject_id,
            assessment_scheme_id=latest.assessment_scheme_id,
            assessment_component_id=latest.assessment_component_id,
            question_bank_id=latest.question_bank_id,
            question_selection_mode=latest.question_selection_mode,
            question_count=latest.question_count,
            title=latest.title,
            instructions=latest.instructions,
            duration_minutes=latest.duration_minutes,
            shuffle_questions=latest.shuffle_questions,
            shuffle_options=latest.shuffle_options,
            scheduled_start_at=latest.scheduled_start_at,
            latest_normal_start_at=latest.latest_normal_start_at,
            status=ExamStatus.DRAFT,
            roster_status=ExamRosterStatus.NOT_PREPARED,
            roster_version=0,
            roster_candidate_count=0,
            revision_number=latest.revision_number + 1,
            revision_of_exam_id=latest.id,
            created_by_actor_id=actor.id,
            component_maximum_score=None,
        )
        try:
            revision = await ExamRepository.add_exam(db, revision)
            if revision.question_selection_mode == ExamQuestionSelectionMode.MANUAL:
                frozen_questions = await ExamRepository.list_exam_questions(
                    db,
                    latest.id,
                )
                await ExamRepository.add_question_selections(
                    db,
                    [
                        ExamQuestionSelection(
                            exam_id=revision.id,
                            question_id=question.source_question_id,
                            position=question.position,
                        )
                        for question in frozen_questions
                    ],
                )
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ValueError(
                "The examination revision could not be created because it "
                "conflicts with existing examination data"
            ) from exc
        return revision

    @staticmethod
    async def activate_exam(
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
    ) -> Exam:
        ExamService._require_admin(actor)
        exam = await ExamRepository.get_exam_by_id(db, exam_id=exam_id, lock=True)
        if exam is None:
            raise ExamNotFound("Examination does not exist")
        if exam.status != ExamStatus.SEALED:
            raise ExamStateError("Only SEALED examinations can be activated")
        if exam.roster_status != ExamRosterStatus.READY:
            raise ExamStateError("Candidate roster must be READY before activation")
        frozen_count = await ExamRepository.count_exam_questions(db, exam.id)
        if frozen_count != exam.question_count:
            raise ExamStateError("Frozen question count does not match exam setup")
        if exam.sealed_at is None or exam.component_maximum_score is None:
            raise ExamStateError("Exam is missing required sealed state")
        activated_at = datetime.now(UTC)
        exam.status = ExamStatus.ACTIVE
        exam.activated_by_actor_id = actor.id
        exam.activated_at = activated_at
        try:
            exam = await ExamRepository.save_exam(db, exam)
            await ExamService._add_lifecycle_event(
                db,
                exam=exam,
                event_type="exam.activated",
                actor=actor,
                occurred_at=activated_at,
            )
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ValueError(
                "The examination could not be activated because its "
                "current state conflicts with existing examination data"
            ) from exc
        return exam

    @staticmethod
    async def suspend_exam(
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
        reason: str,
    ) -> Exam:
        ExamService._require_admin(actor)
        reason = ExamService._normalize_required_text(reason)
        exam = await ExamRepository.get_exam_by_id(db, exam_id=exam_id, lock=True)
        if exam is None:
            raise ExamNotFound("Examination does not exist")
        if exam.status != ExamStatus.ACTIVE:
            raise ExamStateError("Only ACTIVE examinations can be suspended")
        suspended_at = datetime.now(UTC)
        exam.status = ExamStatus.SUSPENDED
        suspension = ExamSuspension(
            exam_id=exam.id,
            source=ExamSuspensionSource.ADMIN,
            suspended_at=suspended_at,
            suspended_by_actor_id=actor.id,
            reason=reason,
        )
        try:
            await ExamRepository.add_suspension(db, suspension)
            exam = await ExamRepository.save_exam(db, exam)
            await ExamService._add_lifecycle_event(
                db,
                exam=exam,
                event_type="exam.suspended",
                actor=actor,
                occurred_at=suspended_at,
                extra_payload={"reason": reason},
            )
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ValueError(
                "The examination could not be suspended because its "
                "current state conflicts with existing examination data"
            ) from exc
        return exam

    @staticmethod
    async def resume_exam(
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
        reason: str | None = None,
    ) -> Exam:
        ExamService._require_admin(actor)
        exam = await ExamRepository.get_exam_by_id(db, exam_id=exam_id, lock=True)
        if exam is None:
            raise ExamNotFound("Examination does not exist")
        if exam.status != ExamStatus.SUSPENDED:
            raise ExamStateError("Only SUSPENDED examinations can be resumed")
        suspension = await ExamRepository.get_open_suspension_for_exam(
            db,
            exam.id,
            lock=True,
        )
        if suspension is None:
            raise ExamStateError("Suspended examination has no open suspension")
        resumed_at = datetime.now(UTC)
        suspension.resumed_at = resumed_at
        suspension.resumed_by_actor_id = actor.id
        suspension.resume_reason = _normalize_optional_text(reason)
        exam.status = ExamStatus.ACTIVE
        try:
            await ExamRepository.save_suspension(db, suspension)
            exam = await ExamRepository.save_exam(db, exam)
            await ExamService._add_lifecycle_event(
                db,
                exam=exam,
                event_type="exam.resumed",
                actor=actor,
                occurred_at=resumed_at,
                extra_payload={"reason": suspension.resume_reason},
            )
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ValueError(
                "The examination could not be resumed because its "
                "current state conflicts with existing examination data"
            ) from exc
        return exam

    @staticmethod
    async def close_exam(
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
    ) -> Exam:
        ExamService._require_admin(actor)
        exam = await ExamRepository.get_exam_by_id(db, exam_id=exam_id, lock=True)
        if exam is None:
            raise ExamNotFound("Examination does not exist")
        if exam.status not in {ExamStatus.ACTIVE, ExamStatus.SUSPENDED}:
            raise ExamStateError("Only ACTIVE or SUSPENDED examinations can be closed")
        closed_at = datetime.now(UTC)
        if exam.status == ExamStatus.SUSPENDED:
            suspension = await ExamRepository.get_open_suspension_for_exam(
                db,
                exam.id,
                lock=True,
            )
            if suspension is not None:
                suspension.resumed_at = closed_at
                suspension.resumed_by_actor_id = actor.id
                suspension.resume_reason = "Closed while suspended"
                await ExamRepository.save_suspension(db, suspension)
        exam.status = ExamStatus.CLOSED
        exam.closed_by_actor_id = actor.id
        exam.closed_at = closed_at
        try:
            exam = await ExamRepository.save_exam(db, exam)
            await ExamService._add_lifecycle_event(
                db,
                exam=exam,
                event_type="exam.closed",
                actor=actor,
                occurred_at=closed_at,
            )
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ValueError(
                "The examination could not be closed because its "
                "current state conflicts with existing examination data"
            ) from exc
        return exam

    @staticmethod
    async def cancel_exam(
        db: AsyncSession,
        *,
        actor: LocalActor,
        exam_id: UUID,
        reason: str,
    ) -> Exam:
        ExamService._require_admin(actor)
        reason = ExamService._normalize_required_text(reason)
        exam = await ExamRepository.get_exam_by_id(db, exam_id=exam_id, lock=True)
        if exam is None:
            raise ExamNotFound("Examination does not exist")
        if exam.status not in {
            ExamStatus.SEALED,
            ExamStatus.ACTIVE,
            ExamStatus.SUSPENDED,
        }:
            raise ExamStateError(
                "Only SEALED, ACTIVE, or SUSPENDED examinations can be cancelled"
            )
        cancelled_at = datetime.now(UTC)
        if exam.status == ExamStatus.SUSPENDED:
            suspension = await ExamRepository.get_open_suspension_for_exam(
                db,
                exam.id,
                lock=True,
            )
            if suspension is not None:
                suspension.resumed_at = cancelled_at
                suspension.resumed_by_actor_id = actor.id
                suspension.resume_reason = "Cancelled while suspended"
                await ExamRepository.save_suspension(db, suspension)
        exam.status = ExamStatus.CANCELLED
        exam.cancelled_by_actor_id = actor.id
        exam.cancelled_at = cancelled_at
        exam.cancellation_reason = reason
        try:
            exam = await ExamRepository.save_exam(db, exam)
            await ExamService._add_lifecycle_event(
                db,
                exam=exam,
                event_type="exam.cancelled",
                actor=actor,
                occurred_at=cancelled_at,
                extra_payload={"reason": reason},
            )
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ValueError(
                "The examination could not be cancelled because its "
                "current state conflicts with existing examination data"
            ) from exc
        return exam
