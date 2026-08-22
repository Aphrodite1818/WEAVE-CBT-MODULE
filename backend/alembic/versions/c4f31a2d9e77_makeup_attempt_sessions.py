"""add makeup execution, student sessions, and attempt paper snapshots

Revision ID: c4f31a2d9e77
Revises: b91d2c4e7a10
Create Date: 2026-08-22

This is an intentional pre-launch destructive cutover for attempt paper
allocation rows. Existing development attempt answers/allocations are discarded
because the previous shape could only reference the sealed main paper and could
not safely freeze fresh makeup questions.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4f31a2d9e77"
down_revision: Union[str, Sequence[str], None] = "b91d2c4e7a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "candidate_make_up_authorizations",
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("approved_by_actor_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column(
            "approved_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_actor_id", sa.Uuid(), nullable=True),
        sa.Column("revocation_reason", sa.String(length=500), nullable=True),
        *_timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "consumed_at IS NULL OR consumed_at >= approved_at",
            name="ck_candidate_makeup_consumed_valid",
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= approved_at",
            name="ck_candidate_makeup_revoked_valid",
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_by_actor_id IS NOT NULL",
            name="ck_candidate_makeup_revocation_actor_required",
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revocation_reason IS NOT NULL",
            name="ck_candidate_makeup_revocation_reason_required",
        ),
        sa.CheckConstraint(
            "NOT (consumed_at IS NOT NULL AND revoked_at IS NOT NULL)",
            name="ck_candidate_makeup_not_consumed_and_revoked",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_actor_id"],
            ["local_actors.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["exam_candidates.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by_actor_id"],
            ["local_actors.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_candidate_make_up_authorizations_candidate_id",
        "candidate_make_up_authorizations",
        ["candidate_id"],
    )
    op.create_index(
        "ix_candidate_make_up_authorizations_approved_by_actor_id",
        "candidate_make_up_authorizations",
        ["approved_by_actor_id"],
    )
    op.create_index(
        "ix_candidate_make_up_authorizations_approved_at",
        "candidate_make_up_authorizations",
        ["approved_at"],
    )
    op.create_index(
        "ix_candidate_make_up_authorizations_revoked_by_actor_id",
        "candidate_make_up_authorizations",
        ["revoked_by_actor_id"],
    )
    op.create_index(
        "uq_candidate_makeup_one_active",
        "candidate_make_up_authorizations",
        ["candidate_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "ix_candidate_makeup_candidate_approved",
        "candidate_make_up_authorizations",
        ["candidate_id", "approved_at"],
    )

    # Pre-launch allocation cutover. Keep ExamAttempt and interruption history,
    # but rebuild candidate paper/answer rows into the source-agnostic snapshot.
    op.drop_table("attempt_answer_selections")
    op.drop_table("attempt_answers")
    op.drop_table("attempt_option_allocations")
    op.drop_table("attempt_question_allocations")

    op.create_table(
        "attempt_question_allocations",
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("exam_question_id", sa.Uuid(), nullable=True),
        sa.Column("source_question_id", sa.Uuid(), nullable=False),
        sa.Column("source_question_version", sa.Integer(), nullable=False),
        sa.Column(
            "question_type",
            sa.Enum(
                "single_choice",
                "multiple_choice",
                name="attempt_question_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=True),
        sa.Column("image_asset_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "source_question_version >= 1",
            name="ck_attempt_questions_source_version_positive",
        ),
        sa.CheckConstraint(
            "position >= 1",
            name="ck_attempt_questions_position_positive",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"], ["exam_attempts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["exam_question_id"], ["exam_questions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_question_id"], ["questions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["image_asset_id"], ["media_assets.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "attempt_id",
            "source_question_id",
            name="uq_attempt_questions_attempt_source_question",
        ),
        sa.UniqueConstraint(
            "attempt_id",
            "position",
            name="uq_attempt_questions_attempt_position",
        ),
    )
    op.create_index(
        "ix_attempt_question_allocations_attempt_id",
        "attempt_question_allocations",
        ["attempt_id"],
    )
    op.create_index(
        "ix_attempt_question_allocations_exam_question_id",
        "attempt_question_allocations",
        ["exam_question_id"],
    )
    op.create_index(
        "ix_attempt_question_allocations_source_question_id",
        "attempt_question_allocations",
        ["source_question_id"],
    )
    op.create_index(
        "ix_attempt_question_allocations_image_asset_id",
        "attempt_question_allocations",
        ["image_asset_id"],
    )
    op.create_index(
        "ix_attempt_questions_attempt_position",
        "attempt_question_allocations",
        ["attempt_id", "position"],
    )

    op.create_table(
        "attempt_option_allocations",
        sa.Column("attempt_question_id", sa.Uuid(), nullable=False),
        sa.Column("exam_question_option_id", sa.Uuid(), nullable=True),
        sa.Column("source_question_option_id", sa.Uuid(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "is_correct",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        *_timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "(exam_question_option_id IS NOT NULL "
            "AND source_question_option_id IS NULL) "
            "OR (exam_question_option_id IS NULL "
            "AND source_question_option_id IS NOT NULL)",
            name="ck_attempt_options_exactly_one_source",
        ),
        sa.CheckConstraint(
            "position >= 1",
            name="ck_attempt_options_position_positive",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_question_id"],
            ["attempt_question_allocations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["exam_question_option_id"],
            ["exam_question_options.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_question_option_id"],
            ["question_options.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "attempt_question_id",
            "position",
            name="uq_attempt_options_question_position",
        ),
    )
    op.create_index(
        "ix_attempt_option_allocations_attempt_question_id",
        "attempt_option_allocations",
        ["attempt_question_id"],
    )
    op.create_index(
        "ix_attempt_option_allocations_exam_question_option_id",
        "attempt_option_allocations",
        ["exam_question_option_id"],
    )
    op.create_index(
        "ix_attempt_option_allocations_source_question_option_id",
        "attempt_option_allocations",
        ["source_question_option_id"],
    )
    op.create_index(
        "uq_attempt_options_exam_source",
        "attempt_option_allocations",
        ["attempt_question_id", "exam_question_option_id"],
        unique=True,
        postgresql_where=sa.text("exam_question_option_id IS NOT NULL"),
    )
    op.create_index(
        "uq_attempt_options_bank_source",
        "attempt_option_allocations",
        ["attempt_question_id", "source_question_option_id"],
        unique=True,
        postgresql_where=sa.text("source_question_option_id IS NOT NULL"),
    )
    op.create_index(
        "ix_attempt_options_question_position",
        "attempt_option_allocations",
        ["attempt_question_id", "position"],
    )

    op.create_table(
        "attempt_answers",
        sa.Column("attempt_question_id", sa.Uuid(), nullable=False),
        sa.Column(
            "is_flagged",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "mutation_sequence",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "mutation_sequence >= 0",
            name="ck_attempt_answers_mutation_sequence_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_question_id"],
            ["attempt_question_allocations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_question_id"),
    )
    op.create_index(
        "ix_attempt_answers_attempt_question_id",
        "attempt_answers",
        ["attempt_question_id"],
        unique=True,
    )
    op.create_index(
        "ix_attempt_answers_updated",
        "attempt_answers",
        ["updated_at"],
    )

    op.create_table(
        "attempt_answer_selections",
        sa.Column("answer_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_option_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["answer_id"], ["attempt_answers.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["attempt_option_id"],
            ["attempt_option_allocations.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "answer_id",
            "attempt_option_id",
            name="uq_attempt_answer_selections_answer_option",
        ),
    )
    op.create_index(
        "ix_attempt_answer_selections_answer_id",
        "attempt_answer_selections",
        ["answer_id"],
    )
    op.create_index(
        "ix_attempt_answer_selections_attempt_option_id",
        "attempt_answer_selections",
        ["attempt_option_id"],
    )
    op.create_index(
        "ix_attempt_answer_selections_answer",
        "attempt_answer_selections",
        ["answer_id"],
    )

    op.create_table(
        "student_exam_sessions",
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("exam_id", sa.Uuid(), nullable=False),
        sa.Column("makeup_authorization_id", sa.Uuid(), nullable=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(length=500), nullable=True),
        *_timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_student_exam_sessions_valid_expiry",
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name="ck_student_exam_sessions_valid_revocation",
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revocation_reason IS NOT NULL",
            name="ck_student_exam_sessions_revocation_reason_required",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["exam_candidates.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["makeup_authorization_id"],
            ["candidate_make_up_authorizations.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_student_exam_sessions_student_id",
        "student_exam_sessions",
        ["student_id"],
    )
    op.create_index(
        "ix_student_exam_sessions_candidate_id",
        "student_exam_sessions",
        ["candidate_id"],
    )
    op.create_index(
        "ix_student_exam_sessions_exam_id",
        "student_exam_sessions",
        ["exam_id"],
    )
    op.create_index(
        "ix_student_exam_sessions_makeup_authorization_id",
        "student_exam_sessions",
        ["makeup_authorization_id"],
    )
    op.create_index(
        "ix_student_exam_sessions_token_hash",
        "student_exam_sessions",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_student_exam_sessions_expires_at",
        "student_exam_sessions",
        ["expires_at"],
    )
    op.create_index(
        "ix_student_exam_sessions_revoked_at",
        "student_exam_sessions",
        ["revoked_at"],
    )
    op.create_index(
        "uq_student_exam_sessions_one_active_candidate",
        "student_exam_sessions",
        ["candidate_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "ix_student_exam_sessions_student_expiry",
        "student_exam_sessions",
        ["student_id", "expires_at"],
    )


def downgrade() -> None:
    op.drop_table("student_exam_sessions")

    op.drop_table("attempt_answer_selections")
    op.drop_table("attempt_answers")
    op.drop_table("attempt_option_allocations")
    op.drop_table("attempt_question_allocations")

    # Restore the previous main-paper-only allocation shape. Data is not
    # restored because the upgrade is intentionally destructive pre-launch.
    op.create_table(
        "attempt_question_allocations",
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("exam_question_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "position >= 1", name="ck_attempt_questions_position_positive"
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"], ["exam_attempts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["exam_question_id"], ["exam_questions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "attempt_id",
            "exam_question_id",
            name="uq_attempt_questions_attempt_exam_question",
        ),
        sa.UniqueConstraint(
            "attempt_id",
            "position",
            name="uq_attempt_questions_attempt_position",
        ),
    )
    op.create_index(
        "ix_attempt_question_allocations_attempt_id",
        "attempt_question_allocations",
        ["attempt_id"],
    )
    op.create_index(
        "ix_attempt_question_allocations_exam_question_id",
        "attempt_question_allocations",
        ["exam_question_id"],
    )
    op.create_index(
        "ix_attempt_questions_attempt_position",
        "attempt_question_allocations",
        ["attempt_id", "position"],
    )

    op.create_table(
        "attempt_option_allocations",
        sa.Column("attempt_question_id", sa.Uuid(), nullable=False),
        sa.Column("exam_question_option_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "position >= 1", name="ck_attempt_options_position_positive"
        ),
        sa.ForeignKeyConstraint(
            ["attempt_question_id"],
            ["attempt_question_allocations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["exam_question_option_id"],
            ["exam_question_options.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "attempt_question_id",
            "exam_question_option_id",
            name="uq_attempt_options_question_option",
        ),
        sa.UniqueConstraint(
            "attempt_question_id",
            "position",
            name="uq_attempt_options_question_position",
        ),
    )
    op.create_index(
        "ix_attempt_option_allocations_attempt_question_id",
        "attempt_option_allocations",
        ["attempt_question_id"],
    )
    op.create_index(
        "ix_attempt_option_allocations_exam_question_option_id",
        "attempt_option_allocations",
        ["exam_question_option_id"],
    )
    op.create_index(
        "ix_attempt_options_question_position",
        "attempt_option_allocations",
        ["attempt_question_id", "position"],
    )

    op.create_table(
        "attempt_answers",
        sa.Column("attempt_question_id", sa.Uuid(), nullable=False),
        sa.Column(
            "is_flagged",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "mutation_sequence",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "mutation_sequence >= 0",
            name="ck_attempt_answers_mutation_sequence_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_question_id"],
            ["attempt_question_allocations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_question_id"),
    )
    op.create_index(
        "ix_attempt_answers_attempt_question_id",
        "attempt_answers",
        ["attempt_question_id"],
        unique=True,
    )
    op.create_index(
        "ix_attempt_answers_updated",
        "attempt_answers",
        ["updated_at"],
    )

    op.create_table(
        "attempt_answer_selections",
        sa.Column("answer_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_option_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["answer_id"], ["attempt_answers.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["attempt_option_id"],
            ["attempt_option_allocations.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "answer_id",
            "attempt_option_id",
            name="uq_attempt_answer_selections_answer_option",
        ),
    )
    op.create_index(
        "ix_attempt_answer_selections_answer_id",
        "attempt_answer_selections",
        ["answer_id"],
    )
    op.create_index(
        "ix_attempt_answer_selections_attempt_option_id",
        "attempt_answer_selections",
        ["attempt_option_id"],
    )
    op.create_index(
        "ix_attempt_answer_selections_answer",
        "attempt_answer_selections",
        ["answer_id"],
    )

    op.drop_table("candidate_make_up_authorizations")
