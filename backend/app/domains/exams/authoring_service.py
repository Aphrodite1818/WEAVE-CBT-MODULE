"""Application services for examination authoring and lifecycle management"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AcademicScopeError
from app.domains.academics.authorization import AcademicAuthorizationService
from app.domains.academics.repository import AcademicRepository
from app.domains.auth.models import LocalActor
from app.domains.exams.exceptions import (
    ExamNotFound,
    ExamStateError,
)
from app.domains.exams.models import (
    Exam,
    ExamQuestionSelection,
    ExamQuestionSelectionMode,
    ExamRosterStatus,
    ExamStatus,
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
from app.domains.questions.repository import QuestionRepository


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
