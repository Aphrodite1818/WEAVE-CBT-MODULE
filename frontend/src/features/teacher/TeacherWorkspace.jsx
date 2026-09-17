import { useCallback, useEffect, useState } from "react";
import { weaveGateway } from "../../app/gateway";
import { TeacherLayout } from "./TeacherLayout";
import { OverviewPage } from "./OverviewPage";
import { BankDetailPage, QuestionBanksPage } from "./QuestionBanksPage";
import { QuestionBuilder } from "./QuestionBuilder";
import { TeacherCreateExamPage, TeacherExamsPage } from "./TeacherExamsPage";
import { TeacherQuestionsPage } from "./TeacherQuestionsPage";
import { TeacherQuestionPreviewPage } from "./TeacherQuestionPreviewPage";
import "./teacher-dashboard.css";
import "./teacher-selects.css";
import "./teacher-exams.css";

const emptyTeacherData = {
  banks: [],
  questions: [],
  exams: [],
  subjects: [],
  assignments: [],
  assessmentSchemes: [],
  assessmentComponents: [],
  session: null,
  term: null,
};

export function TeacherWorkspace({
  state,
  dispatch,
  signOut,
  gateway = weaveGateway,
}) {
  const teacherData = useTeacherData(gateway);

  return (
    <TeacherLayout state={state} dispatch={dispatch} signOut={signOut}>
      {state.staff.section === "overview" && (
        <OverviewPage
          state={state}
          dispatch={dispatch}
          teacherData={teacherData}
        />
      )}
      {state.staff.section === "question-banks" && (
        <QuestionBanksPage dispatch={dispatch} teacherData={teacherData} />
      )}
      {state.staff.section === "bank-detail" && (
        <BankDetailPage
          state={state}
          dispatch={dispatch}
          teacherData={teacherData}
        />
      )}
      {state.staff.section === "questions" && (
        <TeacherQuestionsPage
          state={state}
          dispatch={dispatch}
          teacherData={teacherData}
          gateway={gateway}
        />
      )}
      {state.staff.section === "preview-question" && (
        <TeacherQuestionPreviewPage
          state={state}
          dispatch={dispatch}
          teacherData={teacherData}
          gateway={gateway}
        />
      )}
      {state.staff.section === "create-question" && (
        <QuestionBuilder
          mode="create"
          state={state}
          dispatch={dispatch}
          teacherData={teacherData}
          gateway={gateway}
        />
      )}
      {state.staff.section === "edit-question" && (
        <QuestionBuilder
          key={state.staff.selectedQuestionId || "teacher-question-editor"}
          mode="edit"
          state={state}
          dispatch={dispatch}
          teacherData={teacherData}
          gateway={gateway}
        />
      )}
      {state.staff.section === "exams" && (
        <TeacherExamsPage
          state={state}
          dispatch={dispatch}
          teacherData={teacherData}
          gateway={gateway}
        />
      )}
      {state.staff.section === "create-exam" && (
        <TeacherCreateExamPage
          state={state}
          dispatch={dispatch}
          teacherData={teacherData}
          gateway={gateway}
        />
      )}
    </TeacherLayout>
  );
}

function useTeacherData(gateway) {
  const [data, setData] = useState(emptyTeacherData);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [warning, setWarning] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    setWarning("");
    try {
      const loaded = await loadTeacherData(gateway);
      setData(loaded.data);
      setWarning(loaded.warning);
    } catch (requestError) {
      setError(
        requestError.userMessage || "Weave could not load teacher content.",
      );
      setData(emptyTeacherData);
    } finally {
      setLoading(false);
    }
  }, [gateway]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    loadTeacherData(gateway)
      .then((loaded) => {
        if (cancelled) return;
        setData(loaded.data);
        setWarning(loaded.warning);
        setError("");
      })
      .catch((requestError) => {
        if (cancelled) return;
        setError(
          requestError.userMessage || "Weave could not load teacher content.",
        );
        setData(emptyTeacherData);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [gateway]);

  return { ...data, loading, error, warning, refresh };
}

async function loadTeacherData(gateway) {
  const warnings = [];
  const bankRows = await gateway.questions.listAuthorableQuestionBanks();

  const optional = async (request, fallback) => {
    if (typeof request !== "function") return fallback;
    try {
      const value = await request();
      return value ?? fallback;
    } catch (requestError) {
      warnings.push(
        requestError.userMessage ||
          requestError.message ||
          "Some teacher data could not be loaded.",
      );
      return fallback;
    }
  };

  const [
    sessionRow,
    termRow,
    subjectRows,
    assignmentRows,
    examPayload,
    schemeRows,
  ] = await Promise.all([
    optional(gateway.academics?.getCurrentAcademicSession, null),
    optional(gateway.academics?.getCurrentAcademicTerm, null),
    optional(gateway.academics?.listAuthorableCurriculumSubjects, []),
    optional(gateway.academics?.listEffectiveTeacherAssignments, []),
    optional(() => gateway.exams?.listExams?.({ limit: 200 }), { exams: [] }),
    optional(
      () => gateway.academics?.listAssessmentSchemes?.({ active_only: true }),
      [],
    ),
  ]);

  const questionGroups = await Promise.all(
    bankRows.map((bank) =>
      gateway.questions
        .listQuestionsForBank(bank.id, { include_archived: true })
        .then((items) =>
          items.map((question) => normalizeQuestion(question, bank)),
        )
        .catch((requestError) => {
          warnings.push(
            requestError.userMessage ||
              requestError.message ||
              `Questions for ${bank.name} could not be loaded.`,
          );
          return [];
        }),
    ),
  );
  const questions = questionGroups.flat();

  const componentGroups = await Promise.all(
    schemeRows.map((scheme) =>
      optional(
        () =>
          gateway.academics?.listAssessmentComponents?.(scheme.id, {
            active_only: true,
          }),
        [],
      ),
    ),
  );

  const subjects = subjectRows.map(normalizeSubject);
  const assignments = assignmentRows.map(normalizeAssignment);
  const assessmentSchemes = schemeRows.map(normalizeAssessmentScheme);
  const assessmentComponents = componentGroups
    .flat()
    .map(normalizeAssessmentComponent);
  const subjectByCurriculum = new Map(
    subjects.map((subject) => [subject.id, subject]),
  );
  const componentById = new Map(
    assessmentComponents.map((component) => [component.id, component]),
  );
  const examRows = Array.isArray(examPayload)
    ? examPayload
    : examPayload?.exams || [];

  return {
    data: {
      banks: bankRows.map((bank) => normalizeBank(bank, questions)),
      questions,
      exams: examRows.map((exam) =>
        normalizeExam(exam, subjectByCurriculum, componentById),
      ),
      subjects,
      assignments,
      assessmentSchemes,
      assessmentComponents,
      session: sessionRow ? normalizeSession(sessionRow) : null,
      term: termRow ? normalizeTerm(termRow) : null,
    },
    warning: warnings[0] || "",
  };
}

