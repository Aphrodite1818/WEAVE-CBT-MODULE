import { useEffect, useMemo, useState } from "react";
import { RiAddLine, RiCalendarTodoLine, RiSearchLine } from "@remixicon/react";
import { Icon } from "../../shared/icons/Icon";
import { Notice, SelectControl, StatusBadge } from "../../shared/ui";

const PAGE_SIZE = 10;
const examTabs = ["all", "draft", "submitted", "sealed", "active", "closed"];

export function TeacherExamsPage({ state, dispatch, teacherData }) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [subjectId, setSubjectId] = useState("all");
  const [componentId, setComponentId] = useState("all");
  const [page, setPage] = useState(1);

  useEffect(() => {
    if (!state.staff.selectedExamId) return;
    const exam = teacherData.exams.find(
      (item) => item.id === state.staff.selectedExamId,
    );
    if (!exam) return;
    setQuery(exam.title);
    setStatus("all");
    setSubjectId("all");
    setComponentId("all");
    setPage(1);
  }, [state.staff.selectedExamId, teacherData.exams]);

  const statusCounts = useMemo(() => {
    const counts = Object.fromEntries(examTabs.map((tab) => [tab, 0]));
    counts.all = teacherData.exams.length;
    teacherData.exams.forEach((exam) => {
      if (counts[exam.status] !== undefined) counts[exam.status] += 1;
    });
    return counts;
  }, [teacherData.exams]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return teacherData.exams.filter((exam) => {
      if (status !== "all" && exam.status !== status) return false;
      if (subjectId !== "all" && exam.curriculumSubjectId !== subjectId)
        return false;
      if (componentId !== "all" && exam.assessmentComponentId !== componentId)
        return false;
      if (!needle) return true;
      return `${exam.title} ${exam.subjectName} ${exam.assessmentName}`
        .toLowerCase()
        .includes(needle);
    });
  }, [componentId, query, status, subjectId, teacherData.exams]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const visibleExams = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  useEffect(() => {
    if (page > pageCount) setPage(pageCount);
  }, [page, pageCount]);

  const setFilter = (setter) => (value) => {
    setter(value);
    setPage(1);
  };

  const subjectOptions = [
    { value: "all", label: "All subjects" },
    ...teacherData.subjects.map((subject) => ({
      value: subject.id,
      label: subject.name,
      description: subject.code || undefined,
    })),
  ];
  const componentOptions = [
    { value: "all", label: "All components" },
    ...teacherData.assessmentComponents.map((component) => ({
      value: component.id,
      label: component.name,
      description: `${component.maximumScore} marks`,
    })),
  ];

  return (
    <div className="teacher-reference-page">
      <div className="teacher-page-heading">
        <div>
          <div className="teacher-page-title-line">
            <span className="teacher-page-title-icon">
              <Icon name="calendar" size={27} />
            </span>
            <h1>Examinations</h1>
          </div>
          <p>
            Create and track the examinations visible to you through your
            teaching or invigilation access.
          </p>
        </div>
        <button
          className="teacher-primary-action"
          type="button"
          onClick={() =>
            dispatch({ type: "staff", patch: { section: "create-exam" } })
          }
        >
          <RiAddLine size={18} /> Create Exam
        </button>
      </div>

      {teacherData.error && <Notice tone="danger">{teacherData.error}</Notice>}

      <nav className="teacher-tab-row" aria-label="Exam status filters">
        {examTabs.map((tab) => (
          <button
            key={tab}
            type="button"
            className={status === tab ? "active" : ""}
            onClick={() => setFilter(setStatus)(tab)}
          >
            {titleCase(tab)} <span>{statusCounts[tab] || 0}</span>
          </button>
        ))}
      </nav>

      <div className="teacher-exam-filters">
        <label className="teacher-search-control teacher-search-control--grow">
          <RiSearchLine size={17} aria-hidden="true" />
          <input
            aria-label="Search exams"
            type="search"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
            placeholder="Search exams..."
          />
        </label>
        <SelectControl
          label="Exam subject filter"
          value={subjectId}
          options={subjectOptions}
          onChange={setFilter(setSubjectId)}
        />
        <SelectControl
          label="Assessment component filter"
          value={componentId}
          options={componentOptions}
          onChange={setFilter(setComponentId)}
        />
      </div>

      <section className="teacher-exam-list" aria-busy={teacherData.loading}>
        <div className="teacher-exam-list__header">
          <span>Title</span>
          <span>Subject</span>
          <span>Assessment</span>
          <span>Questions</span>
          <span>Duration</span>
          <span>Status</span>
          <span>Updated</span>
          <span className="sr-only">Actions</span>
        </div>

        {visibleExams.map((exam) => (
          <article
            key={exam.id}
            className={`teacher-exam-row ${state.staff.selectedExamId === exam.id ? "is-selected" : ""}`}
          >
            <div className="teacher-exam-row__title">
              <strong>{exam.title}</strong>
              <small className="teacher-inline-note">
                {formatSelectionMode(exam.selectionMode)}
              </small>
            </div>
            <span className="teacher-exam-row__text">{exam.subjectName}</span>
            <span className="teacher-exam-row__text">
              {exam.assessmentName}
            </span>
            <span className="teacher-exam-row__text">{exam.questionCount}</span>
            <span className="teacher-exam-row__text">
              {formatDuration(exam.durationMinutes)}
            </span>
            <div>
              <StatusBadge tone={statusTone(exam.status)}>
                {exam.statusLabel}
              </StatusBadge>
            </div>
            <span className="teacher-exam-row__text">
              {formatDate(exam.updatedAt)}
            </span>
            <div className="teacher-exam-row__actions">
              <details className="teacher-row-menu">
                <summary aria-label={`More details for ${exam.title}`}>
                  •••
                </summary>
                <div>
                  <span>
                    <strong>Schedule</strong>
                    {exam.scheduledStartAt
                      ? formatDateTime(exam.scheduledStartAt)
                      : "Not scheduled"}
                  </span>
                  <span>
                    <strong>Roster</strong>
                    {exam.rosterCandidateCount ?? 0} candidates
                  </span>
                  <span>
                    <strong>Paper version</strong>v{exam.authoringVersion || 1}
                  </span>
                </div>
              </details>
            </div>
          </article>
        ))}

        {!teacherData.loading && visibleExams.length === 0 && (
          <div className="teacher-exam-list__empty">
            <RiCalendarTodoLine size={32} />
            <strong>
              {teacherData.exams.length === 0
                ? "No examinations are visible to you yet."
                : "No examinations match the current filters."}
            </strong>
          </div>
        )}

        {teacherData.loading && (
          <div className="teacher-exam-list__empty">
            <strong>Loading examinations…</strong>
          </div>
        )}

        <div className="teacher-exam-pagination">
          <span>
            {filtered.length === 0
              ? "0 exams"
              : `Showing ${(page - 1) * PAGE_SIZE + 1}–${Math.min(page * PAGE_SIZE, filtered.length)} of ${filtered.length} exams`}
          </span>
          <div>
            <button
              type="button"
              disabled={page === 1}
              onClick={() => setPage((current) => current - 1)}
            >
              ‹
            </button>
            <span>
              {page} / {pageCount}
            </span>
            <button
              type="button"
              disabled={page === pageCount}
              onClick={() => setPage((current) => current + 1)}
            >
              ›
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}

