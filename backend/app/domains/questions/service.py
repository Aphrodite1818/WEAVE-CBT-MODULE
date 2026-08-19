"""Application services for question banks and source questions."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AcademicAuthorizationError, AcademicScopeError
from app.domains.academics.authorization import AcademicAuthorizationService
from app.domains.academics.repository import AcademicRepository
from app.domains.auth.models import LocalActor
from app.domains.exams.repository import ExamRepository
from app.domains.media.repository import MediaRepository
from app.domains.media.service import MediaService
from app.domains.questions.models import (
    Question,
    QuestionBank,
    QuestionOption,
    QuestionType,
)
from app.domains.questions.repository import QuestionRepository
from app.domains.questions.schemas import (
    MultipleChoiceQuestionCreate,
    QuestionBankCreate,
    QuestionBankUpdate,
    QuestionOptionCreate,
    QuestionUpdate,
    SingleChoiceQuestionCreate,
)

logger = logging.getLogger(__name__)


def _normalize_question_bank_name(name: str) -> str | None:
    value = name.strip()
    return value.upper() if value else None


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _normalize_required_text(value: str) -> str | None:
    value = value.strip()
    return value or None


def _require_admin(actor: LocalActor) -> None:
    if not actor.is_active:
        raise AcademicAuthorizationError("Active local actor is required")
    if actor.role != "admin":
        raise AcademicAuthorizationError(
            "Only school administrators can manage question banks"
        )


def _require_can_manage_question(*, actor: LocalActor, question: Question) -> None:
    if not actor.is_active:
        raise AcademicAuthorizationError("Active local actor is required")
    if actor.role == "admin":
        return
    if actor.role == "teacher" and question.created_by_actor_id == actor.id:
        return
    raise AcademicAuthorizationError("You are not allowed to manage this question")


def _normalize_and_validate_options(
    options: list[QuestionOptionCreate],
    *,
    question_type: QuestionType,
) -> list[tuple[str, bool]]:
    if len(options) < 2:
        raise ValueError("A question must have at least two options")

    normalized: list[tuple[str, bool]] = []
    for option in options:
        text = _normalize_required_text(option.text)
        if text is None:
            raise ValueError("Question options cannot be empty")
        normalized.append((text, option.is_correct))

    comparable = [text.casefold() for text, _ in normalized]
    if len(comparable) != len(set(comparable)):
        raise ValueError("Question options must be unique")

    correct_count = sum(1 for _, is_correct in normalized if is_correct)

    if question_type == QuestionType.SINGLE_CHOICE and correct_count != 1:
        raise ValueError(
            "A single-choice question must have exactly one correct option"
        )

    if question_type == QuestionType.MULTIPLE_CHOICE:
        if correct_count < 2:
            raise ValueError(
                "A multiple-choice question must have at least two correct options"
            )
        if correct_count == len(normalized):
            raise ValueError(
                "A multiple-choice question must have at least one incorrect option"
            )

    return normalized


async def _resolve_new_question_image(
    db: AsyncSession,
    *,
    actor: LocalActor,
    image_asset_id: UUID,
) -> UUID:
    asset = await MediaRepository.get_asset_by_id(db, image_asset_id)
    if asset is None:
        raise ValueError("Question image does not exist")
    if asset.created_by_actor_id != actor.id:
        raise ValueError(
            "New question image must have been uploaded by the current actor"
        )
    return asset.id


class QuestionService:
    @staticmethod
    async def create_question_bank(
        db: AsyncSession,
        *,
        actor: LocalActor,
        curriculum_subject_id: UUID,
        payload: QuestionBankCreate,
    ) -> QuestionBank:
        _require_admin(actor)

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

        existing = await QuestionRepository.get_bank_by_scope_and_name(
            db,
            curriculum_subject_id,
            name,
        )
        if existing is not None:
            raise ValueError(
                "A question bank with this name already exists for this curriculum subject"
            )

        bank = QuestionBank(
            curriculum_subject_id=curriculum_subject_id,
            name=name,
            description=_normalize_optional_text(payload.description),
            created_by_actor_id=actor.id,
            is_active=True,
        )

        try:
            bank = await QuestionRepository.add_bank(db, bank)
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ValueError(
                "A question bank with this name already exists for this curriculum subject"
            ) from exc

        return bank

    @staticmethod
    async def list_actor_authorable_question_banks(
        db: AsyncSession,
        *,
        actor: LocalActor,
    ) -> list[QuestionBank]:
        subjects = (
            await AcademicAuthorizationService.list_actor_authorable_curriculum_subjects(
                db,
                actor=actor,
            )
        )
        return await QuestionRepository.list_banks_for_curriculum_subjects(
            db,
            curriculum_subject_ids=[subject.id for subject in subjects],
            active_only=True,
        )

    @staticmethod
    async def update_question_bank(
        db: AsyncSession,
        *,
        actor: LocalActor,
        bank_id: UUID,
        payload: QuestionBankUpdate,
    ) -> QuestionBank:
        _require_admin(actor)

        bank = await QuestionRepository.get_bank_by_id(db, bank_id, lock=True)
        if bank is None:
            raise ValueError("Question bank does not exist")

        fields = payload.model_fields_set
        if not fields:
            await db.commit()
            return bank

        next_subject_id = bank.curriculum_subject_id
        next_name = bank.name

        if "curriculum_subject_id" in fields:
            if payload.curriculum_subject_id is None:
                raise ValueError("Curriculum subject cannot be null")
            if payload.curriculum_subject_id != bank.curriculum_subject_id:
                question_count = await QuestionRepository.count_questions_for_bank(
                    db,
                    bank.id,
                )
                if question_count > 0:
                    raise ValueError(
                        "A question bank's curriculum subject can only change while the bank is empty"
                    )
                subject = await AcademicRepository.get_curriculum_subject_by_id(
                    db,
                    payload.curriculum_subject_id,
                )
                if subject is None:
                    raise AcademicScopeError(
                        "Curriculum subject does not exist or is no longer available"
                    )
                if not subject.is_active:
                    raise AcademicScopeError("Curriculum subject is inactive")
                next_subject_id = subject.id

        if "name" in fields:
            if payload.name is None:
                raise ValueError("Question bank name cannot be null")
            normalized_name = _normalize_question_bank_name(payload.name)
            if normalized_name is None:
                raise ValueError("Question bank name cannot be empty")
            next_name = normalized_name

        duplicate = await QuestionRepository.get_bank_by_scope_and_name(
            db,
            next_subject_id,
            next_name,
        )
        if duplicate is not None and duplicate.id != bank.id:
            raise ValueError(
                "A question bank with this name already exists for this curriculum subject"
            )

        bank.curriculum_subject_id = next_subject_id
        bank.name = next_name

        if "description" in fields:
            bank.description = _normalize_optional_text(payload.description)

        try:
            bank = await QuestionRepository.save_bank(db, bank)
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ValueError(
                "A question bank with this name already exists for this curriculum subject"
            ) from exc

        return bank

    @staticmethod
    async def archive_question_bank(
        db: AsyncSession,
        *,
        actor: LocalActor,
        bank_id: UUID,
    ) -> QuestionBank:
        _require_admin(actor)
        bank = await QuestionRepository.get_bank_by_id(db, bank_id, lock=True)
        if bank is None:
            raise ValueError("Question bank does not exist")
        if bank.is_active:
            bank.is_active = False
            bank = await QuestionRepository.save_bank(db, bank)
        await db.commit()
        return bank

    @staticmethod
    async def reactivate_question_bank(
        db: AsyncSession,
        *,
        actor: LocalActor,
        bank_id: UUID,
    ) -> QuestionBank:
        _require_admin(actor)
        bank = await QuestionRepository.get_bank_by_id(db, bank_id, lock=True)
        if bank is None:
            raise ValueError("Question bank does not exist")

        subject = await AcademicRepository.get_curriculum_subject_by_id(
            db,
            bank.curriculum_subject_id,
        )
        if subject is None or not subject.is_active:
            raise AcademicScopeError(
                "Question bank cannot be reactivated because its curriculum subject is unavailable"
            )

        if not bank.is_active:
            bank.is_active = True
            bank = await QuestionRepository.save_bank(db, bank)
        await db.commit()
        return bank

    @staticmethod
    async def delete_empty_question_bank(
        db: AsyncSession,
        *,
        actor: LocalActor,
        bank_id: UUID,
    ) -> None:
        _require_admin(actor)
        bank = await QuestionRepository.get_bank_by_id(db, bank_id, lock=True)
        if bank is None:
            raise ValueError("Question bank does not exist")

        if await QuestionRepository.count_questions_for_bank(db, bank.id) > 0:
            raise ValueError(
                "A question bank containing questions cannot be deleted; archive it instead"
            )

        await QuestionRepository.delete_bank(db, bank)
        await db.commit()

    @staticmethod
    async def create_single_choice_question(
        db: AsyncSession,
        *,
        actor: LocalActor,
        bank_id: UUID,
        payload: SingleChoiceQuestionCreate,
    ) -> Question:
        return await QuestionService._create_choice_question(
            db,
            actor=actor,
            bank_id=bank_id,
            prompt=payload.prompt,
            instruction=payload.instruction,
            image_asset_id=payload.image_asset_id,
            options=payload.options,
            question_type=QuestionType.SINGLE_CHOICE,
        )

    @staticmethod
    async def create_multiple_choice_question(
        db: AsyncSession,
        *,
        actor: LocalActor,
        bank_id: UUID,
        payload: MultipleChoiceQuestionCreate,
    ) -> Question:
        return await QuestionService._create_choice_question(
            db,
            actor=actor,
            bank_id=bank_id,
            prompt=payload.prompt,
            instruction=payload.instruction,
            image_asset_id=payload.image_asset_id,
            options=payload.options,
            question_type=QuestionType.MULTIPLE_CHOICE,
        )

    @staticmethod
    async def _create_choice_question(
        db: AsyncSession,
        *,
        actor: LocalActor,
        bank_id: UUID,
        prompt: str,
        instruction: str | None,
        image_asset_id: UUID | None,
        options: list[QuestionOptionCreate],
        question_type: QuestionType,
    ) -> Question:
        bank = await QuestionRepository.get_bank_by_id(db, bank_id, lock=True)
        if bank is None:
            raise ValueError("Question bank does not exist")
        if not bank.is_active:
            raise ValueError("Questions cannot be added to an inactive question bank")

        await AcademicAuthorizationService.require_can_author_curriculum_subject(
            db,
            actor=actor,
            curriculum_subject_id=bank.curriculum_subject_id,
        )

        normalized_prompt = _normalize_required_text(prompt)
        if normalized_prompt is None:
            raise ValueError("Question prompt cannot be empty")

        resolved_image_id: UUID | None = None
        if image_asset_id is not None:
            resolved_image_id = await _resolve_new_question_image(
                db,
                actor=actor,
                image_asset_id=image_asset_id,
            )

        normalized_options = _normalize_and_validate_options(
            options,
            question_type=question_type,
        )

        question = Question(
            bank_id=bank.id,
            question_type=question_type,
            prompt=normalized_prompt,
            instruction=_normalize_optional_text(instruction),
            image_asset_id=resolved_image_id,
            version=1,
            created_by_actor_id=actor.id,
            last_edited_by_actor_id=None,
            is_active=True,
        )
        question = await QuestionRepository.add_question(db, question)

        await QuestionRepository.add_options(
            db,
            [
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
            ],
        )

        await db.commit()
        return question

    @staticmethod
    async def list_actor_questions_for_bank(
        db: AsyncSession,
        *,
        actor: LocalActor,
        bank_id: UUID,
        active_only: bool = True,
    ) -> list[Question]:
        bank = await QuestionRepository.get_bank_by_id(db, bank_id)
        if bank is None:
            raise ValueError("Question bank does not exist")

        await AcademicAuthorizationService.require_can_author_curriculum_subject(
            db,
            actor=actor,
            curriculum_subject_id=bank.curriculum_subject_id,
        )

        return await QuestionRepository.list_questions_for_bank(
            db,
            bank.id,
            active_only=active_only,
        )

    @staticmethod
    async def get_actor_question(
        db: AsyncSession,
        *,
        actor: LocalActor,
        question_id: UUID,
    ) -> Question:
        question = await QuestionRepository.get_question_by_id(db, question_id)
        if question is None:
            raise ValueError("Question does not exist")

        bank = await QuestionRepository.get_bank_by_id(db, question.bank_id)
        if bank is None:
            raise ValueError("Question bank does not exist")

        await AcademicAuthorizationService.require_can_author_curriculum_subject(
            db,
            actor=actor,
            curriculum_subject_id=bank.curriculum_subject_id,
        )
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

        bank = await QuestionRepository.get_bank_by_id(db, question.bank_id)
        if bank is None:
            raise ValueError("Question bank does not exist")
        if not bank.is_active:
            raise ValueError("Questions inside an archived bank cannot be edited")

        await AcademicAuthorizationService.require_can_author_curriculum_subject(
            db,
            actor=actor,
            curriculum_subject_id=bank.curriculum_subject_id,
        )
        _require_can_manage_question(actor=actor, question=question)

        fields = payload.model_fields_set
        changed = False
        old_image_asset_id = question.image_asset_id

        if "prompt" in fields:
            if payload.prompt is None:
                raise ValueError("Question prompt cannot be null")
            prompt = _normalize_required_text(payload.prompt)
            if prompt is None:
                raise ValueError("Question prompt cannot be empty")
            if prompt != question.prompt:
                question.prompt = prompt
                changed = True

        if "instruction" in fields:
            instruction = _normalize_optional_text(payload.instruction)
            if instruction != question.instruction:
                question.instruction = instruction
                changed = True

        if "image_asset_id" in fields:
            next_image_id: UUID | None = None
            if payload.image_asset_id is not None:
                next_image_id = await _resolve_new_question_image(
                    db,
                    actor=actor,
                    image_asset_id=payload.image_asset_id,
                )
            if next_image_id != question.image_asset_id:
                question.image_asset_id = next_image_id
                changed = True

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
            current_values = [
                (option.text, option.is_correct) for option in current_options
            ]
            if normalized_options != current_values:
                options_changed = True
                changed = True

        if not changed:
            await db.commit()
            return question

        question.version += 1
        question.last_edited_by_actor_id = actor.id
        question = await QuestionRepository.save_question(db, question)

        if options_changed and normalized_options is not None:
            await QuestionRepository.remove_options_for_question(db, question.id)
            await QuestionRepository.add_options(
                db,
                [
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
                ],
            )

        await db.commit()

        if old_image_asset_id is not None and old_image_asset_id != question.image_asset_id:
            try:
                await MediaService.delete_unreferenced_asset(
                    db,
                    asset_id=old_image_asset_id,
                )
            except ValueError:
                pass
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

        bank = await QuestionRepository.get_bank_by_id(db, question.bank_id)
        if bank is None:
            raise ValueError("Question bank does not exist")

        await AcademicAuthorizationService.require_can_author_curriculum_subject(
            db,
            actor=actor,
            curriculum_subject_id=bank.curriculum_subject_id,
        )
        _require_can_manage_question(actor=actor, question=question)

        if question.is_active:
            question.is_active = False
            question = await QuestionRepository.save_question(db, question)
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

        bank = await QuestionRepository.get_bank_by_id(db, question.bank_id)
        if bank is None:
            raise ValueError("Question bank does not exist")
        if not bank.is_active:
            raise ValueError("A question cannot be reactivated inside an archived bank")

        await AcademicAuthorizationService.require_can_author_curriculum_subject(
            db,
            actor=actor,
            curriculum_subject_id=bank.curriculum_subject_id,
        )
        _require_can_manage_question(actor=actor, question=question)

        if not question.is_active:
            question.is_active = True
            question = await QuestionRepository.save_question(db, question)
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

        bank = await QuestionRepository.get_bank_by_id(db, question.bank_id)
        if bank is None:
            raise ValueError("Question bank does not exist")

        await AcademicAuthorizationService.require_can_author_curriculum_subject(
            db,
            actor=actor,
            curriculum_subject_id=bank.curriculum_subject_id,
        )
        _require_can_manage_question(actor=actor, question=question)

        if await ExamRepository.is_source_question_referenced(db, question.id):
            raise ValueError(
                "A question already used by an exam cannot be deleted; archive it instead"
            )

        image_asset_id = question.image_asset_id
        await QuestionRepository.delete_question(db, question)
        await db.commit()

        if image_asset_id is not None:
            try:
                await MediaService.delete_unreferenced_asset(
                    db,
                    asset_id=image_asset_id,
                )
            except ValueError:
                pass
            except Exception:
                logger.exception(
                    "Failed to clean up media for deleted question %s",
                    question_id,
                )