function normalizeBank(bank, questions) {
  const bankQuestions = questions.filter((question) => question.bankId === bank.id);
  return {
    id: bank.id,
    curriculumSubjectId: bank.curriculum_subject_id,
    name: bank.name,
    description: bank.description,
    status: bank.is_active ? "Ready" : "Archived",
    count: bankQuestions.length,
    activeQuestionCount: bankQuestions.filter((question) => question.status === "Ready").length,
  };
}

function normalizeQuestion(question, bank) {
  return {
    id: question.id,
    bankId: question.bank_id,
    prompt: question.prompt,
    instruction: question.instruction,
    type:
      question.question_type === "multiple_choice"
        ? "Multiple choice"
        : "Single choice",
    image: Boolean(question.image_asset_id),
    imageAssetId: question.image_asset_id,
    status: question.is_active ? "Ready" : "Archived",
    updated: `v${question.version}`,
    version: question.version,
    options: question.options,
    bankName: bank.name,
    createdByActorId: question.created_by_actor_id,
    lastEditedByActorId: question.last_edited_by_actor_id,
  };
}

function normalizeSubject(subject) {
  return {
    id: subject.id,
    curriculumId: subject.curriculum_id,
    subjectId: subject.subject_id,
    name: subject.subject_name,
    code: subject.subject_code,
    isElective: subject.is_elective,
    isActive: subject.is_active,
  };
}

function normalizeAssignment(assignment) {
  return {
    id: assignment.id,
    curriculumSubjectId: assignment.curriculum_subject_id,
    subjectId: assignment.subject_id,
    subjectName: assignment.subject_name,
    subjectCode: assignment.subject_code,
    classId: assignment.class_id,
    className: assignment.class_name,
    effectiveFrom: assignment.effective_from,
    effectiveTo: assignment.effective_to,
  };
}

function normalizeAssessmentScheme(scheme) {
  return { id: scheme.id, name: scheme.name, status: scheme.status };
}

function normalizeAssessmentComponent(component) {
  return {
    id: component.id,
    schemeId: component.assessment_scheme_id,
    name: component.name,
    code: component.code,
    maximumScore: Number(component.maximum_score),
    position: component.position,
    isActive: component.is_active,
  };
}

function normalizeSession(session) {
  return {
    id: session.id,
    name: session.name,
    status: session.status,
    isCurrent: session.is_current,
  };
}

function normalizeTerm(term) {
  return {
    id: term.id,
    sessionId: term.academic_session_id,
    name: term.name,
    status: term.status,
    isCurrent: term.is_current,
  };
}

function normalizeExam(exam, subjectByCurriculum, componentById) {
  const status = String(exam.status || "draft").toLowerCase();
  const subject = subjectByCurriculum.get(exam.curriculum_subject_id);
  const component = componentById.get(exam.assessment_component_id);
  return {
    id: exam.id,
    sessionId: exam.session_id,
    termId: exam.term_id,
    title: exam.title,
    instructions: exam.instructions || "",
    subjectName: subject?.name || "Subject",
    subjectCode: subject?.code || "",
    curriculumSubjectId: exam.curriculum_subject_id,
    assessmentSchemeId: exam.assessment_scheme_id,
    assessmentComponentId: exam.assessment_component_id,
    assessmentName: component?.name || "Assessment",
    questionBankId: exam.question_bank_id,
    questionCount: exam.question_count,
    selectionMode: exam.question_selection_mode,
    durationMinutes: exam.duration_minutes,
    shuffleQuestions: exam.shuffle_questions,
    shuffleOptions: exam.shuffle_options,
    status,
    statusLabel: status
      .replaceAll("_", " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase()),
    scheduledStartAt: exam.scheduled_start_at,
    latestNormalStartAt: exam.latest_normal_start_at,
    rosterStatus: exam.roster_status,
    rosterCandidateCount: exam.roster_candidate_count,
    authoringVersion: exam.authoring_version,
    revisionNumber: exam.revision_number,
    revisionOfExamId: exam.revision_of_exam_id,
    createdByActorId: exam.created_by_actor_id,
    componentMaximumScore: exam.component_maximum_score,
    createdAt: exam.created_at,
    updatedAt: exam.updated_at,
  };
}