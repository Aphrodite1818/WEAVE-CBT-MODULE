import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  RiAddLine,
  RiDeleteBinLine,
  RiEdit2Line,
  RiSearchLine,
} from "@remixicon/react";
import { Icon } from "../../shared/icons/Icon";
import { Notice, SelectControl, StatusBadge } from "../../shared/ui";

const PAGE_SIZE = 10;
const EXAM_TABS = [
  "all",
  "draft",
  "submitted",
  "sealed",
  "active",
  "suspended",
  "closed",
  "cancelled",
];
const POPOVER_WIDTH = 320;
const VIEWPORT_GAP = 12;

export function TeacherExamsPage({ state, dispatch, teacherData, gateway }) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [subjectId, setSubjectId] = useState("all");
  const [componentId, setComponentId] = useState("all");
  const [page, setPage] = useState(1);
  const [menuExamId, setMenuExamId] = useState(null);
  const [menuPosition, setMenuPosition] = useState(null);
  const [pendingAction, setPendingAction] = useState(null);
  const [lifecycleError, setLifecycleError] = useState("");
  const [busyExamId, setBusyExamId] = useState(null);
  const menuRef = useRef(null);
  const actor = state.session?.actor;

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

  useEffect(() => {
    if (!menuExamId) return undefined;

    const closeOutside = (event) => {
      if (!menuRef.current?.contains(event.target)) closeMenu();
    };
    const closeEscape = (event) => {
      if (event.key === "Escape") closeMenu();
    };
    const closeViewport = () => closeMenu();

    document.addEventListener("pointerdown", closeOutside);
    document.addEventListener("keydown", closeEscape);
    window.addEventListener("resize", closeViewport);
    window.addEventListener("scroll", closeViewport, true);

    return () => {
      document.removeEventListener("pointerdown", closeOutside);
      document.removeEventListener("keydown", closeEscape);
      window.removeEventListener("resize", closeViewport);
      window.removeEventListener("scroll", closeViewport, true);
    };
  }, [menuExamId]);

  useEffect(() => {
    if (!pendingAction) return undefined;
    const closeEscape = (event) => {
      if (event.key === "Escape" && !busyExamId) closeConfirmation();
    };
    document.addEventListener("keydown", closeEscape);
    return () => document.removeEventListener("keydown", closeEscape);
  }, [pendingAction, busyExamId]);

  const statusCounts = useMemo(() => {
    const counts = Object.fromEntries(EXAM_TABS.map((tab) => [tab, 0]));
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
  const visibleExams = filtered.slice(
    (page - 1) * PAGE_SIZE,
    page * PAGE_SIZE,
  );

  useEffect(() => {
    if (page > pageCount) setPage(pageCount);
  }, [page, pageCount]);

  const applyFilter = (setter) => (value) => {
    setter(value);
    setPage(1);
  };

  const closeMenu = () => {
    setMenuExamId(null);
    setMenuPosition(null);
  };

  const toggleMenu = (exam, trigger) => {
    if (menuExamId === exam.id) {
      closeMenu();
      return;
    }
    setMenuPosition(getPopoverPosition(trigger));
    setMenuExamId(exam.id);
  };

  const requestAction = (exam, action) => {
    closeMenu();
    setLifecycleError("");
    setPendingAction({ exam, action });
  };

  const closeConfirmation = () => {
    if (busyExamId) return;
    setPendingAction(null);
    setLifecycleError("");
  };

  const confirmLifecycle = async () => {
    if (!pendingAction) return;
    const { exam, action } = pendingAction;
    setLifecycleError("");
    setBusyExamId(exam.id);

    try {
      if (action === "submit") {
        await gateway.exams.submitExam(exam.id, exam.authoringVersion || 1);
      } else if (action === "delete") {
        await gateway.exams.deleteDraftExam(
          exam.id,
          exam.authoringVersion || 1,
        );
      }
      await teacherData.refresh();
      setPendingAction(null);
      dispatch({ type: "staff", patch: { selectedExamId: null } });
    } catch (requestError) {
      setLifecycleError(
        requestError.userMessage ||
          `Weave could not ${action} this examination.`,
      );
    } finally {
      setBusyExamId(null);
    }
  };

  const openCreate = () =>
    dispatch({
      type: "staff",
      patch: { section: "create-exam", selectedExamId: null },
    });

  const openEdit = (exam) => {
    closeMenu();
    dispatch({
      type: "staff",
      patch: { section: "create-exam", selectedExamId: exam.id },
    });
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
  const confirmationCopy = pendingAction
    ? getLifecycleConfirmation(pendingAction.action)
    : null;

  return (
    <div className="teacher-reference-page teacher-exams-page">
      <div className="teacher-page-heading teacher-exams-heading">
        <div>
          <div className="teacher-page-title-line">
            <span className="teacher-page-title-icon">
              <Icon name="calendar" size={27} />
            </span>
            <h1>Examinations</h1>
          </div>
          <p>
            Build draft papers, track their progress, and keep each assessment
            tied to the synchronized academic context.
          </p>
        </div>
        <button
          className="teacher-primary-action"
          type="button"
          onClick={openCreate}
        >
          <RiAddLine size={18} /> Create Exam
        </button>
      </div>

      {teacherData.error && <Notice tone="danger">{teacherData.error}</Notice>}
      {teacherData.warning && (
        <Notice tone="warning">{teacherData.warning}</Notice>
      )}

      <nav
        className="teacher-tab-row teacher-exam-tabs"
        aria-label="Exam status filters"
      >
        {EXAM_TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            className={status === tab ? "active" : ""}
            aria-current={status === tab ? "page" : undefined}
            onClick={() => applyFilter(setStatus)(tab)}
          >
            {titleCase(tab)} <span>{statusCounts[tab] || 0}</span>
          </button>
        ))}
      </nav>

      <div className="teacher-exam-filters teacher-exam-filters--refined">
        <label className="teacher-search-control teacher-search-control--grow">
          <RiSearchLine size={18} aria-hidden="true" />
          <input
            aria-label="Search examinations"
            type="search"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
            placeholder="Search by title, subject, or assessment..."
          />
        </label>
        <SelectControl
          label="Exam subject filter"
          value={subjectId}
          options={subjectOptions}
          onChange={applyFilter(setSubjectId)}
        />
        <SelectControl
          label="Assessment component filter"
          value={componentId}
          options={componentOptions}
          onChange={applyFilter(setComponentId)}
        />
      </div>

      <section
        className="teacher-exam-collection"
        aria-busy={teacherData.loading}
        aria-label="Examinations"
      >
        <div className="teacher-exam-collection__header" aria-hidden="true">
          <span>Examination</span>
          <span>Academic context</span>
          <span>Paper</span>
          <span>Schedule</span>
          <span>Status</span>
          <span>Updated</span>
          <span>Actions</span>
        </div>

        {visibleExams.map((exam) => {
          const canManageDraft =
            exam.status === "draft" &&
            (actor?.role === "admin" || actor?.id === exam.createdByActorId);

          return (
            <article
              key={exam.id}
              className={`teacher-exam-entity ${
                state.staff.selectedExamId === exam.id ? "is-selected" : ""
              }`}
            >
              <div className="teacher-exam-entity__title">
                <span className="teacher-exam-entity__icon">
                  <Icon name="exam" size={20} />
                </span>
                <div>
                  <h2>{exam.title}</h2>
                  <p>
                    {formatSelectionMode(exam.selectionMode)} · Revision{" "}
                    {exam.revisionNumber || 1}
                  </p>
                </div>
              </div>

              <div
                className="teacher-exam-entity__stack"
                data-label="Academic context"
              >
                <strong>{exam.subjectName}</strong>
                <span>{exam.assessmentName}</span>
              </div>

              <div className="teacher-exam-entity__stack" data-label="Paper">
                <strong>{pluralize(exam.questionCount, "question")}</strong>
                <span>{formatDuration(exam.durationMinutes)}</span>
              </div>

              <div
                className="teacher-exam-entity__stack"
                data-label="Schedule"
              >
                <strong>
                  {exam.scheduledStartAt
                    ? formatShortDate(exam.scheduledStartAt)
                    : "Not scheduled"}
                </strong>
                <span>
                  {exam.scheduledStartAt
                    ? formatTime(exam.scheduledStartAt)
                    : "Draft timing"}
                </span>
              </div>

              <div data-label="Status">
                <StatusBadge tone={statusTone(exam.status)}>
                  {exam.statusLabel}
                </StatusBadge>
              </div>

              <div
                className="teacher-exam-entity__updated"
                data-label="Updated"
              >
                {formatDate(exam.updatedAt)}
              </div>

              <div
                className="teacher-exam-entity__actions"
                data-label="Actions"
              >
                <div
                  className="teacher-exam-lifecycle"
                  ref={menuExamId === exam.id ? menuRef : undefined}
                >
                  <button
                    className="teacher-exam-lifecycle__trigger"
                    type="button"
                    aria-label={`Lifecycle actions for ${exam.title}`}
                    aria-haspopup="dialog"
                    aria-expanded={menuExamId === exam.id}
                    onClick={(event) => toggleMenu(exam, event.currentTarget)}
                  >
                    <Icon name="moreVertical" size={19} />
                  </button>

                  {menuExamId === exam.id && menuPosition && (
                    <div
                      className="teacher-exam-lifecycle__menu"
                      role="dialog"
                      aria-label={`Lifecycle for ${exam.title}`}
                      style={menuPosition}
                    >
                      <div className="teacher-exam-lifecycle__heading">
                        <div>
                          <strong>Exam lifecycle</strong>
                          <span>{exam.statusLabel}</span>
                        </div>
                        <small>v{exam.authoringVersion || 1}</small>
                      </div>

                      {canManageDraft ? (
                        <>
                          <button type="button" onClick={() => openEdit(exam)}>
                            <RiEdit2Line size={18} />
                            <span>
                              <strong>Edit draft details</strong>
                              <small>
                                Update assessment, timing, instructions and
                                delivery settings.
                              </small>
                            </span>
                          </button>

                          <button
                            type="button"
                            onClick={() => requestAction(exam, "submit")}
                          >
                            <Icon name="submit" size={18} />
                            <span>
                              <strong>Submit for review</strong>
                              <small>
                                Finish teacher authoring and send the paper to
                                administration.
                              </small>
                            </span>
                          </button>

                          <button
                            type="button"
                            className="teacher-exam-lifecycle__danger"
                            onClick={() => requestAction(exam, "delete")}
                          >
                            <RiDeleteBinLine size={18} />
                            <span>
                              <strong>Delete draft</strong>
                              <small>Permanently remove this draft paper.</small>
                            </span>
                          </button>
                        </>
                      ) : (
                        <div className="teacher-exam-lifecycle__info">
                          <Icon name="info" size={18} />
                          <p>{lifecycleMessage(exam.status)}</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </article>
          );
        })}

        {!teacherData.loading && visibleExams.length === 0 && (
          <div className="teacher-exam-collection__empty">
            <span>
              <Icon name="calendar" size={24} />
            </span>
            <strong>
              {teacherData.exams.length === 0
                ? "No examinations yet"
                : "No examinations match these filters"}
            </strong>
            <p>
              {teacherData.exams.length === 0
                ? "Create the first draft paper for your current teaching scope."
                : "Adjust the search, subject, component, or lifecycle filter."}
            </p>
          </div>
        )}

        {teacherData.loading && (
          <div className="teacher-exam-collection__empty">
            <strong>Loading examinations…</strong>
          </div>
        )}

        <div className="teacher-exam-pagination teacher-exam-pagination--refined">
          <span>
            {filtered.length === 0
              ? "0 exams"
              : `Showing ${(page - 1) * PAGE_SIZE + 1}–${Math.min(
                  page * PAGE_SIZE,
                  filtered.length,
                )} of ${filtered.length} exams`}
          </span>
          <div>
            <button
              type="button"
              aria-label="Previous page"
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
              aria-label="Next page"
              disabled={page === pageCount}
              onClick={() => setPage((current) => current + 1)}
            >
              ›
            </button>
          </div>
        </div>
      </section>

      {pendingAction &&
        confirmationCopy &&
        typeof document !== "undefined" &&
        createPortal(
          <div
            className="teacher-exam-confirm-backdrop"
            onMouseDown={(event) => {
              if (event.currentTarget === event.target) closeConfirmation();
            }}
          >
            <section
              className={`teacher-exam-confirm-modal ${
                pendingAction.action === "delete" ? "is-danger" : ""
              }`}
              role="alertdialog"
              aria-modal="true"
              aria-labelledby="teacher-exam-confirm-title"
              aria-describedby="teacher-exam-confirm-description"
            >
              <div className="teacher-exam-confirm-modal__heading">
                <span>
                  {pendingAction.action === "delete" ? (
                    <RiDeleteBinLine size={22} />
                  ) : (
                    <Icon name="submit" size={22} />
                  )}
                </span>
                <div>
                  <h2 id="teacher-exam-confirm-title">
                    {confirmationCopy.title}
                  </h2>
                  <p id="teacher-exam-confirm-description">
                    {confirmationCopy.description}
                  </p>
                </div>
              </div>

              <div className="teacher-exam-confirm-modal__exam">
                <span>Examination</span>
                <strong>{pendingAction.exam.title}</strong>
                <small>
                  {pendingAction.exam.subjectName} ·{" "}
                  {pendingAction.exam.assessmentName}
                </small>
              </div>

              <p className="teacher-exam-confirm-modal__warning">
                {confirmationCopy.warning}
              </p>

              {lifecycleError && (
                <Notice tone="danger">{lifecycleError}</Notice>
              )}

              <div className="teacher-exam-confirm-modal__actions">
                <button
                  type="button"
                  className="teacher-exam-confirm-modal__cancel"
                  disabled={busyExamId === pendingAction.exam.id}
                  onClick={closeConfirmation}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className={`teacher-exam-confirm-modal__confirm ${
                    pendingAction.action === "delete" ? "is-danger" : ""
                  }`}
                  disabled={busyExamId === pendingAction.exam.id}
                  onClick={confirmLifecycle}
                >
                  {busyExamId === pendingAction.exam.id
                    ? confirmationCopy.busyLabel
                    : confirmationCopy.confirmLabel}
                </button>
              </div>
            </section>
          </div>,
          document.body,
        )}
    </div>
  );
}

export function TeacherCreateExamPage({
  state,
  dispatch,
  teacherData,
  gateway,
}) {
  const selectedExamId = state?.staff?.selectedExamId || null;
  const editingExam = selectedExamId
    ? teacherData.exams.find((exam) => exam.id === selectedExamId)
    : null;
  const editing = Boolean(editingExam);

  const [title, setTitle] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [schemeId, setSchemeId] = useState("");
  const [componentId, setComponentId] = useState("");
  const [bankId, setBankId] = useState("");
  const [selectionMode, setSelectionMode] = useState("random");
  const [questionCount, setQuestionCount] = useState(20);
  const [durationMinutes, setDurationMinutes] = useState(45);
  const [instructions, setInstructions] = useState("");
  const [shuffleQuestions, setShuffleQuestions] = useState(true);
  const [shuffleOptions, setShuffleOptions] = useState(true);
  const [scheduledStartAt, setScheduledStartAt] = useState("");
  const [latestNormalStartAt, setLatestNormalStartAt] = useState("");
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

  const selectedSubject = teacherData.subjects.find(
    (subject) => subject.id === subjectId,
  );
  const selectedBank = subjectBanks.find((bank) => bank.id === bankId);
  const selectedComponent = components.find(
    (component) => component.id === componentId,
  );
  const selectedScheme = teacherData.assessmentSchemes.find(
    (scheme) => scheme.id === schemeId,
  );

  useEffect(() => {
    if (!editingExam) return;
    setTitle(editingExam.title || "");
    setSubjectId(editingExam.curriculumSubjectId || "");
    setSchemeId(editingExam.assessmentSchemeId || "");
    setComponentId(editingExam.assessmentComponentId || "");
    setBankId(editingExam.questionBankId || "");
    setSelectionMode(editingExam.selectionMode || "random");
    setQuestionCount(editingExam.questionCount || 1);
    setDurationMinutes(editingExam.durationMinutes || 45);
    setInstructions(editingExam.instructions || "");
    setShuffleQuestions(editingExam.shuffleQuestions !== false);
    setShuffleOptions(editingExam.shuffleOptions !== false);
    setScheduledStartAt(toDateTimeLocal(editingExam.scheduledStartAt));
    setLatestNormalStartAt(toDateTimeLocal(editingExam.latestNormalStartAt));
  }, [editingExam]);

  useEffect(() => {
    if (editingExam) return;
    if (!subjectId && teacherData.subjects[0]) {
      setSubjectId(teacherData.subjects[0].id);
    }
    if (!schemeId && teacherData.assessmentSchemes[0]) {
      setSchemeId(teacherData.assessmentSchemes[0].id);
    }
  }, [
    editingExam,
    schemeId,
    subjectId,
    teacherData.assessmentSchemes,
    teacherData.subjects,
  ]);

  useEffect(() => {
    if (editing) return;
    if (
      subjectBanks.length &&
      !subjectBanks.some((bank) => bank.id === bankId)
    ) {
      setBankId(subjectBanks[0].id);
    }
    if (!subjectBanks.length) setBankId("");
  }, [bankId, editing, subjectBanks]);

  useEffect(() => {
    if (
      components.length &&
      !components.some((component) => component.id === componentId)
    ) {
      setComponentId(components[0].id);
    }
    if (!components.length) setComponentId("");
  }, [componentId, components]);

  const activeBankQuestions = Number(
    selectedBank?.activeQuestionCount ?? selectedBank?.count ?? 0,
  );
  const capacityIssue =
    !editing &&
    selectionMode === "random" &&
    selectedBank &&
    Number(questionCount) > activeBankQuestions
      ? `This bank currently has only ${activeBankQuestions} active questions.`
      : "";

  const leaveForm = () =>
    dispatch({
      type: "staff",
      patch: { section: "exams", selectedExamId: null },
    });

  const saveExam = async (event) => {
    event.preventDefault();
    setError("");

    if (!teacherData.session?.id || !teacherData.term?.id) {
      setError(
        "The current academic session and term are not available on this CBT server.",
      );
      return;
    }
    if (!title.trim() || !subjectId || !schemeId || !componentId || !bankId) {
      setError("Complete the required exam fields before saving the draft.");
      return;
    }
    if (Number(questionCount) < 1 || Number(durationMinutes) < 1) {
      setError("Question count and duration must both be greater than zero.");
      return;
    }
    if (capacityIssue) {
      setError(capacityIssue);
      return;
    }
    if (
      scheduledStartAt &&
      latestNormalStartAt &&
      new Date(latestNormalStartAt).getTime() <
        new Date(scheduledStartAt).getTime()
    ) {
      setError(
        "Latest normal start cannot be earlier than the scheduled start.",
      );
      return;
    }

    setSaving(true);
    try {
      if (editing) {
        await gateway.exams.updateExam(editingExam.id, {
          expected_authoring_version: editingExam.authoringVersion || 1,
          assessment_scheme_id: schemeId,
          assessment_component_id: componentId,
          title: title.trim(),
          instructions: instructions.trim() || null,
          duration_minutes: Number(durationMinutes),
          shuffle_questions: shuffleQuestions,
          shuffle_options: shuffleOptions,
          scheduled_start_at: toIsoOrNull(scheduledStartAt),
          latest_normal_start_at: toIsoOrNull(latestNormalStartAt),
        });
      } else {
        await gateway.exams.createExam({
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
          shuffle_questions: shuffleQuestions,
          shuffle_options: shuffleOptions,
          scheduled_start_at: toIsoOrNull(scheduledStartAt),
          latest_normal_start_at: toIsoOrNull(latestNormalStartAt),
        });
      }

      await teacherData.refresh();
      leaveForm();
    } catch (requestError) {
      setError(
        requestError.userMessage ||
          `Weave could not ${editing ? "update" : "create"} this examination.`,
      );
    } finally {
      setSaving(false);
    }
  };

  const canSave = Boolean(
    teacherData.session?.id &&
      teacherData.term?.id &&
      teacherData.subjects.length &&
      teacherData.assessmentSchemes.length &&
      subjectBanks.length &&
      components.length,
  );

  if (selectedExamId && !editingExam && teacherData.loading) {
    return (
      <div className="teacher-exam-form-loading">Loading examination…</div>
    );
  }

  if (selectedExamId && !editingExam && !teacherData.loading) {
    return (
      <div className="teacher-reference-page teacher-exam-builder-page">
        <Notice tone="danger">
          This draft is no longer available to edit.
        </Notice>
        <button
          className="teacher-secondary-action"
          type="button"
          onClick={leaveForm}
        >
          Back to examinations
        </button>
      </div>
    );
  }

  return (
    <div className="teacher-reference-page teacher-exam-builder-page">
      <header className="teacher-exam-builder-header">
        <div>
          <button
            className="teacher-exam-back"
            type="button"
            onClick={leaveForm}
          >
            <Icon name="back" size={16} /> Back to exams
          </button>
          <div className="teacher-page-title-line">
            <span className="teacher-page-title-icon">
              <Icon name="calendar" size={27} />
            </span>
            <h1>{editing ? "Edit Examination" : "Create Examination"}</h1>
          </div>
          <p>
            {editing
              ? "Update the draft metadata and delivery settings without disturbing its question configuration."
              : "Create a clear, reviewable draft paper from the academic context synchronized from Weave."}
          </p>
        </div>

        <div className="teacher-exam-builder-header__actions">
          <button
            className="teacher-secondary-action"
            type="button"
            onClick={leaveForm}
            disabled={saving}
          >
            Cancel
          </button>
          <button
            className="teacher-primary-action"
            type="submit"
            form="teacher-exam-form"
            disabled={!canSave || saving}
          >
            <Icon name="check" size={17} />{" "}
            {saving
              ? "Saving…"
              : editing
                ? "Save changes"
                : "Create Draft Exam"}
          </button>
        </div>
      </header>

      {error && <Notice tone="danger">{error}</Notice>}
      {!canSave && !teacherData.loading && (
        <Notice tone="warning">
          A current session, term, assigned subject, assessment scheme/component,
          and matching question bank are required before a teacher can create an
          exam.
        </Notice>
      )}

      <form
        id="teacher-exam-form"
        className="teacher-exam-builder"
        onSubmit={saveExam}
      >
        <div className="teacher-exam-builder__main">
          <ExamSection
            number="01"
            title="Academic setup"
            description="Anchor the paper to the correct subject and assessment component."
          >
            <label className="teacher-exam-field teacher-exam-field--wide">
              <span>Exam title</span>
              <input
                aria-label="Exam title"
                value={title}
                maxLength={255}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="e.g. English Language CA 1"
              />
            </label>

            <FieldSelect
              label="Subject"
              helper={editing ? "Subject is fixed for this draft revision." : ""}
            >
              <SelectControl
                label="Subject"
                value={subjectId}
                options={teacherData.subjects.map((subject) => ({
                  value: subject.id,
                  label: subject.name,
                  description: subject.code || undefined,
                }))}
                onChange={setSubjectId}
                disabled={editing}
                placeholder="Choose a subject"
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
                placeholder="Choose a scheme"
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
                placeholder="Choose a component"
              />
            </FieldSelect>
          </ExamSection>

          <ExamSection
            number="02"
            title="Question setup"
            description={
              editing
                ? "Question configuration is protected here so manual selections are never cleared accidentally."
                : "Choose where the paper draws questions from and how the paper is assembled."
            }
          >
            <FieldSelect
              label="Question bank"
              helper={
                selectedBank
                  ? `${activeBankQuestions} active questions available`
                  : ""
              }
            >
              <SelectControl
                label="Question bank"
                value={bankId}
                options={subjectBanks.map((bank) => ({
                  value: bank.id,
                  label: bank.name,
                  description: `${
                    bank.activeQuestionCount ?? bank.count ?? 0
                  } active questions`,
                }))}
                onChange={setBankId}
                disabled={editing || !subjectBanks.length}
                placeholder="Choose a bank"
              />
            </FieldSelect>

            <label className="teacher-exam-field">
              <span>Number of questions</span>
              <input
                aria-label="Number of questions"
                type="number"
                min="1"
                value={questionCount}
                disabled={editing}
                onChange={(event) => setQuestionCount(event.target.value)}
              />
              {capacityIssue && (
                <small className="teacher-exam-field__error">
                  {capacityIssue}
                </small>
              )}
            </label>

            <fieldset
              className="teacher-exam-selection teacher-exam-field--wide"
              disabled={editing}
            >
              <legend>Question selection</legend>
              <div>
                <SelectionCard
                  value="random"
                  current={selectionMode}
                  onChange={setSelectionMode}
                  title="Random selection"
                  description="The server selects the configured number of active questions when the paper is sealed."
                />
                <SelectionCard
                  value="manual"
                  current={selectionMode}
                  onChange={setSelectionMode}
                  title="Manual selection"
                  description="Build the paper deliberately by choosing the exact questions after draft creation."
                />
              </div>
              {editing && (
                <small>
                  Question source changes are intentionally separated from
                  metadata editing to protect collaborative/manual selections.
                </small>
              )}
            </fieldset>
          </ExamSection>

          <ExamSection
            number="03"
            title="Delivery settings"
            description="Control timing, presentation order, and what students see before answering."
          >
            <label className="teacher-exam-field">
              <span>Duration</span>
              <div className="teacher-exam-input-suffix">
                <input
                  aria-label="Duration in minutes"
                  type="number"
                  min="1"
                  value={durationMinutes}
                  onChange={(event) => setDurationMinutes(event.target.value)}
                />
                <span>minutes</span>
              </div>
            </label>

            <div className="teacher-exam-field">
              <span>Presentation</span>
              <div className="teacher-exam-switches">
                <ToggleSwitch
                  checked={shuffleQuestions}
                  onChange={setShuffleQuestions}
                  label="Shuffle questions"
                />
                <ToggleSwitch
                  checked={shuffleOptions}
                  onChange={setShuffleOptions}
                  label="Shuffle answer options"
                />
              </div>
            </div>

            <label className="teacher-exam-field">
              <span>
                Scheduled start <small>(optional)</small>
              </span>
              <input
                aria-label="Scheduled start"
                type="datetime-local"
                value={scheduledStartAt}
                onChange={(event) => setScheduledStartAt(event.target.value)}
              />
              <small>
                Leave blank if administration will schedule it later.
              </small>
            </label>

            <label className="teacher-exam-field">
              <span>
                Latest normal start <small>(optional)</small>
              </span>
              <input
                aria-label="Latest normal start"
                type="datetime-local"
                value={latestNormalStartAt}
                min={scheduledStartAt || undefined}
                onChange={(event) =>
                  setLatestNormalStartAt(event.target.value)
                }
              />
              <small>
                Students starting after this point require the applicable
                makeup/late-start flow.
              </small>
            </label>

            <label className="teacher-exam-field teacher-exam-field--wide">
              <span>
                Student instructions <small>(optional)</small>
              </span>
              <textarea
                value={instructions}
                onChange={(event) => setInstructions(event.target.value)}
                placeholder="Write only the instructions students need for this paper."
              />
            </label>
          </ExamSection>
        </div>

        <aside
          className="teacher-exam-summary"
          aria-label="Draft examination summary"
        >
          <div className="teacher-exam-summary__header">
            <div>
              <span>Draft summary</span>
              <StatusBadge tone="warning">Draft</StatusBadge>
            </div>
            <p>Review the configuration before saving.</p>
          </div>

          <div className="teacher-exam-summary__title">
            <span>
              <Icon name="exam" size={20} />
            </span>
            <div>
              <strong>{title.trim() || "Untitled examination"}</strong>
              <small>
                {teacherData.session?.name || "No session"} ·{" "}
                {teacherData.term?.name || "No term"}
              </small>
            </div>
          </div>

          <SummaryRow
            label="Subject"
            value={selectedSubject?.name || "Not selected"}
          />
          <SummaryRow
            label="Assessment"
            value={selectedComponent?.name || "Not selected"}
            helper={selectedScheme?.name}
          />
          <SummaryRow
            label="Question bank"
            value={selectedBank?.name || "Not selected"}
            helper={
              selectedBank
                ? `${activeBankQuestions} active questions`
                : undefined
            }
          />
          <SummaryRow
            label="Paper"
            value={`${questionCount || 0} questions`}
            helper={formatSelectionMode(selectionMode)}
          />
          <SummaryRow
            label="Duration"
            value={`${durationMinutes || 0} minutes`}
            helper={`${
              shuffleQuestions ? "Questions shuffled" : "Fixed question order"
            } · ${
              shuffleOptions ? "Options shuffled" : "Fixed option order"
            }`}
          />
          <SummaryRow
            label="Schedule"
            value={
              scheduledStartAt
                ? formatDateTime(toIsoOrNull(scheduledStartAt))
                : "Not scheduled"
            }
            helper={
              latestNormalStartAt
                ? `Latest normal start: ${formatDateTime(
                    toIsoOrNull(latestNormalStartAt),
                  )}`
                : "Can be scheduled later"
            }
          />

          {selectedComponent && (
            <div className="teacher-exam-summary__score">
              <span>Academic component maximum</span>
              <strong>{selectedComponent.maximumScore}</strong>
            </div>
          )}
        </aside>
      </form>
    </div>
  );
}

function ExamSection({ number, title, description, children }) {
  return (
    <section className="teacher-exam-section">
      <div className="teacher-exam-section__heading">
        <span>{number}</span>
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
      </div>
      <div className="teacher-exam-section__grid">{children}</div>
    </section>
  );
}

function FieldSelect({ label, helper, children }) {
  return (
    <div className="teacher-exam-field">
      <span>{label}</span>
      {children}
      {helper && <small>{helper}</small>}
    </div>
  );
}

function SelectionCard({ value, current, onChange, title, description }) {
  return (
    <label
      className={`teacher-exam-selection-card ${
        current === value ? "is-selected" : ""
      }`}
    >
      <input
        type="radio"
        name="question-selection"
        value={value}
        checked={current === value}
        onChange={() => onChange(value)}
      />
      <span
        className="teacher-exam-selection-card__indicator"
        aria-hidden="true"
      />
      <span>
        <strong>{title}</strong>
        <small>{description}</small>
      </span>
    </label>
  );
}

function ToggleSwitch({ checked, onChange, label }) {
  return (
    <button
      type="button"
      className={`teacher-exam-switch ${checked ? "is-on" : ""}`}
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
    >
      <span className="teacher-exam-switch__track">
        <i />
      </span>
      <strong>{label}</strong>
    </button>
  );
}

function SummaryRow({ label, value, helper }) {
  return (
    <div className="teacher-exam-summary__row">
      <span>{label}</span>
      <div>
        <strong>{value}</strong>
        {helper && <small>{helper}</small>}
      </div>
    </div>
  );
}

function lifecycleMessage(status) {
  if (status === "draft") {
    return "This is a shared draft. Only its lead author can edit metadata, submit it for review, or delete it.";
  }
  if (status === "submitted") {
    return "This paper has been submitted for administrator review. Teacher authoring is now read-only.";
  }
  if (status === "sealed") {
    return "This paper is sealed. Operational lifecycle controls belong to school administration.";
  }
  if (status === "active" || status === "suspended") {
    return "This examination is in its live operational lifecycle. Teacher controls are handled through invigilation access, not paper authoring.";
  }
  if (status === "closed") {
    return "This examination is closed and preserved as academic evidence.";
  }
  if (status === "cancelled") {
    return "This examination revision was cancelled. Lifecycle recovery is an administrator operation.";
  }
  return "No teacher lifecycle action is available for this examination state.";
}

function getLifecycleConfirmation(action) {
  if (action === "delete") {
    return {
      title: "Delete this draft examination?",
      description: "This permanently removes the draft paper.",
      warning:
        "Deletion cannot be undone. If another author changed the draft since this page loaded, Weave will reject the request instead of deleting stale data.",
      confirmLabel: "Delete draft",
      busyLabel: "Deleting…",
    };
  }

  return {
    title: "Submit this examination for review?",
    description:
      "Teacher authoring will end and the paper will move to the submitted lifecycle state.",
    warning:
      "Weave validates the paper before submission. Incomplete manual selections, insufficient random-bank capacity, or stale authoring versions will be rejected safely.",
    confirmLabel: "Submit for review",
    busyLabel: "Submitting…",
  };
}

function getPopoverPosition(trigger) {
  const rect = trigger.getBoundingClientRect();
  const width = Math.min(
    POPOVER_WIDTH,
    window.innerWidth - VIEWPORT_GAP * 2,
  );
  const left = Math.max(
    VIEWPORT_GAP,
    Math.min(
      rect.right - width,
      window.innerWidth - width - VIEWPORT_GAP,
    ),
  );
  const below = window.innerHeight - rect.bottom - VIEWPORT_GAP;
  const above = rect.top - VIEWPORT_GAP;
  const placeAbove = below < 250 && above > below;
  const maxHeight = Math.max(
    190,
    Math.min(380, placeAbove ? above : below),
  );

  return placeAbove
    ? {
        width,
        left,
        maxHeight,
        bottom: window.innerHeight - rect.top + 8,
        top: "auto",
      }
    : {
        width,
        left,
        maxHeight,
        top: rect.bottom + 8,
        bottom: "auto",
      };
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
  return mode === "manual" ? "Manual selection" : "Random selection";
}

function formatDuration(minutes) {
  return `${minutes} min`;
}

function pluralize(value, noun) {
  return `${value} ${noun}${Number(value) === 1 ? "" : "s"}`;
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleDateString();
}

function formatShortDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : date.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
}

function formatTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : date.toLocaleTimeString(undefined, {
        hour: "numeric",
        minute: "2-digit",
      });
}

function formatDateTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString();
}

function toIsoOrNull(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function toDateTimeLocal(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const offset = date.getTimezoneOffset();
  return new Date(date.getTime() - offset * 60000)
    .toISOString()
    .slice(0, 16);
}

export const ExamsPage = TeacherExamsPage;
export const CreateExamPage = TeacherCreateExamPage;
