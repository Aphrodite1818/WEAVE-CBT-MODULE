# ======================================#
# backekend.app.domains.questions.service
# =======================================#


from __future__ import annotations

from uuid import UUID
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AcademicAuthorizationError,
    AcademicScopeError,
)
from app.domains.academics.authorization import AcademicAuthorizationService
from app.domains.academics.repository import AcademicRepository
from app.domains.auth.models import LocalActor
from app.domains.media.repository import MediaRepository
from app.domains.questions.models import (
    Question,
    QuestionBank,
    QuestionOption,
    QuestionType,
)
from app.domains.questions.repository import QuestionRepository
from app.domains.questions.schemas import (
    QuestionBankCreate,
    SingleChoiceQuestionCreate,
    MultipleChoiceQuestionCreate,
    QuestionBankUpdate,
    QuestionUpdate,
    QuestionOptionCreate,
)

logger = logging.getLogger(__name__)


def _normalize_question_bank_name(
    name: str,
) -> str | None:
    name = name.strip()

    if not name:
        return None

    return name.upper()


def _normalize_question_description(
    description: str | None,
) -> str | None:
    if description is None:
        return None

    description = description.strip()

    if not description:
        return None

    return description


def _normalize_required_question_text(
    value: str,
) -> str | None:
    value = value.strip()

    if not value:
        return None

    return value


