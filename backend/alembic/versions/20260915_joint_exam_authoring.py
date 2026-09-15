"""add joint exam authoring coordination

Revision ID: 20260915_joint_authoring
Revises: 20260914_sync_v5
Create Date: 2026-09-15

One shared paper is authoritative for a term + level-subject + assessment
component. The mutable paper carries a monotonic authoring version and manual
question contributions retain the actor who added them.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260915_joint_authoring"
down_revision: str | Sequence[str] | None = "20260914_sync_v5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_SELECTION_TRIGGER = "trg_exam_selection_contributor"
_FROZEN_TRIGGER = "trg_exam_question_contributor"
_SELECTION_FUNCTION = "weave_cbt_fill_selection_contributor"
_FROZEN_FUNCTION = "weave_cbt_fill_frozen_contributor"


def upgrade() -> None:
    op.add_column(
        "exams",
        sa.Column(
            "authoring_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.create_check_constraint(
        "ck_exams_authoring_version_positive",
        "exams",
        "authoring_version >= 1",
    )

    # A title is presentation only. It must not allow two independent papers
    # for the same academic assessment scope.
    op.drop_index("uq_exams_scope_title_revision", table_name="exams")
    op.create_index(
        "uq_exams_scope_revision",
        "exams",
        [
            "term_id",
            "curriculum_subject_id",
            "assessment_component_id",
            "revision_number",
        ],
        unique=True,
    )

    op.add_column(
        "exam_question_selections",
        sa.Column("added_by_actor_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_exam_question_selections_added_by_actor_id_local_actors",
        "exam_question_selections",
        "local_actors",
        ["added_by_actor_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(
        sa.text(
            """
            UPDATE exam_question_selections AS selection
            SET added_by_actor_id = exam.created_by_actor_id
            FROM exams AS exam
            WHERE exam.id = selection.exam_id
              AND selection.added_by_actor_id IS NULL
            """
        )
    )
    op.alter_column(
        "exam_question_selections",
        "added_by_actor_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.create_index(
        "ix_exam_question_selections_added_by_actor_id",
        "exam_question_selections",
        ["added_by_actor_id"],
        unique=False,
    )

    op.add_column(
        "exam_questions",
        sa.Column("added_by_actor_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_exam_questions_added_by_actor_id_local_actors",
        "exam_questions",
        "local_actors",
        ["added_by_actor_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_exam_questions_added_by_actor_id",
        "exam_questions",
        ["added_by_actor_id"],
        unique=False,
    )

    # Revision creation already knows only the source question id. Preserve the
    # previous frozen contributor automatically, falling back to the new lead.
    op.execute(
        sa.text(
            f"""
            CREATE FUNCTION {_SELECTION_FUNCTION}()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                IF NEW.added_by_actor_id IS NULL THEN
                    SELECT COALESCE(frozen.added_by_actor_id, exam.created_by_actor_id)
                    INTO NEW.added_by_actor_id
                    FROM exams AS exam
                    LEFT JOIN exam_questions AS frozen
                      ON frozen.exam_id = exam.revision_of_exam_id
                     AND frozen.source_question_id = NEW.question_id
                    WHERE exam.id = NEW.exam_id;
                END IF;
                RETURN NEW;
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE TRIGGER {_SELECTION_TRIGGER}
            BEFORE INSERT ON exam_question_selections
            FOR EACH ROW
            EXECUTE FUNCTION {_SELECTION_FUNCTION}()
            """
        )
    )

    # Sealing clears draft selections after the frozen paper is written. Copy
    # contributor provenance into the immutable question snapshot before that.
    op.execute(
        sa.text(
            f"""
            CREATE FUNCTION {_FROZEN_FUNCTION}()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                IF NEW.added_by_actor_id IS NULL THEN
                    SELECT selection.added_by_actor_id
                    INTO NEW.added_by_actor_id
                    FROM exam_question_selections AS selection
                    WHERE selection.exam_id = NEW.exam_id
                      AND selection.question_id = NEW.source_question_id;
                END IF;
                RETURN NEW;
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE TRIGGER {_FROZEN_TRIGGER}
            BEFORE INSERT ON exam_questions
            FOR EACH ROW
            EXECUTE FUNCTION {_FROZEN_FUNCTION}()
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text(f"DROP TRIGGER IF EXISTS {_FROZEN_TRIGGER} ON exam_questions"))
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {_FROZEN_FUNCTION}()"))
    op.execute(
        sa.text(
            f"DROP TRIGGER IF EXISTS {_SELECTION_TRIGGER} "
            "ON exam_question_selections"
        )
    )
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {_SELECTION_FUNCTION}()"))

    op.drop_index("ix_exam_questions_added_by_actor_id", table_name="exam_questions")
    op.drop_constraint(
        "fk_exam_questions_added_by_actor_id_local_actors",
        "exam_questions",
        type_="foreignkey",
    )
    op.drop_column("exam_questions", "added_by_actor_id")

    op.drop_index(
        "ix_exam_question_selections_added_by_actor_id",
        table_name="exam_question_selections",
    )
    op.drop_constraint(
        "fk_exam_question_selections_added_by_actor_id_local_actors",
        "exam_question_selections",
        type_="foreignkey",
    )
    op.drop_column("exam_question_selections", "added_by_actor_id")

    op.drop_index("uq_exams_scope_revision", table_name="exams")
    op.execute(
        sa.text(
            """
            CREATE UNIQUE INDEX uq_exams_scope_title_revision
            ON exams (
                term_id,
                curriculum_subject_id,
                assessment_component_id,
                lower(title),
                revision_number
            )
            """
        )
    )

    op.drop_constraint(
        "ck_exams_authoring_version_positive",
        "exams",
        type_="check",
    )
    op.drop_column("exams", "authoring_version")
