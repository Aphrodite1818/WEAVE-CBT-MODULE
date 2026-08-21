"""align exam authoring and scoring schema

Revision ID: 7dfe6fd9894b
Revises: b91d2c4e7a10
Create Date: 2026-08-21 15:28:56.607864

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7dfe6fd9894b"
down_revision: str | Sequence[str] | None = "b91d2c4e7a10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("exams", sa.Column("question_bank_id", sa.Uuid(), nullable=True))
    op.add_column(
        "exams",
        sa.Column(
            "question_selection_mode",
            sa.Enum(
                "random",
                "manual",
                name="exam_question_selection_mode",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="random",
            nullable=False,
        ),
    )
    op.add_column("exams", sa.Column("question_count", sa.Integer(), nullable=True))
    op.add_column(
        "exams", sa.Column("scheduled_start_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "exams",
        sa.Column("latest_normal_start_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "exams",
        sa.Column(
            "roster_status",
            sa.Enum(
                "not_prepared",
                "pending",
                "building",
                "ready",
                "stale",
                "failed",
                name="exam_roster_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="not_prepared",
            nullable=False,
        ),
    )
    op.add_column(
        "exams",
        sa.Column("roster_version", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "exams",
        sa.Column(
            "roster_candidate_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "exams", sa.Column("roster_prepared_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("exams", sa.Column("roster_error", sa.Text(), nullable=True))
    op.add_column(
        "exams",
        sa.Column("revision_number", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )
    op.add_column("exams", sa.Column("revision_of_exam_id", sa.Uuid(), nullable=True))
    op.add_column("exams", sa.Column("sealed_by_actor_id", sa.Uuid(), nullable=True))
    op.add_column("exams", sa.Column("activated_by_actor_id", sa.Uuid(), nullable=True))
    op.add_column("exams", sa.Column("closed_by_actor_id", sa.Uuid(), nullable=True))
    op.add_column("exams", sa.Column("cancelled_by_actor_id", sa.Uuid(), nullable=True))
    op.add_column("exams", sa.Column("cancellation_reason", sa.Text(), nullable=True))
    op.add_column(
        "exams",
        sa.Column("component_maximum_score", sa.Numeric(8, 2), nullable=True),
    )

    op.execute("UPDATE exams SET scheduled_start_at = opens_at")
    op.execute(
        """
        UPDATE exams
        SET component_maximum_score = COALESCE(
            source_assessment_component_maximum_score,
            maximum_score
        )
        """
    )
    op.execute(
        """
        UPDATE exams
        SET question_count = COALESCE(
            NULLIF((
                SELECT COUNT(eq.id)::integer
                FROM exam_questions eq
                WHERE eq.exam_id = exams.id
            ), 0),
            maximum_score::integer
        )
        """
    )
    op.execute(
        """
        UPDATE exams
        SET question_bank_id = inferred.bank_id
        FROM (
            SELECT DISTINCT ON (eq.exam_id)
                eq.exam_id,
                q.bank_id
            FROM exam_questions eq
            JOIN questions q ON q.id = eq.source_question_id
            ORDER BY eq.exam_id, eq.position
        ) AS inferred
        WHERE inferred.exam_id = exams.id
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM exams
                WHERE question_bank_id IS NULL
            ) THEN
                RAISE EXCEPTION
                    'Cannot infer question_bank_id for one or more existing exams';
            END IF;
        END
        $$;
        """
    )

    op.create_foreign_key(
        op.f("fk_exams_question_bank_id_question_banks"),
        "exams",
        "question_banks",
        ["question_bank_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        op.f("fk_exams_revision_of_exam_id_exams"),
        "exams",
        "exams",
        ["revision_of_exam_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        op.f("fk_exams_sealed_by_actor_id_local_actors"),
        "exams",
        "local_actors",
        ["sealed_by_actor_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        op.f("fk_exams_activated_by_actor_id_local_actors"),
        "exams",
        "local_actors",
        ["activated_by_actor_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        op.f("fk_exams_closed_by_actor_id_local_actors"),
        "exams",
        "local_actors",
        ["closed_by_actor_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        op.f("fk_exams_cancelled_by_actor_id_local_actors"),
        "exams",
        "local_actors",
        ["cancelled_by_actor_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.alter_column("exams", "question_bank_id", nullable=False)
    op.alter_column("exams", "question_count", nullable=False)
    op.create_index(op.f("ix_exams_question_bank_id"), "exams", ["question_bank_id"])
    op.create_index(
        op.f("ix_exams_question_selection_mode"),
        "exams",
        ["question_selection_mode"],
    )
    op.create_index(
        op.f("ix_exams_scheduled_start_at"), "exams", ["scheduled_start_at"]
    )
    op.create_index(
        op.f("ix_exams_latest_normal_start_at"),
        "exams",
        ["latest_normal_start_at"],
    )
    op.create_index(op.f("ix_exams_roster_status"), "exams", ["roster_status"])
    op.create_index(
        op.f("ix_exams_revision_of_exam_id"),
        "exams",
        ["revision_of_exam_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_exams_sealed_by_actor_id"), "exams", ["sealed_by_actor_id"]
    )
    op.create_index(
        op.f("ix_exams_activated_by_actor_id"), "exams", ["activated_by_actor_id"]
    )
    op.create_index(
        op.f("ix_exams_closed_by_actor_id"), "exams", ["closed_by_actor_id"]
    )
    op.create_index(
        op.f("ix_exams_cancelled_by_actor_id"), "exams", ["cancelled_by_actor_id"]
    )

    op.drop_index(
        "uq_exams_term_curriculum_subject_title_lower",
        table_name="exams",
    )
    op.create_index(
        "uq_exams_scope_title_revision",
        "exams",
        [
            "term_id",
            "curriculum_subject_id",
            "assessment_component_id",
            sa.text("lower(title)"),
            "revision_number",
        ],
        unique=True,
    )
    op.create_index(
        "ix_exams_roster_status_exam_status",
        "exams",
        ["roster_status", "status"],
    )
    op.create_index(
        "ix_exams_scheduled_status",
        "exams",
        ["scheduled_start_at", "status"],
    )

    op.drop_constraint("exam_status", "exams", type_="check")
    op.create_check_constraint(
        "exam_status",
        "exams",
        "status IN ('draft', 'submitted', 'sealed', 'active', 'suspended', "
        "'closed', 'cancelled')",
    )
    op.drop_constraint("ck_exams_maximum_score_positive", "exams", type_="check")
    op.drop_constraint(
        "ck_exams_source_component_maximum_positive", "exams", type_="check"
    )
    op.drop_constraint("ck_exams_valid_schedule", "exams", type_="check")
    op.create_check_constraint(
        "ck_exams_question_count_positive",
        "exams",
        "question_count > 0",
    )
    op.create_check_constraint(
        "ck_exams_revision_positive",
        "exams",
        "revision_number >= 1",
    )
    op.create_check_constraint(
        "ck_exams_revision_lineage_shape",
        "exams",
        "(revision_of_exam_id IS NULL AND revision_number = 1) OR "
        "(revision_of_exam_id IS NOT NULL AND revision_number > 1)",
    )
    op.create_check_constraint(
        "ck_exams_roster_version_nonnegative",
        "exams",
        "roster_version >= 0",
    )
    op.create_check_constraint(
        "ck_exams_roster_candidate_count_nonnegative",
        "exams",
        "roster_candidate_count >= 0",
    )
    op.create_check_constraint(
        "ck_exams_roster_error_length",
        "exams",
        "roster_error IS NULL OR char_length(roster_error) <= 1024",
    )
    op.create_check_constraint(
        "ck_exams_valid_normal_start_window",
        "exams",
        "latest_normal_start_at IS NULL OR scheduled_start_at IS NULL OR "
        "latest_normal_start_at >= scheduled_start_at",
    )
    op.create_check_constraint(
        "ck_exams_component_maximum_positive",
        "exams",
        "component_maximum_score IS NULL OR component_maximum_score > 0",
    )
    op.create_check_constraint(
        "ck_exams_sealing_actor_required",
        "exams",
        "sealed_at IS NULL OR sealed_by_actor_id IS NOT NULL",
    )
    op.create_check_constraint(
        "ck_exams_activation_actor_required",
        "exams",
        "activated_at IS NULL OR activated_by_actor_id IS NOT NULL",
    )
    op.create_check_constraint(
        "ck_exams_cancellation_actor_required",
        "exams",
        "cancelled_at IS NULL OR cancelled_by_actor_id IS NOT NULL",
    )
    op.create_check_constraint(
        "ck_exams_cancellation_reason_required",
        "exams",
        "cancelled_at IS NULL OR cancellation_reason IS NOT NULL",
    )

    op.drop_column("exams", "maximum_score")
    op.drop_column("exams", "opens_at")
    op.drop_column("exams", "closes_at")
    op.drop_column("exams", "source_assessment_scheme_id")
    op.drop_column("exams", "source_assessment_component_id")
    op.drop_column("exams", "source_assessment_component_name")
    op.drop_column("exams", "source_assessment_component_code")
    op.drop_column("exams", "source_assessment_component_maximum_score")

    op.create_table(
        "exam_question_selections",
        sa.Column("exam_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "position >= 1",
            name="ck_exam_question_selections_position_positive",
        ),
        sa.ForeignKeyConstraint(
            ["exam_id"],
            ["exams.id"],
            name=op.f("fk_exam_question_selections_exam_id_exams"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            name=op.f("fk_exam_question_selections_question_id_questions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exam_question_selections")),
        sa.UniqueConstraint(
            "exam_id",
            "question_id",
            name="uq_exam_question_selections_exam_question",
        ),
        sa.UniqueConstraint(
            "exam_id",
            "position",
            name="uq_exam_question_selections_exam_position",
        ),
    )
    op.create_index(
        op.f("ix_exam_question_selections_exam_id"),
        "exam_question_selections",
        ["exam_id"],
    )
    op.create_index(
        "ix_exam_question_selections_exam_position",
        "exam_question_selections",
        ["exam_id", "position"],
    )
    op.create_index(
        op.f("ix_exam_question_selections_question_id"),
        "exam_question_selections",
        ["question_id"],
    )

    op.drop_constraint(
        "ck_exam_questions_points_positive",
        "exam_questions",
        type_="check",
    )
    op.drop_column("exam_questions", "points")

    op.create_table(
        "exam_suspensions",
        sa.Column("exam_id", sa.Uuid(), nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                "admin",
                "system",
                name="exam_suspension_source",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("suspended_by_actor_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("resumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resumed_by_actor_id", sa.Uuid(), nullable=True),
        sa.Column("resume_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "resumed_at IS NULL OR resumed_at >= suspended_at",
            name="ck_exam_suspensions_resume_after_suspend",
        ),
        sa.CheckConstraint(
            "resumed_at IS NULL OR resumed_by_actor_id IS NOT NULL",
            name="ck_exam_suspensions_resume_actor_required",
        ),
        sa.CheckConstraint(
            "(source != 'admin') OR (suspended_by_actor_id IS NOT NULL)",
            name="ck_exam_suspensions_admin_actor_required",
        ),
        sa.ForeignKeyConstraint(
            ["exam_id"],
            ["exams.id"],
            name=op.f("fk_exam_suspensions_exam_id_exams"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["suspended_by_actor_id"],
            ["local_actors.id"],
            name=op.f("fk_exam_suspensions_suspended_by_actor_id_local_actors"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["resumed_by_actor_id"],
            ["local_actors.id"],
            name=op.f("fk_exam_suspensions_resumed_by_actor_id_local_actors"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exam_suspensions")),
    )
    op.create_index(op.f("ix_exam_suspensions_exam_id"), "exam_suspensions", ["exam_id"])
    op.create_index(
        "ix_exam_suspensions_exam_suspended_at",
        "exam_suspensions",
        ["exam_id", "suspended_at"],
    )
    op.create_index(
        op.f("ix_exam_suspensions_suspended_by_actor_id"),
        "exam_suspensions",
        ["suspended_by_actor_id"],
    )
    op.create_index(
        op.f("ix_exam_suspensions_resumed_by_actor_id"),
        "exam_suspensions",
        ["resumed_by_actor_id"],
    )

    op.add_column("exam_results", sa.Column("raw_score", sa.Integer(), nullable=True))
    op.add_column("exam_results", sa.Column("raw_max_score", sa.Integer(), nullable=True))
    op.add_column(
        "exam_results", sa.Column("percentage", sa.Numeric(5, 2), nullable=True)
    )
    op.add_column(
        "exam_results", sa.Column("component_score", sa.Numeric(8, 2), nullable=True)
    )
    op.add_column(
        "exam_results",
        sa.Column("component_maximum_score", sa.Numeric(8, 2), nullable=True),
    )
    op.execute(
        """
        UPDATE exam_results
        SET
            raw_score = score::integer,
            raw_max_score = maximum_score::integer,
            percentage = ROUND((score / maximum_score) * 100, 2),
            component_score = score,
            component_maximum_score = maximum_score
        """
    )
    op.alter_column("exam_results", "raw_score", nullable=False)
    op.alter_column("exam_results", "raw_max_score", nullable=False)
    op.alter_column("exam_results", "percentage", nullable=False)
    op.alter_column("exam_results", "component_score", nullable=False)
    op.alter_column("exam_results", "component_maximum_score", nullable=False)
    op.drop_constraint("ck_exam_results_score_nonnegative", "exam_results", type_="check")
    op.drop_constraint(
        "ck_exam_results_maximum_score_positive", "exam_results", type_="check"
    )
    op.drop_constraint(
        "ck_exam_results_score_within_maximum", "exam_results", type_="check"
    )
    op.create_check_constraint(
        "ck_exam_results_raw_score_nonnegative",
        "exam_results",
        "raw_score >= 0",
    )
    op.create_check_constraint(
        "ck_exam_results_raw_max_positive",
        "exam_results",
        "raw_max_score > 0",
    )
    op.create_check_constraint(
        "ck_exam_results_raw_score_within_max",
        "exam_results",
        "raw_score <= raw_max_score",
    )
    op.create_check_constraint(
        "ck_exam_results_percentage_nonnegative",
        "exam_results",
        "percentage >= 0",
    )
    op.create_check_constraint(
        "ck_exam_results_percentage_within_100",
        "exam_results",
        "percentage <= 100",
    )
    op.create_check_constraint(
        "ck_exam_results_component_score_nonnegative",
        "exam_results",
        "component_score >= 0",
    )
    op.create_check_constraint(
        "ck_exam_results_component_max_positive",
        "exam_results",
        "component_maximum_score > 0",
    )
    op.create_check_constraint(
        "ck_exam_results_component_score_within_max",
        "exam_results",
        "component_score <= component_maximum_score",
    )
    op.create_check_constraint(
        "ck_exam_results_synced_at_matches_status",
        "exam_results",
        "synced_at IS NULL OR sync_status = 'synced'",
    )
    op.create_index(
        "ix_exam_results_sync_status_attempt",
        "exam_results",
        ["sync_status", "last_sync_attempt_at"],
    )
    op.drop_column("exam_results", "score")
    op.drop_column("exam_results", "maximum_score")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "exam_results",
        sa.Column("maximum_score", sa.Numeric(8, 2), nullable=True),
    )
    op.add_column(
        "exam_results",
        sa.Column("score", sa.Numeric(8, 2), nullable=True),
    )
    op.execute(
        """
        UPDATE exam_results
        SET
            score = component_score,
            maximum_score = component_maximum_score
        """
    )
    op.alter_column("exam_results", "score", nullable=False)
    op.alter_column("exam_results", "maximum_score", nullable=False)
    op.drop_index("ix_exam_results_sync_status_attempt", table_name="exam_results")
    op.drop_constraint(
        "ck_exam_results_synced_at_matches_status", "exam_results", type_="check"
    )
    op.drop_constraint(
        "ck_exam_results_component_score_within_max", "exam_results", type_="check"
    )
    op.drop_constraint(
        "ck_exam_results_component_max_positive", "exam_results", type_="check"
    )
    op.drop_constraint(
        "ck_exam_results_component_score_nonnegative", "exam_results", type_="check"
    )
    op.drop_constraint(
        "ck_exam_results_percentage_within_100", "exam_results", type_="check"
    )
    op.drop_constraint(
        "ck_exam_results_percentage_nonnegative", "exam_results", type_="check"
    )
    op.drop_constraint(
        "ck_exam_results_raw_score_within_max", "exam_results", type_="check"
    )
    op.drop_constraint(
        "ck_exam_results_raw_max_positive", "exam_results", type_="check"
    )
    op.drop_constraint(
        "ck_exam_results_raw_score_nonnegative", "exam_results", type_="check"
    )
    op.create_check_constraint(
        "ck_exam_results_score_within_maximum",
        "exam_results",
        "score <= maximum_score",
    )
    op.create_check_constraint(
        "ck_exam_results_maximum_score_positive",
        "exam_results",
        "maximum_score > 0",
    )
    op.create_check_constraint(
        "ck_exam_results_score_nonnegative",
        "exam_results",
        "score >= 0",
    )
    op.drop_column("exam_results", "component_maximum_score")
    op.drop_column("exam_results", "component_score")
    op.drop_column("exam_results", "percentage")
    op.drop_column("exam_results", "raw_max_score")
    op.drop_column("exam_results", "raw_score")

    op.drop_index(
        op.f("ix_exam_suspensions_resumed_by_actor_id"),
        table_name="exam_suspensions",
    )
    op.drop_index(
        op.f("ix_exam_suspensions_suspended_by_actor_id"),
        table_name="exam_suspensions",
    )
    op.drop_index(
        "ix_exam_suspensions_exam_suspended_at",
        table_name="exam_suspensions",
    )
    op.drop_index(op.f("ix_exam_suspensions_exam_id"), table_name="exam_suspensions")
    op.drop_table("exam_suspensions")

    op.add_column(
        "exam_questions",
        sa.Column(
            "points",
            sa.Numeric(8, 2),
            server_default=sa.text("1"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_exam_questions_points_positive",
        "exam_questions",
        "points > 0",
    )
    op.alter_column("exam_questions", "points", server_default=None)

    op.drop_index(
        op.f("ix_exam_question_selections_question_id"),
        table_name="exam_question_selections",
    )
    op.drop_index(
        "ix_exam_question_selections_exam_position",
        table_name="exam_question_selections",
    )
    op.drop_index(
        op.f("ix_exam_question_selections_exam_id"),
        table_name="exam_question_selections",
    )
    op.drop_table("exam_question_selections")

    op.add_column(
        "exams",
        sa.Column(
            "source_assessment_component_maximum_score",
            sa.Numeric(8, 2),
            nullable=True,
        ),
    )
    op.add_column(
        "exams",
        sa.Column("source_assessment_component_code", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "exams",
        sa.Column("source_assessment_component_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "exams", sa.Column("source_assessment_component_id", sa.Uuid(), nullable=True)
    )
    op.add_column(
        "exams", sa.Column("source_assessment_scheme_id", sa.Uuid(), nullable=True)
    )
    op.add_column("exams", sa.Column("closes_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("exams", sa.Column("opens_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "exams",
        sa.Column("maximum_score", sa.Numeric(8, 2), nullable=True),
    )
    op.execute("UPDATE exams SET opens_at = scheduled_start_at")
    op.execute(
        "UPDATE exams SET maximum_score = COALESCE(component_maximum_score, question_count)"
    )
    op.execute(
        "UPDATE exams SET source_assessment_component_maximum_score = component_maximum_score"
    )
    op.alter_column("exams", "maximum_score", nullable=False)

    op.drop_constraint("ck_exams_cancellation_reason_required", "exams", type_="check")
    op.drop_constraint("ck_exams_cancellation_actor_required", "exams", type_="check")
    op.drop_constraint("ck_exams_activation_actor_required", "exams", type_="check")
    op.drop_constraint("ck_exams_sealing_actor_required", "exams", type_="check")
    op.drop_constraint("ck_exams_component_maximum_positive", "exams", type_="check")
    op.drop_constraint("ck_exams_valid_normal_start_window", "exams", type_="check")
    op.drop_constraint("ck_exams_roster_error_length", "exams", type_="check")
    op.drop_constraint(
        "ck_exams_roster_candidate_count_nonnegative",
        "exams",
        type_="check",
    )
    op.drop_constraint("ck_exams_roster_version_nonnegative", "exams", type_="check")
    op.drop_constraint("ck_exams_revision_lineage_shape", "exams", type_="check")
    op.drop_constraint("ck_exams_revision_positive", "exams", type_="check")
    op.drop_constraint("ck_exams_question_count_positive", "exams", type_="check")
    op.create_check_constraint(
        "ck_exams_valid_schedule",
        "exams",
        "closes_at IS NULL OR opens_at IS NULL OR closes_at > opens_at",
    )
    op.create_check_constraint(
        "ck_exams_source_component_maximum_positive",
        "exams",
        "source_assessment_component_maximum_score IS NULL OR "
        "source_assessment_component_maximum_score > 0",
    )
    op.create_check_constraint(
        "ck_exams_maximum_score_positive",
        "exams",
        "maximum_score > 0",
    )
    op.drop_constraint("exam_status", "exams", type_="check")
    op.create_check_constraint(
        "exam_status",
        "exams",
        "status IN ('draft', 'submitted', 'sealed', 'active', 'closed', 'cancelled')",
    )

    op.drop_index("ix_exams_scheduled_status", table_name="exams")
    op.drop_index("ix_exams_roster_status_exam_status", table_name="exams")
    op.drop_index("uq_exams_scope_title_revision", table_name="exams")
    op.create_index(
        "uq_exams_term_curriculum_subject_title_lower",
        "exams",
        ["term_id", "curriculum_subject_id", sa.text("lower(title)")],
        unique=True,
    )

    op.drop_index(op.f("ix_exams_cancelled_by_actor_id"), table_name="exams")
    op.drop_index(op.f("ix_exams_closed_by_actor_id"), table_name="exams")
    op.drop_index(op.f("ix_exams_activated_by_actor_id"), table_name="exams")
    op.drop_index(op.f("ix_exams_sealed_by_actor_id"), table_name="exams")
    op.drop_index(op.f("ix_exams_revision_of_exam_id"), table_name="exams")
    op.drop_index(op.f("ix_exams_roster_status"), table_name="exams")
    op.drop_index(op.f("ix_exams_latest_normal_start_at"), table_name="exams")
    op.drop_index(op.f("ix_exams_scheduled_start_at"), table_name="exams")
    op.drop_index(op.f("ix_exams_question_selection_mode"), table_name="exams")
    op.drop_index(op.f("ix_exams_question_bank_id"), table_name="exams")

    op.drop_constraint(op.f("fk_exams_cancelled_by_actor_id_local_actors"), "exams", type_="foreignkey")
    op.drop_constraint(op.f("fk_exams_closed_by_actor_id_local_actors"), "exams", type_="foreignkey")
    op.drop_constraint(op.f("fk_exams_activated_by_actor_id_local_actors"), "exams", type_="foreignkey")
    op.drop_constraint(op.f("fk_exams_sealed_by_actor_id_local_actors"), "exams", type_="foreignkey")
    op.drop_constraint(op.f("fk_exams_revision_of_exam_id_exams"), "exams", type_="foreignkey")
    op.drop_constraint(op.f("fk_exams_question_bank_id_question_banks"), "exams", type_="foreignkey")

    op.drop_column("exams", "component_maximum_score")
    op.drop_column("exams", "cancellation_reason")
    op.drop_column("exams", "cancelled_by_actor_id")
    op.drop_column("exams", "closed_by_actor_id")
    op.drop_column("exams", "activated_by_actor_id")
    op.drop_column("exams", "sealed_by_actor_id")
    op.drop_column("exams", "revision_of_exam_id")
    op.drop_column("exams", "revision_number")
    op.drop_column("exams", "roster_error")
    op.drop_column("exams", "roster_prepared_at")
    op.drop_column("exams", "roster_candidate_count")
    op.drop_column("exams", "roster_version")
    op.drop_column("exams", "roster_status")
    op.drop_column("exams", "latest_normal_start_at")
    op.drop_column("exams", "scheduled_start_at")
    op.drop_column("exams", "question_count")
    op.drop_column("exams", "question_selection_mode")
    op.drop_column("exams", "question_bank_id")