export function TeacherCreateExamPage({ dispatch, teacherData, gateway }) {
  const [title, setTitle] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [schemeId, setSchemeId] = useState("");
  const [componentId, setComponentId] = useState("");
  const [bankId, setBankId] = useState("");
  const [selectionMode, setSelectionMode] = useState("random");
  const [questionCount, setQuestionCount] = useState(20);
  const [durationMinutes, setDurationMinutes] = useState(45);
  const [instructions, setInstructions] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const subjectBanks = useMemo(
    () =>
      teacherData.banks.filter(
        (bank) => !subjectId || bank.curriculumSubjectId === subjectId,
      ),
    [subjectId, teacherData.banks],
  );
  const components = useMemo(
    () =>
      teacherData.assessmentComponents.filter(
        (component) => component.schemeId === schemeId,
      ),
    [schemeId, teacherData.assessmentComponents],
  );
  const selectedComponent = components.find(
    (component) => component.id === componentId,
  );

  useEffect(() => {
    if (!subjectId && teacherData.subjects[0])
      setSubjectId(teacherData.subjects[0].id);
    if (!schemeId && teacherData.assessmentSchemes[0])
      setSchemeId(teacherData.assessmentSchemes[0].id);
  }, [
    schemeId,
    subjectId,
    teacherData.assessmentSchemes,
    teacherData.subjects,
  ]);

  useEffect(() => {
    if (subjectBanks.length && !subjectBanks.some((bank) => bank.id === bankId))
      setBankId(subjectBanks[0].id);
    if (!subjectBanks.length) setBankId("");
  }, [bankId, subjectBanks]);

  useEffect(() => {
    if (
      components.length &&
      !components.some((component) => component.id === componentId)
    )
      setComponentId(components[0].id);
    if (!components.length) setComponentId("");
  }, [componentId, components]);

  const createExam = async (event) => {
    event.preventDefault();
    setError("");
    if (!teacherData.session?.id || !teacherData.term?.id)
      return setError(
        "The current academic session and term are not available on this CBT server.",
      );
    if (!title.trim() || !subjectId || !schemeId || !componentId || !bankId)
      return setError(
        "Complete the required exam fields before creating the draft.",
      );
    setSaving(true);
    try {
      const exam = await gateway.exams.createExam({
        session_id: teacherData.session.id,
        term_id: teacherData.term.id,
        curriculum_subject_id: subjectId,
        assessment_scheme_id: schemeId,
        assessment_component_id: componentId,
        question_bank_id: bankId,
        question_selection_mode: selectionMode,
        question_count: Number(questionCount),
        title: title.trim(),
        instructions: instructions.trim() || null,
        duration_minutes: Number(durationMinutes),
        shuffle_questions: true,
        shuffle_options: true,
      });
      await teacherData.refresh();
      dispatch({
        type: "staff",
        patch: { section: "exams", selectedExamId: exam.id },
      });
    } catch (requestError) {
      setError(
        requestError.userMessage || "Weave could not create this examination.",
      );
    } finally {
      setSaving(false);
    }
  };

  const canCreate = Boolean(
    teacherData.session?.id &&
    teacherData.term?.id &&
    teacherData.subjects.length &&
    teacherData.assessmentSchemes.length &&
    subjectBanks.length &&
    components.length,
  );

  return (
    <div className="teacher-reference-page">
      <div className="teacher-page-heading">
        <div>
          <button
            className="text-button"
            type="button"
            onClick={() =>
              dispatch({ type: "staff", patch: { section: "exams" } })
            }
          >
            Back to exams
          </button>
          <div className="teacher-page-title-line">
            <span className="teacher-page-title-icon">
              <Icon name="calendar" size={27} />
            </span>
            <h1>Create Examination</h1>
          </div>
          <p>
            Create a draft paper from the academic context already synchronized
            from Weave.
          </p>
        </div>
      </div>
      {error && <Notice tone="danger">{error}</Notice>}
      {!canCreate && !teacherData.loading && (
        <Notice tone="warning">
          A current session, term, assigned subject, assessment
          scheme/component, and matching question bank are required before a
          teacher can create an exam.
        </Notice>
      )}
      <form className="teacher-exam-create-card" onSubmit={createExam}>
        <div className="teacher-create-section">
          <div>
            <h2>Paper details</h2>
            <p>Define the assessment and the question source for this draft.</p>
          </div>
          <div className="teacher-form-grid">
            <label className="teacher-field teacher-field--wide">
              <span>Exam title</span>
              <input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="e.g. Mathematics CA 1"
              />
            </label>
            <FieldSelect label="Subject">
              <SelectControl
                label="Subject"
                value={subjectId}
                options={teacherData.subjects.map((subject) => ({
                  value: subject.id,
                  label: subject.name,
                  description: subject.code || undefined,
                }))}
                onChange={setSubjectId}
              />
            </FieldSelect>
            <FieldSelect label="Question bank">
              <SelectControl
                label="Question bank"
                value={bankId}
                options={subjectBanks.map((bank) => ({
                  value: bank.id,
                  label: bank.name,
                  description: `${bank.count || 0} questions`,
                }))}
                onChange={setBankId}
                disabled={!subjectBanks.length}
              />
            </FieldSelect>
            <FieldSelect label="Assessment scheme">
              <SelectControl
                label="Assessment scheme"
                value={schemeId}
                options={teacherData.assessmentSchemes.map((scheme) => ({
                  value: scheme.id,
                  label: scheme.name,
                }))}
                onChange={setSchemeId}
              />
            </FieldSelect>
            <FieldSelect
              label="Assessment component"
              helper={
                selectedComponent
                  ? `Maximum academic score: ${selectedComponent.maximumScore}`
                  : ""
              }
            >
              <SelectControl
                label="Assessment component"
                value={componentId}
                options={components.map((component) => ({
                  value: component.id,
                  label: component.name,
                  description: `${component.maximumScore} marks`,
                }))}
                onChange={setComponentId}
                disabled={!components.length}
              />
            </FieldSelect>
            <FieldSelect label="Question selection">
              <SelectControl
                label="Question selection"
                value={selectionMode}
                options={[
                  {
                    value: "random",
                    label: "Random selection",
                    description:
                      "Weave chooses from the active bank at sealing.",
                  },
                  {
                    value: "manual",
                    label: "Manual selection",
                    description: "Teachers curate the exact paper.",
                  },
                ]}
                onChange={setSelectionMode}
              />
            </FieldSelect>
            <label className="teacher-field">
              <span>Questions</span>
              <input
                type="number"
                min="1"
                value={questionCount}
                onChange={(event) => setQuestionCount(event.target.value)}
              />
            </label>
            <label className="teacher-field">
              <span>Duration (minutes)</span>
              <input
                type="number"
                min="1"
                value={durationMinutes}
                onChange={(event) => setDurationMinutes(event.target.value)}
              />
            </label>
            <label className="teacher-field teacher-field--wide">
              <span>
                Instructions <small>(optional)</small>
              </span>
              <textarea
                value={instructions}
                onChange={(event) => setInstructions(event.target.value)}
                placeholder="Instructions students should see for this paper."
              />
            </label>
          </div>
        </div>
        <div className="teacher-create-footer">
          <div>
            <strong>{teacherData.session?.name || "No current session"}</strong>
            <span>{teacherData.term?.name || "No current term"}</span>
          </div>
          <div>
            <button
              className="teacher-secondary-action"
              type="button"
              onClick={() =>
                dispatch({ type: "staff", patch: { section: "exams" } })
              }
            >
              Cancel
            </button>
            <button
              className="teacher-primary-action"
              type="submit"
              disabled={!canCreate || saving}
            >
              {saving ? "Creating…" : "Create Draft Exam"}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}

function FieldSelect({ label, helper, children }) {
  return (
    <div className="teacher-field">
      <span>{label}</span>
      {children}
      {helper && <small>{helper}</small>}
    </div>
  );
}

function statusTone(status) {
  if (status === "active" || status === "closed") return "success";
  if (status === "draft") return "warning";
  if (status === "cancelled" || status === "suspended") return "danger";
  return "info";
}

function titleCase(value) {
  return String(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
function formatSelectionMode(mode) {
  return mode === "manual" ? "Manual paper" : "Random paper";
}
function formatDuration(minutes) {
  return `${minutes} min`;
}
function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleDateString();
}
function formatDateTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString();
}
