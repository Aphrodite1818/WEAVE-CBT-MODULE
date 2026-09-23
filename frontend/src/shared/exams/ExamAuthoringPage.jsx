import { examRevisionHistory, loadAllExams } from './examLineage'
import { useMemo, useState } from 'react'
import { RiCheckLine, RiCheckboxCircleFill, RiCheckboxBlankCircleLine } from '@remixicon/react'
import { buildAcademicLevels, findSubjectScope, humanizeAcademicCategory, listBanksForSubject, listSubjectsForLevel } from '../academics/authoringScope'
import { Icon } from '../icons/Icon'
import { Notice, SelectControl } from '../ui'
import { ExamFolder } from './ExamCard'
import { ExamDateTimePicker } from './ExamDateTimePicker'
import { ManualQuestionPicker } from './ManualQuestionPicker'
import { LeadAuthorControl } from './LeadAuthorControl'
import { canManageExam } from './examPermissions'
import './exam-workspace.css'

export function ExamAuthoringPage(props) {
  if (props.teacherData.loading && !props.teacherData.subjects.length) {
    return <div className="teacher-exam-form-loading">Loading examination context...</div>
  }
  return <ExamAuthoringForm key={props.state?.staff?.selectedExamId || 'new'} {...props} />
}

function ExamAuthoringForm({ state, dispatch, teacherData, gateway }) {
  const selectedExamId = state?.staff?.selectedExamId || null
  const editingExam = selectedExamId
    ? teacherData.exams.find((exam) => exam.id === selectedExamId)
    : null
  const editing = Boolean(editingExam)
  const actor = state.session?.actor
  const isAdmin = actor?.role === 'admin'
  const canManageConfiguration = !editing || canManageExam(editingExam, actor, teacherData.assignments)
  const readOnly = editing && !canManageConfiguration
  const isEligibleTeacherContributor = Boolean(
    editing &&
    editingExam?.status === 'draft' &&
    actor?.role === 'teacher' &&
    teacherData.assignments.some((assignment) => assignment.curriculumSubjectId === editingExam.curriculumSubjectId),
  )
  const initialSubject = editing
    ? findSubjectScope(teacherData.subjects, editingExam?.curriculumSubjectId)
    : null
  const initialSchemeId = editingExam?.assessmentSchemeId || teacherData.assessmentSchemes[0]?.id || ''

  const [leadTeacherId, setLeadTeacherId] = useState(editingExam?.leadTeacherId || '')
  const [leadTeacherName, setLeadTeacherName] = useState(
    isAdmin
      ? editingExam?.leadTeacherId ? 'Assigned teacher' : 'Administrator'
      : actor?.display_name || 'You',
  )
  const [folderColor, setFolderColor] = useState(editingExam?.folderColor || '#8190a5')
  const [leadSaving, setLeadSaving] = useState(false)
  const [leadMessage, setLeadMessage] = useState('')
  const [title, setTitle] = useState(editingExam?.title || '')
  const [levelId, setLevelId] = useState(editing ? initialSubject?.academicLevelId || '' : '')
  const [subjectId, setSubjectId] = useState(editing ? initialSubject?.id || '' : '')
  const [schemeId, setSchemeId] = useState(initialSchemeId)
  const [componentId, setComponentId] = useState(editing ? editingExam?.assessmentComponentId || '' : '')
  const [bankId, setBankId] = useState(editing ? editingExam?.questionBankId || '' : '')
  const [selectionMode, setSelectionMode] = useState(editingExam?.selectionMode || 'random')
  const [questionCount, setQuestionCount] = useState(editingExam?.questionCount || 20)
  const [durationMinutes, setDurationMinutes] = useState(editingExam?.durationMinutes || 45)
  const [instructions, setInstructions] = useState(editingExam?.instructions || '')
  const [shuffleQuestions, setShuffleQuestions] = useState(editingExam?.shuffleQuestions !== false)
  const [shuffleOptions, setShuffleOptions] = useState(editingExam?.shuffleOptions !== false)
  const [scheduledStartAt, setScheduledStartAt] = useState(toDateTimeLocal(editingExam?.scheduledStartAt))
  const [latestNormalStartAt, setLatestNormalStartAt] = useState(toDateTimeLocal(editingExam?.latestNormalStartAt))
  const [manualSelection, setManualSelection] = useState({ bankId: '', ids: [] })
  const manualQuestionIds = manualSelection.bankId === bankId ? manualSelection.ids : []
  const [questionSaving, setQuestionSaving] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [duplicateScope, setDuplicateScope] = useState(null)
  const currentScope = { termId: teacherData.term?.id, curriculumSubjectId: subjectId, assessmentComponentId: componentId }
  const hasChosenAssessmentScope = Boolean(!editing && currentScope.termId && subjectId && componentId)
  const existingScopeExam = hasChosenAssessmentScope ? teacherData.exams.find((exam) =>
    exam.termId === currentScope.termId && exam.curriculumSubjectId === subjectId && exam.assessmentComponentId === componentId,
  ) : null
  const existingExam = existingScopeExam ? examRevisionHistory(teacherData.exams, existingScopeExam)[0] : null
  const recoveryExamId = hasChosenAssessmentScope ? existingExam?.id || (
    duplicateScope?.termId === currentScope.termId && duplicateScope?.curriculumSubjectId === subjectId && duplicateScope?.assessmentComponentId === componentId
      ? duplicateScope.id : null
  ) : null
  const openExam = (id) => dispatch({ type: 'staff', patch: { section: 'exam-history', selectedExamId: id, examAuthoringNotice: '' } })

  const levels = useMemo(() => buildAcademicLevels(teacherData.subjects), [teacherData.subjects])
  const subjectsForLevel = useMemo(
    () => listSubjectsForLevel(teacherData.subjects, levelId),
    [levelId, teacherData.subjects],
  )
  const subjectBanks = useMemo(
    () => listBanksForSubject(teacherData.banks, subjectId),
    [subjectId, teacherData.banks],
  )
  const components = useMemo(
    () => teacherData.assessmentComponents.filter((component) => component.schemeId === schemeId),
    [schemeId, teacherData.assessmentComponents],
  )

  const selectedLevel = levels.find((level) => level.id === levelId)
  const selectedSubject = findSubjectScope(teacherData.subjects, subjectId)
  const selectedBank = subjectBanks.find((bank) => bank.id === bankId)
  const selectedComponent = components.find((component) => component.id === componentId)
  const questionConfigurationChanged = Boolean(
    editing && (
      bankId !== editingExam.questionBankId ||
      selectionMode !== editingExam.selectionMode ||
      Number(questionCount) !== Number(editingExam.questionCount)
    ),
  )
  const persistedManualDraft = Boolean(editing && editingExam.status === 'draft' && editingExam.selectionMode === 'manual')
  const canManageManualSelections = Boolean(
    !editing || (persistedManualDraft && (canManageConfiguration || isEligibleTeacherContributor)),
  )
  const showManualPicker = Boolean(
    selectionMode === 'manual' &&
    bankId &&
    (!editing || (editingExam.selectionMode === 'manual' && bankId === editingExam.questionBankId)),
  )

  const activeBankQuestions = Number(selectedBank?.activeQuestionCount ?? selectedBank?.count ?? 0)
  const capacityIssue =
    selectionMode === 'random' &&
    selectedBank &&
    (!editing || questionConfigurationChanged) &&
    Number(questionCount) > activeBankQuestions
      ? `This bank currently has only ${activeBankQuestions} active questions.`
      : ''

  const resetLead = () => {
    setLeadTeacherId('')
    setLeadTeacherName('Administrator')
  }

  const resetDuplicateRecovery = () => {
    setDuplicateScope(null)
    setError('')
  }

  const changeLevel = (nextLevelId) => {
    setLevelId(nextLevelId)
    setSubjectId('')
    setBankId('')
    resetLead()
    setManualSelection({ bankId: '', ids: [] })
    resetDuplicateRecovery()
  }

  const changeSubject = (nextSubjectId) => {
    setSubjectId(nextSubjectId)
    setBankId('')
    resetLead()
    setManualSelection({ bankId: '', ids: [] })
    resetDuplicateRecovery()
  }

  const changeScheme = (nextSchemeId) => {
    setSchemeId(nextSchemeId)
    setComponentId('')
    resetDuplicateRecovery()
  }

  const changeComponent = (nextComponentId) => {
    setComponentId(nextComponentId)
    resetDuplicateRecovery()
  }

  const leaveForm = () => dispatch({
    type: 'staff',
    patch: { section: 'exams', selectedExamId: null, examAuthoringNotice: '' },
  })

  const saveExam = async (event) => {
    event.preventDefault()
    if (readOnly || saving || leadSaving || questionSaving) return
    setError('')

    if (!editing && recoveryExamId) {
      setError('Exam already exists for this assessment scope.')
      return
    }
    if (!teacherData.session?.id || !teacherData.term?.id) {
      setError('The current academic session and term are not available on this CBT server.')
      return
    }
    if (!levelId || !selectedSubject || selectedSubject.academicLevelId !== levelId) {
      setError('Choose an academic level and a subject from that level before saving the draft.')
      return
    }
    if (!title.trim() || !subjectId || !schemeId || !componentId || !bankId) {
      setError('Complete the required exam fields before saving the draft.')
      return
    }
    if (!selectedBank || selectedBank.curriculumSubjectId !== subjectId) {
      setError('Choose a question bank that belongs to the selected level and subject.')
      return
    }
    if (!Number.isInteger(Number(questionCount)) || !Number.isInteger(Number(durationMinutes)) || Number(questionCount) < 1 || Number(durationMinutes) < 1) {
      setError('Question count and duration must both be greater than zero.')
      return
    }
    if (!editing && selectionMode === 'manual' && manualQuestionIds.length > Number(questionCount)) {
      setError('Remove extra manual selections or increase the number of questions.')
      return
    }
    if (capacityIssue) {
      setError(capacityIssue)
      return
    }
    if ([scheduledStartAt, latestNormalStartAt].some((value) => value && !toIsoOrNull(value))) {
      setError('Choose a valid date and time for the examination schedule.')
      return
    }
    if (
      scheduledStartAt &&
      latestNormalStartAt &&
      new Date(latestNormalStartAt).getTime() < new Date(scheduledStartAt).getTime()
    ) {
      setError('Latest normal start cannot be earlier than the scheduled start.')
      return
    }

    setSaving(true)
    try {
      if (editing) {
        let clearExistingManualSelections = false
        if (questionConfigurationChanged && editingExam.selectionMode === 'manual') {
          const selections = await gateway.exams.listManualQuestions(editingExam.id)
          if (
            selectionMode === 'manual' &&
            bankId === editingExam.questionBankId &&
            Number(questionCount) < selections.length
          ) {
            setError(`Question count cannot be lower than the ${selections.length} questions already selected for this paper.`)
            return
          }

          const changingToRandom = selectionMode === 'random'
          const changingBank = bankId !== editingExam.questionBankId
          if ((changingToRandom || changingBank) && selections.length) {
            const warning = buildDestructiveQuestionConfigurationWarning({
              selections,
              changingToRandom,
              changingBank,
            })
            const confirmed = typeof window !== 'undefined' && window.confirm(warning)
            if (!confirmed) return
            clearExistingManualSelections = true
          }
        }

        const updatedExam = await gateway.exams.updateExam(editingExam.id, {
          expected_authoring_version: editingExam.authoringVersion || 1,
          assessment_scheme_id: schemeId,
          assessment_component_id: componentId,
          title: title.trim(),
          instructions: instructions.trim() || null,
          folder_color: folderColor,
          duration_minutes: Number(durationMinutes),
          shuffle_questions: shuffleQuestions,
          shuffle_options: shuffleOptions,
          scheduled_start_at: toIsoOrNull(scheduledStartAt),
          latest_normal_start_at: toIsoOrNull(latestNormalStartAt),
        })

        if (questionConfigurationChanged) {
          await gateway.exams.configureExamQuestions(editingExam.id, {
            question_bank_id: bankId,
            question_selection_mode: selectionMode,
            question_count: Number(questionCount),
            clear_existing_manual_selections: clearExistingManualSelections,
            expected_authoring_version: updatedExam.authoring_version ?? updatedExam.authoringVersion ?? (editingExam.authoringVersion || 1),
          })
        }
      } else {
        const createdExam = await gateway.exams.createExam({
          ...(isAdmin ? { lead_teacher_id: leadTeacherId || null } : {}),
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
          folder_color: folderColor,
          duration_minutes: Number(durationMinutes),
          shuffle_questions: shuffleQuestions,
          shuffle_options: shuffleOptions,
          scheduled_start_at: toIsoOrNull(scheduledStartAt),
          latest_normal_start_at: toIsoOrNull(latestNormalStartAt),
        })
        if (selectionMode === 'manual' && manualQuestionIds.length) {
          try {
            await gateway.exams.addManualQuestions(createdExam.id, manualQuestionIds, createdExam.authoring_version)
          } catch (selectionError) {
            // Creation committed separately. Continue on that draft so retrying cannot create a duplicate.
            try {
              await teacherData.refresh()
            } finally {
              dispatch({ type: 'staff', patch: {
                section: 'create-exam', selectedExamId: createdExam.id,
                examAuthoringNotice: `The draft was created, but its questions could not be added. ${selectionError.userMessage || 'Choose the questions again below.'}`,
              } })
            }
            return
          }
        }
      }

      await teacherData.refresh()
      leaveForm()
    } catch (requestError) {
      setError(requestError.userMessage || `Weave could not ${editing ? 'update' : 'create'} this examination.`)
      if (editing) {
        try {
          await teacherData.refresh()
        } catch {
          // Keep the mutation error visible even if the surrounding refresh fails.
        }
      }
      if (!editing && requestError.status === 409) {
        // A concurrent creator may have committed after this form loaded.
        try {
          const payload = await loadAllExams(gateway.exams, {
            term_id: currentScope.termId, curriculum_subject_id: subjectId, assessment_component_id: componentId,
          })
          const latest = payload.exams.reduce((current, exam) => !current || exam.revision_number > current.revision_number ? exam : current, null)
          if (latest) {
            setDuplicateScope({ ...currentScope, id: latest.id })
            setError('Exam already exists for this assessment scope.')
            await teacherData.refresh()
          }
        } catch {
          // Keep the original creation error if recovery data is unavailable.
        }
      }
    } finally {
      setSaving(false)
    }
  }

  const hasAuthoringContext = Boolean(
    teacherData.session?.id &&
    teacherData.term?.id &&
    levels.length &&
    teacherData.assessmentSchemes.length,
  )
  const canSave = Boolean(
    hasAuthoringContext &&
      levelId &&
      selectedSubject?.academicLevelId === levelId &&
      schemeId &&
      componentId &&
      components.some((component) => component.id === componentId) &&
      bankId &&
      selectedBank?.curriculumSubjectId === subjectId,
  )

  if (selectedExamId && !editingExam && teacherData.loading) {
    return <div className="teacher-exam-form-loading">Loading examination…</div>
  }

  if (selectedExamId && !editingExam && !teacherData.loading) {
    return (
      <div className="teacher-reference-page teacher-exam-builder-page">
        <Notice tone="danger">This draft is no longer available to edit.</Notice>
        <button className="teacher-secondary-action" type="button" onClick={leaveForm}>
          Back to examinations
        </button>
      </div>
    )
  }

  const manualContributor = Boolean(readOnly && isEligibleTeacherContributor && editingExam?.selectionMode === 'manual')
  const randomViewer = Boolean(readOnly && isEligibleTeacherContributor && editingExam?.selectionMode === 'random')
  const leadName = isAdmin
    ? leadTeacherName
    : readOnly
      ? editingExam?.leadTeacherId ? 'Assigned lead teacher' : 'Administrator'
      : actor?.display_name || 'You'
  const readiness = [
    ['Exam title added', Boolean(title.trim())],
    ['Academic context', Boolean(levelId && subjectId && schemeId && componentId && teacherData.session?.id && teacherData.term?.id)],
    ['Question source', Boolean(bankId && Number(questionCount) > 0 && !capacityIssue)],
    ['Settings configured', Number(durationMinutes) > 0],
  ]

  const saveLead = async () => {
    setLeadSaving(true)
    setError('')
    setLeadMessage('')
    try {
      await gateway.exams.assignExamLead(editingExam.id, leadTeacherId, editingExam.authoringVersion)
      await teacherData.refresh()
      setLeadMessage('Lead author updated.')
    } catch (requestError) {
      setError(requestError.userMessage || 'The lead author could not be updated.')
    } finally {
      setLeadSaving(false)
    }
  }

  return (
    <div className="teacher-reference-page teacher-exam-builder-page exam-authoring-page">
      <header className="teacher-exam-builder-header">
        <div>
          <div className="teacher-page-title-line">
            <span className="teacher-page-title-icon"><Icon name="exam" size={28} /></span>
            <h1>{readOnly ? 'Examination details' : editing ? 'Edit Examination' : 'Create Examination'}</h1>
          </div>
          <p>{manualContributor
            ? 'Review the lead-managed settings and contribute questions to this manual paper.'
            : randomViewer
              ? 'Review the lead-managed settings. Random question selection has no manual contribution step.'
              : readOnly
                ? 'Review the paper and its current examination settings.'
                : 'Set up the paper, choose a question source and configure delivery.'}</p>
        </div>
        <div className="teacher-exam-builder-header__actions">
          <button className="teacher-primary-action" type="button" onClick={leaveForm} disabled={saving || leadSaving || questionSaving}>
            <Icon name="back" size={17} /> Back to Examinations
          </button>
        </div>
      </header>

      {state.staff?.examAuthoringNotice && <Notice tone="warning">{state.staff.examAuthoringNotice}</Notice>}
      {error && <Notice tone="danger">{error}</Notice>}
      {!editing && recoveryExamId && (
        <div className="exam-authoring-recovery" role="status">
          <p>Exam already exists for this assessment scope.</p>
          <button type="button" className="teacher-secondary-action" disabled={saving} onClick={() => openExam(recoveryExamId)}>Open Existing Examination</button>
        </div>
      )}
      {editing && <button type="button" className="teacher-secondary-action" disabled={saving || leadSaving || questionSaving} onClick={() => openExam(editingExam.id)}>View revision history</button>}
      {teacherData.error && <Notice tone="danger">{teacherData.error}</Notice>}
      {teacherData.warning && <Notice tone="warning">{teacherData.warning}</Notice>}
      {!hasAuthoringContext && !teacherData.loading && !readOnly && (
        <Notice tone="warning">A current session, term, academic level and assessment scheme are required to author an exam.</Notice>
      )}
      {readOnly && <Notice>{manualContributor
        ? 'This draft is coordinated by its lead author. You can add questions to this manual paper and remove questions you contributed, but paper configuration remains read-only.'
        : randomViewer
          ? 'This draft is coordinated by its lead author. Because it uses random question selection, there are no individual questions for contributors to add, so this paper is view-only for you.'
          : `This paper is ${editingExam.statusLabel.toLowerCase()}. Draft metadata can only be edited by its lead author or an administrator.`}</Notice>}

      <form id="exam-authoring-form" className="teacher-exam-builder" onSubmit={saveExam}>
        <fieldset className="teacher-exam-builder__main" disabled={saving || leadSaving || questionSaving}>
          <ExamSection number="1" title="Paper details" description="Name the paper and choose its academic context." kind="paper">
            <label className="teacher-exam-field teacher-exam-field--wide">
              <span>Exam title <em>*</em></span>
              <input aria-label="Exam title" required value={title} maxLength={255} disabled={readOnly} onChange={(event) => setTitle(event.target.value)} placeholder="e.g. Computer Studies CA2" />
            </label>
            <FieldSelect label="Academic level *" >
              <SelectControl
                label="Academic level"
                value={levelId}
                options={levels.map((level) => ({ value: level.id, label: level.name, description: humanizeAcademicCategory(level.category) || undefined }))}
                onChange={changeLevel}
                disabled={editing || readOnly}
                placeholder="Choose level"
              />
            </FieldSelect>
            <FieldSelect label="Subject *">
              <SelectControl
                label="Subject"
                value={subjectId}
                options={subjectsForLevel.map((subject) => ({ value: subject.id, label: subject.name, description: subject.code || undefined }))}
                onChange={changeSubject}
                disabled={editing || readOnly || !levelId || !subjectsForLevel.length}
                placeholder={levelId ? 'Choose subject' : 'Choose a level first'}
              />
            </FieldSelect>
            <FieldSelect label="Assessment scheme *">
              <SelectControl
                label="Assessment scheme"
                value={schemeId}
                options={teacherData.assessmentSchemes.map((scheme) => ({ value: scheme.id, label: scheme.name }))}
                onChange={changeScheme}
                disabled={readOnly}
                placeholder="Choose scheme"
              />
            </FieldSelect>
            <FieldSelect label="Assessment component *">
              <SelectControl
                label="Assessment component"
                value={componentId}
                options={components.map((component) => ({ value: component.id, label: component.name, description: `${component.maximumScore} marks` }))}
                onChange={changeComponent}
                disabled={readOnly || !components.length}
                placeholder={schemeId ? 'Choose component' : 'Choose a scheme first'}
              />
            </FieldSelect>
            <div className="exam-paper-options">
            <div className="exam-paper-options__lead">
            {isAdmin ? (
              <LeadAuthorControl
                key={`${subjectId}:${editingExam?.termId || teacherData.term?.id}`}
                gateway={gateway}
                subjectId={subjectId}
                termId={editingExam?.termId || teacherData.term?.id}
                value={leadTeacherId}
                onChange={setLeadTeacherId}
                onResolvedName={setLeadTeacherName}
                disabled={readOnly}
              />
            ) : (
              <div className="exam-lead-identity">
                <span>{(leadName || 'L').slice(0, 1)}</span>
                <div><small>Lead author</small><strong>{leadName}</strong></div>
              </div>
            )}
            <div className="exam-ownership-status">
              {editing && isAdmin && !readOnly && (
                <button type="button" className="exam-text-action" onClick={saveLead} disabled={leadSaving || leadTeacherId === (editingExam.leadTeacherId || '')}>
                  {leadSaving ? 'Updating...' : 'Update lead'}
                </button>
              )}
              {leadMessage && <Notice tone="success">{leadMessage}</Notice>}
            </div>
            </div>
            <div className="exam-paper-options__colour">
            <span className="exam-option-label">Folder colour</span>
            <div className="exam-palette" role="group" aria-label="Folder colour">
              {FOLDER_COLORS.map(([name, color]) => (
                <button key={name} type="button" title={name} aria-label={`${name} folder`} aria-pressed={folderColor === color} disabled={readOnly} style={{ '--swatch': color }} onClick={() => setFolderColor(color)}>
                  {folderColor === color && <RiCheckLine size={18} />}
                </button>
              ))}
            </div>
            </div>
            </div>
          </ExamSection>

          <ExamSection number="2" title="Questions & delivery" description="Choose your question source and how students take the paper." kind="questions">
            <FieldSelect label="Question bank *">
              <SelectControl label="Question bank" value={bankId} options={subjectBanks.map((bank) => ({ value: bank.id, label: bank.name, description: `${bank.activeQuestionCount ?? bank.count ?? 0} active questions` }))} onChange={(value) => { setBankId(value); setManualSelection({ bankId: value, ids: [] }); setError('') }} disabled={!subjectBanks.length || readOnly} placeholder={subjectId ? 'Choose bank' : 'Choose a subject first'} />
            </FieldSelect>
            <label className="teacher-exam-field">
              <span>Number of questions <em>*</em></span>
              <input aria-label="Number of questions" type="number" min="1" required value={questionCount} disabled={readOnly} onChange={(event) => setQuestionCount(event.target.value)} />
              <small>{questionCount || 0} required &middot; <b>{activeBankQuestions} available</b></small>
              {capacityIssue && <small className="teacher-exam-field__error">{capacityIssue}</small>}
            </label>
            <fieldset className="teacher-exam-selection" disabled={readOnly}>
              <legend>Question selection method</legend>
              <div>
                <SelectionCard value="random" current={selectionMode} onChange={setSelectionMode} title="Random selection" description="Select from the bank." />
                <SelectionCard value="manual" current={selectionMode} onChange={setSelectionMode} title="Manual selection" description="Choose specific questions." />
              </div>
            </fieldset>
            {showManualPicker && (
              <ManualQuestionPicker
                key={`${selectedExamId || 'new'}:${bankId}`}
                bankId={bankId}
                exam={editingExam ? { ...editingExam, questionCount: Number(questionCount) } : { questionCount }}
                gateway={gateway}
                selectedIds={manualQuestionIds}
                onChange={(ids) => setManualSelection({ bankId, ids })}
                disabled={!canManageManualSelections || questionConfigurationChanged || saving || leadSaving || questionSaving}
                actorId={actor?.id}
                canManageAllSelections={canManageConfiguration}
                onBusyChange={setQuestionSaving}
                onSaved={teacherData.refresh}
              />
            )}
            {editing && <p className="exam-section-note">{readOnly
              ? manualContributor
                ? 'Paper settings are lead-managed. You can contribute questions below; your question changes save immediately.'
                : 'Paper settings are lead-managed. Random selection has no manual question contribution step.'
              : questionConfigurationChanged
                ? 'Save the question configuration before making manual selection changes.'
                : 'The academic level and subject stay fixed; the lead author or administrator may still update the bank, question count and selection method while this revision is a draft.'}</p>}
            <div className="exam-delivery-options">
            <label className="teacher-exam-field">
              <span>Duration <em>*</em></span>
              <div className="teacher-exam-input-suffix">
                <input aria-label="Duration in minutes" type="number" min="1" required value={durationMinutes} disabled={readOnly} onChange={(event) => setDurationMinutes(event.target.value)} />
                <span>minutes</span>
              </div>
            </label>
            <ToggleSwitch checked={shuffleQuestions} onChange={setShuffleQuestions} label="Shuffle questions" disabled={readOnly} />
            <ToggleSwitch checked={shuffleOptions} onChange={setShuffleOptions} label="Shuffle answer options" disabled={readOnly} />
            </div>
          </ExamSection>

          <ExamSection number="3" title="Schedule & instructions" description="Optional. Add now or return to these before the exam." kind="schedule">
            <ExamDateTimePicker label="Scheduled start" value={scheduledStartAt} onChange={setScheduledStartAt} disabled={readOnly || saving || leadSaving || questionSaving} />
            <ExamDateTimePicker label="Latest normal start" value={latestNormalStartAt} min={scheduledStartAt} onChange={setLatestNormalStartAt} disabled={readOnly || saving || leadSaving || questionSaving} />
            <label className="teacher-exam-field teacher-exam-field--wide">
              <span>Student instructions <small>(optional)</small></span>
              <textarea aria-label="Student instructions" rows="3" value={instructions} disabled={readOnly} onChange={(event) => setInstructions(event.target.value)} placeholder="Instructions students will see before they start." />
            </label>
          </ExamSection>
          {!readOnly && (
            <footer className="exam-authoring-actions">
              <button className="teacher-secondary-action" type="button" onClick={leaveForm} disabled={saving || leadSaving || questionSaving}>Cancel</button>
              <button className="teacher-primary-action" type="submit" disabled={!canSave || saving || leadSaving || questionSaving}>
                <Icon name="plus" size={17} />
                {saving ? 'Saving...' : editing ? 'Save changes' : 'Create Draft Exam'}
              </button>
            </footer>
          )}
        </fieldset>

        <aside className="exam-summary" aria-label="Draft examination summary">
          <header><Icon name="exam" size={19} /><div><h2>Exam summary</h2><p>Live preview of your examination.</p></div></header>
          <div className="exam-summary__preview"><ExamFolder color={folderColor} size={54} /><span className={`exam-status exam-status--${editingExam?.status || 'draft'}`}>{editingExam?.statusLabel || 'Draft'}</span></div>
          <h3>{title.trim() || 'Untitled examination'}</h3>
          <p className="exam-summary__context">{selectedLevel?.name || 'Choose level'} &middot; {selectedSubject?.name || 'Choose subject'} &middot; {selectedComponent?.name || 'Choose component'}</p>
          <SummaryRow label="Lead author" value={leadName} />
          <SummaryRow label="Questions" value={`${questionCount || 0} questions`} helper={selectedBank?.name} />
          <SummaryRow label="Duration" value={`${durationMinutes || 0} minutes`} />
          <SummaryRow label="Schedule" value={scheduledStartAt ? formatDateTime(toIsoOrNull(scheduledStartAt)) : 'Not scheduled'} helper={latestNormalStartAt ? `Latest start: ${formatDateTime(toIsoOrNull(latestNormalStartAt))}` : 'Can be set later'} />
          {!readOnly && (
            <div className="exam-readiness">
              <h3>Draft readiness</h3><p>Required to save your draft.</p>
              <ul>
                {readiness.map(([label, ready]) => (
                  <li key={label} className={ready ? 'is-ready' : ''}>
                    {ready ? <RiCheckboxCircleFill size={17} /> : <RiCheckboxBlankCircleLine size={17} />}
                    <span>{label}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </aside>

      </form>
    </div>
  )
}

const FOLDER_COLORS = [
  ['Rose', '#cf4564'],
  ['Blue', '#397fd6'],
  ['Green', '#279b70'],
  ['Amber', '#b77915'],
  ['Purple', '#8855cd'],
  ['Magenta', '#b942a5'],
  ['Teal', '#148e96'],
  ['Slate', '#8190a5'],
]

function ExamSection({ number, title, description, children, kind }) {
  return (
    <section className={`teacher-exam-section exam-section--${kind}`}>
      <div className="teacher-exam-section__heading">
        <span>{number}</span>
        <div><h2>{title}</h2><p>{description}</p></div>
      </div>
      <div className="teacher-exam-section__grid">{children}</div>
    </section>
  )
}

function FieldSelect({ label, helper, children }) {
  return (
    <div className="teacher-exam-field">
      <span>{label}</span>
      {children}
      {helper && <small>{helper}</small>}
    </div>
  )
}

function SelectionCard({ value, current, onChange, title, description }) {
  return (
    <label className={`teacher-exam-selection-card ${current === value ? 'is-selected' : ''}`}>
      <input type="radio" name="question-selection" value={value} checked={current === value} onChange={() => onChange(value)} />
      <span className="teacher-exam-selection-card__indicator" aria-hidden="true" />
      <span><strong>{title}</strong><small>{description}</small></span>
    </label>
  )
}

function ToggleSwitch({ checked, onChange, label, disabled = false }) {
  return (
    <button type="button" className={`teacher-exam-switch ${checked ? 'is-on' : ''}`} role="switch" aria-checked={checked} disabled={disabled} onClick={() => onChange(!checked)}>
      <span className="teacher-exam-switch__track"><i /></span>
      <strong>{label}</strong>
    </button>
  )
}

function SummaryRow({ label, value, helper }) {
  return (
    <div className="teacher-exam-summary__row">
      <span>{label}</span>
      <div><strong>{value}</strong>{helper && <small>{helper}</small>}</div>
    </div>
  )
}

export function buildDestructiveQuestionConfigurationWarning({ selections = [], changingToRandom = false, changingBank = false }) {
  const questionCount = selections.length
  const contributorCount = new Set(
    selections
      .map((selection) => selection.added_by_actor_id)
      .filter(Boolean)
      .map(String),
  ).size
  const questionText = `${questionCount} manually selected question${questionCount === 1 ? '' : 's'}`
  const contributorText = contributorCount
    ? ` from ${contributorCount} contributor${contributorCount === 1 ? '' : 's'}`
    : ''

  if (changingToRandom) {
    return [
      'Switch to Random Selection?',
      '',
      `${questionText}${contributorText} will be removed from this draft.`,
      '',
      'The questions themselves will remain in the question bank, but their selection for this examination cannot be restored automatically.',
      '',
      'Continue?',
    ].join('\n')
  }

  if (changingBank) {
    return [
      'Change Question Bank?',
      '',
      `${questionText}${contributorText} will be removed from this draft because they belong to the current question bank.`,
      '',
      'The questions themselves will remain in the question bank, but their selection for this examination cannot be restored automatically.',
      '',
      'Continue?',
    ].join('\n')
  }

  return ''
}

function formatDateTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString()
}

function toIsoOrNull(value) {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date.toISOString()
}

function toDateTimeLocal(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const offset = date.getTimezoneOffset()
  return new Date(date.getTime() - offset * 60000).toISOString().slice(0, 16)
}