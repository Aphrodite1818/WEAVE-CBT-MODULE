"""PostgreSQL contributor provenance required by exam revision and sealing."""

from sqlalchemy import text
from sqlalchemy.engine import Connection

CONTRIBUTOR_TRIGGERS = {
    ("exam_question_selections", "trg_exam_selection_contributor"),
    ("exam_questions", "trg_exam_question_contributor"),
}


def create_contributor_triggers(connection: Connection) -> None:
    """Install fresh-schema triggers after all referenced tables exist."""
    statements = (
        """
        CREATE FUNCTION public.weave_cbt_fill_selection_contributor()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.added_by_actor_id IS NULL THEN
                SELECT COALESCE(frozen.added_by_actor_id, exam.created_by_actor_id)
                INTO NEW.added_by_actor_id
                FROM public.exams AS exam
                LEFT JOIN public.exam_questions AS frozen
                  ON frozen.exam_id = exam.revision_of_exam_id
                 AND frozen.source_question_id = NEW.question_id
                WHERE exam.id = NEW.exam_id;
            END IF;
            RETURN NEW;
        END;
        $$
        """,
        """
        CREATE TRIGGER trg_exam_selection_contributor
        BEFORE INSERT ON public.exam_question_selections
        FOR EACH ROW EXECUTE FUNCTION public.weave_cbt_fill_selection_contributor()
        """,
        """
        CREATE FUNCTION public.weave_cbt_fill_frozen_contributor()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.added_by_actor_id IS NULL THEN
                SELECT selection.added_by_actor_id INTO NEW.added_by_actor_id
                FROM public.exam_question_selections AS selection
                WHERE selection.exam_id = NEW.exam_id
                  AND selection.question_id = NEW.source_question_id;
            END IF;
            RETURN NEW;
        END;
        $$
        """,
        """
        CREATE TRIGGER trg_exam_question_contributor
        BEFORE INSERT ON public.exam_questions
        FOR EACH ROW EXECUTE FUNCTION public.weave_cbt_fill_frozen_contributor()
        """,
    )
    for statement in statements:
        connection.execute(text(statement))