def _normalize_optional_question_text(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    value = value.strip()

    if not value:
        return None

    return value


def _normalize_and_validate_options(
    options: list[QuestionOptionCreate],
    *,
    question_type: QuestionType,
) -> list[tuple[str, bool]]:

    if len(options) < 2:
        raise ValueError("A question must have at least two options")

    normalized_options: list[tuple[str, bool]] = []

    for option in options:
        text = _normalize_required_question_text(option.text)

        if text is None:
            raise ValueError("Question options cannot be empty")

        normalized_options.append(
            (
                text,
                option.is_correct,
            )
        )

    comparable_texts = [text.casefold() for text, _ in normalized_options]

    if len(comparable_texts) != len(set(comparable_texts)):
        raise ValueError("Question options must be unique")

    correct_count = sum(1 for _, is_correct in normalized_options if is_correct)

    if question_type == QuestionType.SINGLE_CHOICE and correct_count != 1:
        raise ValueError(
            "A single-choice question must have exactly one correct option"
        )

    if question_type == QuestionType.MULTIPLE_CHOICE:
        if correct_count < 2:
            raise ValueError(
                "A multiple-choice question must have at least two correct options"
            )

        if correct_count == len(normalized_options):
            raise ValueError(
                "A multiple-choice question must have at least one incorrect option"
            )

    return normalized_options


async def _resolve_new_question_image(
    db: AsyncSession,
    *,
    actor: LocalActor,
    image_asset_id: UUID,
) -> UUID:

    asset = await MediaRepository.get_asset_by_id(
        db,
        image_asset_id,
    )

    if asset is None:
        raise ValueError("Question image does not exist")

    if asset.created_by_actor_id != actor.id:
        raise ValueError(
            "New question image must have been uploaded by the current actor"
        )

    return asset.id


def _require_can_manage_question(
    *,
    actor: LocalActor,
    question: Question,
) -> None:

    if actor.role == "admin":
        return

    if actor.role == "teacher" and question.created_by_actor_id == actor.id:
        return

    raise AcademicAuthorizationError("You are not allowed to manage this question")


class QuestionService:
    @staticmethod
    async def create_question_bank(
        db: AsyncSession,
        *,
        actor: LocalActor,
        curriculum_subject_id: UUID,
        payload: QuestionBankCreate,
    ) -> QuestionBank:
        """
        Create a shared QuestionBank for a CurriculumSubject.

        Only school administrators may create question banks.

        Teachers may author questions inside banks they are academically
        authorized to use, but may not create the banks themselves.
        """

        if not actor.is_active:
            raise AcademicAuthorizationError("Active local actor is required")

        if actor.role != "admin":
            raise AcademicAuthorizationError(
                "Only school administrators can create question banks"
            )

        curriculum_subject = await AcademicRepository.get_curriculum_subject_by_id(
            db,
            curriculum_subject_id,
        )

        if curriculum_subject is None:
            raise AcademicScopeError(
                "Curriculum subject does not exist or is no longer available"
            )

        if not curriculum_subject.is_active:
            raise AcademicScopeError("Curriculum subject is inactive")

        name = _normalize_question_bank_name(payload.name)

        if name is None:
            raise ValueError("Question bank name cannot be empty")

        description = _normalize_question_description(payload.description)

        existing_bank = await QuestionRepository.get_bank_by_scope_and_name(
            db,
            curriculum_subject_id,
            name,
        )

        if existing_bank is not None:
            raise ValueError(
                "A question bank with this name already exists "
                "for this curriculum subject"
            )

        bank = QuestionBank(
            curriculum_subject_id=curriculum_subject_id,
            name=name,
            description=description,
            created_by_actor_id=actor.id,
            is_active=True,
        )

        return await QuestionRepository.add_bank(
            db,
            bank,
        )

    @staticmethod
    async def list_actor_authorable_question_banks(
        db: AsyncSession,
        *,
        actor: LocalActor,
    ) -> list[QuestionBank]:
        """
        Return active question banks in which the actor may
        currently author questions.

        Admin:
            Banks belonging to every live active CurriculumSubject.

        Teacher:
            Banks belonging only to CurriculumSubjects for which
            the teacher has at least one current effective assignment.
        """

        curriculum_subjects = await AcademicAuthorizationService.list_actor_authorable_curriculum_subjects(
            db,
            actor=actor,
        )

        curriculum_subject_ids = [
            curriculum_subject.id for curriculum_subject in curriculum_subjects
        ]

        return await QuestionRepository.list_banks_for_curriculum_subjects(
            db,
            curriculum_subject_ids=curriculum_subject_ids,
            active_only=True,
        )

    @staticmethod
    async def create_single_choice_question(
        db: AsyncSession,
        *,
        actor: LocalActor,
        bank_id: UUID,
        payload: SingleChoiceQuestionCreate,
    ) -> Question:
        """
        Create a single-choice question inside an active QuestionBank.

        Admin:
            May author inside any live active CurriculumSubject bank.

        Teacher:
            Must currently have at least one effective assignment
            involving the bank's CurriculumSubject.
        """

        # =====================================================
        # RESOLVE QUESTION BANK
        # =====================================================

        bank = await QuestionRepository.get_bank_by_id(
            db,
            bank_id,
            lock=True,
        )

        if bank is None:
            raise ValueError("Question bank does not exist")

        if not bank.is_active:
            raise ValueError("Questions cannot be added to an inactive question bank")

        # =====================================================
        # ACADEMIC AUTHORIZATION
        # =====================================================

        await AcademicAuthorizationService.require_can_author_curriculum_subject(
            db,
            actor=actor,
            curriculum_subject_id=bank.curriculum_subject_id,
        )

        # =====================================================
        # NORMALIZE QUESTION CONTENT
        # =====================================================

        prompt = _normalize_required_question_text(payload.prompt)

        if prompt is None:
            raise ValueError("Question prompt cannot be empty")

        instruction = _normalize_optional_question_text(payload.instruction)

        # =====================================================
        # VALIDATE OPTIONAL IMAGE
        # =====================================================

        image_asset_id: UUID | None = None

        if payload.image_asset_id is not None:
            media_asset = await MediaRepository.get_asset_by_id(
                db,
                payload.image_asset_id,
            )

            if media_asset is None:
                raise ValueError("Question image does not exist")

            if media_asset.created_by_actor_id != actor.id:
                raise ValueError("Question image was not uploaded by this actor")

            image_asset_id = media_asset.id

        # =====================================================
        # VALIDATE OPTIONS
        # =====================================================

        if len(payload.options) < 2:
            raise ValueError("A single-choice question must have at least two options")

        normalized_options: list[tuple[str, bool]] = []

        for option in payload.options:
            option_text = _normalize_required_question_text(option.text)

            if option_text is None:
                raise ValueError("Question options cannot be empty")

            normalized_options.append(
                (
                    option_text,
                    option.is_correct,
                )
            )

        # =====================================================
        # PREVENT DUPLICATE OPTIONS
        # =====================================================

        comparable_option_texts = [text.casefold() for text, _ in normalized_options]

        if len(comparable_option_texts) != len(set(comparable_option_texts)):
            raise ValueError("Question options must be unique")

        # =====================================================
        # SINGLE-CHOICE CORRECT ANSWER RULE
        # =====================================================

        correct_option_count = sum(
            1 for _, is_correct in normalized_options if is_correct
        )

        if correct_option_count != 1:
            raise ValueError(
                "A single-choice question must have exactly one correct option"
            )

        # =====================================================
        # CREATE QUESTION
        # =====================================================

        question = Question(
            bank_id=bank.id,
            question_type=QuestionType.SINGLE_CHOICE,
            prompt=prompt,
            instruction=instruction,
            image_asset_id=image_asset_id,
            version=1,
            created_by_actor_id=actor.id,
            last_edited_by_actor_id=None,
            is_active=True,
        )

        question = await QuestionRepository.add_question(
            db,
            question,
        )

        # =====================================================
        # CREATE OPTIONS
        # =====================================================

        options = [
            QuestionOption(
                question_id=question.id,
                position=position,
                text=text,
                is_correct=is_correct,
            )
            for position, (text, is_correct) in enumerate(
                normalized_options,
                start=1,
            )
        ]

        await QuestionRepository.add_options(
            db,
            options,
        )

        return question

    @staticmethod
    async def create_multiple_choice_question(
        db: AsyncSession,
        *,
        actor: LocalActor,
        bank_id: UUID,
        payload: MultipleChoiceQuestionCreate,
    ) -> Question:

        bank = await QuestionRepository.get_bank_by_id(
            db,
            bank_id,
            lock=True,
        )

        if bank is None:
            raise ValueError("Question bank does not exist")

        if not bank.is_active:
            raise ValueError("Questions cannot be added to an inactive question bank")

        await AcademicAuthorizationService.require_can_author_curriculum_subject(
            db,
            actor=actor,
            curriculum_subject_id=bank.curriculum_subject_id,
        )

        prompt = _normalize_required_question_text(payload.prompt)

        if prompt is None:
            raise ValueError("Question prompt cannot be empty")

        instruction = _normalize_optional_question_text(payload.instruction)

        image_asset_id: UUID | None = None

        if payload.image_asset_id is not None:
            image_asset_id = await _resolve_new_question_image(
                db,
                actor=actor,
                image_asset_id=payload.image_asset_id,
            )

        normalized_options = _normalize_and_validate_options(
            payload.options,
            question_type=QuestionType.MULTIPLE_CHOICE,
        )

        question = Question(
            bank_id=bank.id,
            question_type=QuestionType.MULTIPLE_CHOICE,
            prompt=prompt,
            instruction=instruction,
            image_asset_id=image_asset_id,
            version=1,
            created_by_actor_id=actor.id,
            last_edited_by_actor_id=None,
            is_active=True,
        )

        question = await QuestionRepository.add_question(
            db,
            question,
        )

        options = [
            QuestionOption(
                question_id=question.id,
                position=position,
                text=text,
                is_correct=is_correct,
            )
            for position, (text, is_correct) in enumerate(
                normalized_options,
                start=1,
            )
        ]

        await QuestionRepository.add_options(
            db,
            options,
        )

        await db.commit()

        return question

    @staticmethod
    async def update_question(
        db: AsyncSession,
        *,
        actor: LocalActor,
        question_id: UUID,
        payload: QuestionUpdate,
    ) -> Question:

        question = await QuestionRepository.get_question_by_id(
            db,
            question_id,
            lock=True,
        )

        if question is None:
            raise ValueError("Question does not exist")

        if not question.is_active:
            raise ValueError("Archived questions must be reactivated before editing")

        bank = await QuestionRepository.get_bank_by_id(
            db,
            question.bank_id,
        )

        if bank is None:
            raise ValueError("Question bank does not exist")

        if not bank.is_active:
            raise ValueError("Questions inside an archived bank cannot be edited")

        await AcademicAuthorizationService.require_can_author_curriculum_subject(
            db,
            actor=actor,
            curriculum_subject_id=bank.curriculum_subject_id,
        )

        _require_can_manage_question(
            actor=actor,
            question=question,
        )

        fields = payload.model_fields_set

        changed = False

        old_image_asset_id = question.image_asset_id

        # =====================================================
        # PROMPT
        # =====================================================

        if "prompt" in fields:
            if payload.prompt is None:
                raise ValueError("Question prompt cannot be null")

            prompt = _normalize_required_question_text(payload.prompt)

            if prompt is None:
                raise ValueError("Question prompt cannot be empty")

            if prompt != question.prompt:
                question.prompt = prompt
                changed = True

        # =====================================================
        # INSTRUCTION
        # =====================================================

        if "instruction" in fields:
            instruction = _normalize_optional_question_text(payload.instruction)

            if instruction != question.instruction:
                question.instruction = instruction
                changed = True

        # =====================================================
        # IMAGE
        # =====================================================

        if "image_asset_id" in fields:
            new_image_asset_id: UUID | None = None

            if payload.image_asset_id is not None:
                new_image_asset_id = await _resolve_new_question_image(
                    db,
                    actor=actor,
                    image_asset_id=payload.image_asset_id,
                )

            if new_image_asset_id != question.image_asset_id:
                question.image_asset_id = new_image_asset_id
                changed = True

        # =====================================================
        # OPTIONS
        # =====================================================

        normalized_options: list[tuple[str, bool]] | None = None

        options_changed = False

        if "options" in fields:
            if payload.options is None:
                raise ValueError("Question options cannot be null")

            normalized_options = _normalize_and_validate_options(
                payload.options,
                question_type=question.question_type,
            )

            current_options = await QuestionRepository.list_options_for_question(
                db,
                question.id,
            )

            current_option_values = [
                (
                    option.text,
                    option.is_correct,
                )
                for option in current_options
            ]

            if normalized_options != current_option_values:
                options_changed = True
                changed = True

        # =====================================================
        # NOTHING CHANGED
        # =====================================================

        if not changed:
            await db.commit()
            return question

        # =====================================================
        # VERSIONING
        # =====================================================

        question.version += 1
        question.last_edited_by_actor_id = actor.id

        question = await QuestionRepository.save_question(
            db,
            question,
        )

        # =====================================================
        # REPLACE OPTIONS
        # =====================================================

        if options_changed and normalized_options is not None:
            await QuestionRepository.remove_options_for_question(
                db,
                question.id,
            )

            replacement_options = [
                QuestionOption(
                    question_id=question.id,
                    position=position,
                    text=text,
                    is_correct=is_correct,
                )
                for position, (text, is_correct) in enumerate(
                    normalized_options,
                    start=1,
                )
            ]

            await QuestionRepository.add_options(
                db,
                replacement_options,
            )

        await db.commit()

        # Old image is now merely eligible for cleanup.
        if (
            old_image_asset_id is not None
            and old_image_asset_id != question.image_asset_id
        ):
            try:
                if not await MediaRepository.is_referenced(
                    db,
                    old_image_asset_id,
                ):
                    await MediaService.delete_unreferenced_asset(
                        db,
                        asset_id=old_image_asset_id,
                    )

            except Exception:
                logger.exception(
                    "Failed to clean up replaced question image %s",
                    old_image_asset_id,
                )

        return question

    @staticmethod
    async def archive_question(
        db: AsyncSession,
        *,
        actor: LocalActor,
        question_id: UUID,
    ) -> Question:

        question = await QuestionRepository.get_question_by_id(
            db,
            question_id,
            lock=True,
        )

        if question is None:
            raise ValueError("Question does not exist")

        bank = await QuestionRepository.get_bank_by_id(
            db,
            question.bank_id,
        )

        if bank is None:
            raise ValueError("Question bank does not exist")

        await AcademicAuthorizationService.require_can_author_curriculum_subject(
            db,
            actor=actor,
            curriculum_subject_id=bank.curriculum_subject_id,
        )

        _require_can_manage_question(
            actor=actor,
            question=question,
        )

        if not question.is_active:
            await db.commit()
            return question

        question.is_active = False

        question = await QuestionRepository.save_question(
            db,
            question,
        )

        await db.commit()

        return question

    @staticmethod
    async def reactivate_question(
        db: AsyncSession,
        *,
        actor: LocalActor,
        question_id: UUID,
    ) -> Question:

        question = await QuestionRepository.get_question_by_id(
            db,
            question_id,
            lock=True,
        )

        if question is None:
            raise ValueError("Question does not exist")

        bank = await QuestionRepository.get_bank_by_id(
            db,
            question.bank_id,
        )

        if bank is None:
            raise ValueError("Question bank does not exist")

        if not bank.is_active:
            raise ValueError("A question cannot be reactivated inside an archived bank")

        await AcademicAuthorizationService.require_can_author_curriculum_subject(
            db,
            actor=actor,
            curriculum_subject_id=bank.curriculum_subject_id,
        )

        _require_can_manage_question(
            actor=actor,
            question=question,
        )

        if question.is_active:
            await db.commit()
            return question

        question.is_active = True

        question = await QuestionRepository.save_question(
            db,
            question,
        )

        await db.commit()

        return question

    @staticmethod
    async def delete_unused_question(
        db: AsyncSession,
        *,
        actor: LocalActor,
        question_id: UUID,
    ) -> None:

        question = await QuestionRepository.get_question_by_id(
            db,
            question_id,
            lock=True,
        )

        if question is None:
            raise ValueError("Question does not exist")

        bank = await QuestionRepository.get_bank_by_id(
            db,
            question.bank_id,
        )

        if bank is None:
            raise ValueError("Question bank does not exist")

        await AcademicAuthorizationService.require_can_author_curriculum_subject(
            db,
            actor=actor,
            curriculum_subject_id=bank.curriculum_subject_id,
        )

        _require_can_manage_question(
            actor=actor,
            question=question,
        )

        is_used = await ExamRepository.is_source_question_referenced(
            db,
            question.id,
        )

        if is_used:
            raise ValueError(
                "A question already used by an exam cannot be deleted; archive it instead"
            )

        image_asset_id = question.image_asset_id

        await QuestionRepository.delete_question(
            db,
            question,
        )

        await db.commit()

        if image_asset_id is not None:
            try:
                if not await MediaRepository.is_referenced(
                    db,
                    image_asset_id,
                ):
                    await MediaService.delete_unreferenced_asset(
                        db,
                        asset_id=image_asset_id,
                    )

            except Exception:
                logger.exception(
                    "Failed to clean up media for deleted question %s",
                    question_id,
                )
