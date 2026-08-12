from __future__ import annotations

import inspect
import os
import unittest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://weave:weave@localhost:5432/weave_cbt_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from app.domains.academics.models import (  # noqa: E402
    AcademicClass,
    AcademicLevel,
    AcademicLevelSubject,
    AssessmentComponent,
    AssessmentScheme,
    StudentEnrollment,
    TeacherAssignment,
)
from app.domains.academics.repository import AcademicRepository  # noqa: E402
from app.domains.exams.models import Exam, ExamStatus, ExamTargetClass  # noqa: E402
from app.domains.exams.repository import ExamRepository  # noqa: E402
from app.domains.questions.models import Question, QuestionBank  # noqa: E402
from app.domains.questions.repository import QuestionRepository  # noqa: E402


class AcademicProjectionContractTests(unittest.TestCase):
    def test_level_does_not_project_weave_progression_ownership(self) -> None:
        columns = set(AcademicLevel.__table__.c.keys())
        self.assertIn("weave_level_id", columns)
        self.assertIn("name", columns)
        self.assertIn("is_active", columns)
        self.assertNotIn("is_terminal", columns)
        self.assertNotIn("weave_next_level_id", columns)
        self.assertNotIn("progression_mode", columns)
        self.assertNotIn("selection_target_type", columns)

    def test_class_is_an_arm_of_a_level(self) -> None:
        columns = set(AcademicClass.__table__.c.keys())
        self.assertIn("level_id", columns)
        self.assertIn("arm", columns)
        self.assertNotIn("subject_id", columns)

    def test_level_subject_is_the_curriculum_anchor(self) -> None:
        columns = set(AcademicLevelSubject.__table__.c.keys())
        self.assertIn("weave_level_subject_id", columns)
        self.assertIn("level_id", columns)
        self.assertIn("subject_id", columns)

    def test_teacher_assignment_is_arm_specific_and_not_session_owned(self) -> None:
        columns = set(TeacherAssignment.__table__.c.keys())
        self.assertIn("teacher_id", columns)
        self.assertIn("class_id", columns)
        self.assertIn("level_subject_id", columns)
        self.assertIn("effective_from", columns)
        self.assertIn("effective_to", columns)
        self.assertNotIn("session_id", columns)
        self.assertNotIn("subject_id", columns)

    def test_assessment_components_belong_to_schemes_not_terms(self) -> None:
        scheme_columns = set(AssessmentScheme.__table__.c.keys())
        component_columns = set(AssessmentComponent.__table__.c.keys())
        self.assertIn("weave_scheme_id", scheme_columns)
        self.assertIn("assessment_scheme_id", component_columns)
        self.assertNotIn("term_id", component_columns)
        self.assertIn("code", component_columns)

    def test_enrollment_preserves_weave_history(self) -> None:
        columns = set(StudentEnrollment.__table__.c.keys())
        self.assertIn("weave_enrollment_id", columns)
        self.assertIn("started_on", columns)
        self.assertIn("ended_on", columns)
        self.assertIn("is_current", columns)
        self.assertIn("outcome", columns)
        self.assertNotIn("is_active", columns)

    def test_question_bank_is_level_subject_scoped_with_provenance(self) -> None:
        bank_columns = set(QuestionBank.__table__.c.keys())
        question_columns = set(Question.__table__.c.keys())
        self.assertIn("level_subject_id", bank_columns)
        self.assertNotIn("level_id", bank_columns)
        self.assertNotIn("subject_id", bank_columns)
        self.assertIn("created_by_actor_id", bank_columns)
        self.assertIn("created_by_actor_id", question_columns)
        self.assertIn("last_edited_by_actor_id", question_columns)

    def test_exam_has_explicit_period_and_level_subject_scope(self) -> None:
        columns = set(Exam.__table__.c.keys())
        self.assertIn("session_id", columns)
        self.assertIn("term_id", columns)
        self.assertIn("level_subject_id", columns)
        self.assertIn("assessment_scheme_id", columns)
        self.assertIn("assessment_component_id", columns)
        self.assertNotIn("level_id", columns)
        self.assertNotIn("subject_id", columns)
        self.assertIn(ExamStatus.SUBMITTED, set(ExamStatus))

    def test_exam_seal_can_snapshot_component_maximum(self) -> None:
        columns = set(Exam.__table__.c.keys())
        self.assertIn("source_assessment_component_maximum_score", columns)

    def test_exam_target_class_can_snapshot_assignment_provenance(self) -> None:
        columns = set(ExamTargetClass.__table__.c.keys())
        self.assertIn("class_id", columns)
        self.assertIn("teacher_assignment_id", columns)
        self.assertIn("weave_teacher_assignment_id", columns)

    def test_assignment_repository_scope_matches_new_contract(self) -> None:
        params = inspect.signature(AcademicRepository.active_assignment_exists).parameters
        self.assertIn("teacher_id", params)
        self.assertIn("class_id", params)
        self.assertIn("level_subject_id", params)
        self.assertNotIn("session_id", params)
        self.assertNotIn("subject_id", params)

    def test_assignment_repository_separates_current_and_historical_queries(self) -> None:
        self.assertFalse(hasattr(AcademicRepository, "get_assignment_for_scope"))

        active_params = inspect.signature(
            AcademicRepository.get_active_assignment_for_scope
        ).parameters
        self.assertIn("teacher_id", active_params)
        self.assertIn("class_id", active_params)
        self.assertIn("level_subject_id", active_params)
        self.assertIn("effective_on", active_params)

        historical_params = inspect.signature(
            AcademicRepository.get_assignment_effective_on
        ).parameters
        self.assertIn("effective_on", historical_params)

    def test_question_repository_uses_level_subject_scope(self) -> None:
        params = inspect.signature(QuestionRepository.get_bank_by_scope_and_name).parameters
        self.assertIn("level_subject_id", params)
        self.assertNotIn("level_id", params)
        self.assertNotIn("subject_id", params)

    def test_exam_repository_filters_direct_period_scope(self) -> None:
        params = inspect.signature(ExamRepository.list_exams).parameters
        self.assertIn("session_id", params)
        self.assertIn("term_id", params)
        self.assertIn("level_subject_id", params)
        self.assertIn("target_class_id", params)


if __name__ == "__main__":
    unittest.main()
