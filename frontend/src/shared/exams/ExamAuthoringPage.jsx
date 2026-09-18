import { useMemo, useState } from 'react'
import { RiCheckLine, RiCheckboxCircleFill, RiCheckboxBlankCircleLine, RiInformationLine } from '@remixicon/react'
import { Icon } from '../icons/Icon'
import { Notice, SelectControl, StatusBadge } from '../ui'
import { ExamFolder } from './ExamCard'
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
  const readOnly = editing && !canManageExam(editingExam, actor, teacherData.assignments)

  const [leadTeacherId, setLeadTeacherId] = useState(editingExam?.leadTeacherId || '')
  const [leadTeacherName, setLeadTeacherName] = useState(
    isAdmin
      ? editingExam?.leadTeacherId ? 'Assigned teacher' : 'Administrator'
      : actor?.display_name || 'You',
  )
  const [folderColor, setFolderColor] = useState('#8190a5')
  const [leadSaving, setLeadSaving] = useState(false)
  const [leadMessage, setLeadMessage] = useState('')
  const [title, setTitle] = useState(editingExam?.title || '')
  const [subjectId, setSubjectId] = useState(editingExam?.curriculumSubjectId || teacherData.subjects[0]?.id || '')
  const [schemeId, setSchemeId] = useState(editingExam?.assessmentSchemeId || teacherData.assessmentSchemes[0]?.id || '')
  const [componentId, setComponentId] = useState(editingExam?.assessmentComponentId || teacherData.assessmentComponents.find((item) => item.schemeId === schemeId)?.id || '')
  const [bankId, setBankId] = useState(editingExam?.questionBankId || teacherData.banks.find((item) => item.curriculumSubjectId === subjectId)?.id || '')
  const [selectionMode, setSelectionMode] = useState(editingExam?.selectionMode || 'random')
  const [questionCount, setQuestionCount] = useState(editingExam?.questionCount || 20)
  const [durationMinutes, setDurationMinutes] = useState(editingExam?.durationMinutes || 45)
  const [instructions, setInstructions] = useState(editingExam?.instructions || '')
  const [shuffleQuestions, setShuffleQuestions] = useState(editingExam?.shuffleQuestions !== false)
  const [shuffleOptions, setShuffleOptions] = useState(editingExam?.shuffleOptions !== false)
  const [scheduledStartAt, setScheduledStartAt] = useState(toDateTimeLocal(editingExam?.scheduledStartAt))
  const [latestNormalStartAt, setLatestNormalStartAt] = useState(toDateTimeLocal(editingExam?.latestNormalStartAt))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const subjectBanks = useMemo(
    () => teacherData.banks.filter((bank) => !subjectId || bank.curriculumSubjectId === subjectId),
    [subjectId, teacherData.banks],
  )
  const components = useMemo(
    () => teacherData.assessmentComponents.filter((component) => component.schemeId === schemeId),
    [schemeId, teacherData.assessmentComponents],
  )

  const selectedSubject = teacherData.subjects.find((subject) => subject.id === subjectId)
  const selectedBank = subjectBanks.find((bank) => bank.id === bankId)
  const selectedComponent = components.find((component) => component.id === componentId)

  const activeBankQuestions = Number(selectedBank?.activeQuestionCount ?? selectedBank?.count ?? 0)
  const capacityIssue =
    !editing &&
    selectionMode === 'random' &&
    selectedBank &&
    Number(questionCount) > activeBankQuestions
      ? `This bank currently has only ${activeBankQuestions} active questions.`
      : ''

  const leaveForm = () => dispatch({
    type: 'staff',
    patch: { section: 'exams', selectedExamId: null },
  })

  const saveExam = async (event) => {
    event.preventDefault()
    if (readOnly || saving || leadSaving) return
    setError('')

    if (!teacherData.session?.id || !teacherData.term?.id) {
      setError('The current academic session and term are not available on this CBT server.')
      return
    }
    if (!title.trim() || !subjectId || !schemeId || !componentId || !bankId) {
      setError('Complete the required exam fields before saving the draft.')
      return
    }
    if (!Number.isInteger(Number(questionCount)) || !Number.isInteger(Number(durationMinutes)) || Number(questionCount) < 1 || Number(durationMinutes) < 1) {
      setError('Question count and duration must both be greater than zero.')
      return
    }
    if (capacityIssue) {
      setError(capacityIssue)
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
        })
      } else {
        await gateway.exams.createExam({
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
          duration_minutes: Number(durationMinutes),
          shuffle_questions: shuffleQuestions,
          shuffle_options: shuffleOptions,
          scheduled_start_at: toIsoOrNull(scheduledStartAt),
          latest_normal_start_at: toIsoOrNull(latestNormalStartAt),
        })
      }

      await teacherData.refresh()
      leaveForm()
    } catch (requestError) {
      setError(requestError.userMessage || `Weave could not ${editing ? 'update' : 'create'} this examination.`)
    } finally {
      setSaving(false)
    }
  }

  const canSave = Boolean(
    teacherData.session?.id &&
      teacherData.term?.id &&
      teacherData.subjects.length &&
      teacherData.assessmentSchemes.length &&
      subjectBanks.length &&
      components.length,
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

  const leadName = isAdmin ? leadTeacherName : actor?.display_name || 'You'
  const readiness = [
    ['Exam title added', Boolean(title.trim())],
    ['Academic context', Boolean(subjectId && schemeId && componentId && teacherData.session?.id && teacherData.term?.id)],
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
          <button className="teacher-exam-back" type="button" onClick={leaveForm}>
            <Icon name="back" size={16} /> Back to Examinations
          </button>
          <div className="teacher-page-title-line">
            <span className="teacher-page-title-icon"><Icon name="exam" size={28} /></span>
            <h1>{readOnly ? 'Examination details' : editing ? 'Edit Examination' : 'Create Examination'}</h1>
          </div>
          <p>{readOnly ? 'Review the paper and its current examination settings.' : 'Set up the paper, choose a question source and configure delivery.'}</p>
        </div>
        <div className="teacher-exam-builder-header__actions">
          <button className="teacher-secondary-action" type="button" onClick={leaveForm} disabled={saving || leadSaving}>{readOnly ? 'Back to exams' : 'Cancel'}</button>
          {!readOnly && (
            <button className="teacher-primary-action" type="submit" form="exam-authoring-form" disabled={!canSave || saving || leadSaving}>
              <Icon name="plus" size={17} />
              {saving ? 'Saving...' : editing ? 'Save changes' : 'Create Draft Exam'}
            </button>
          )}
        </div>
      </header>

      {error && <Notice tone="danger">{error}</Notice>}
      {teacherData.error && <Notice tone="danger">{teacherData.error}</Notice>}
      {teacherData.warning && <Notice tone="warning">{teacherData.warning}</Notice>}
      {!canSave && !teacherData.loading && !readOnly && (
        <Notice tone="warning">A current session, term, subject, assessment component and matching question bank are required to create an exam.</Notice>
      )}
      {readOnly && <Notice>This paper is {editingExam.statusLabel.toLowerCase()}. Draft metadata can only be edited by its lead author or an administrator.</Notice>}

      <form id="exam-authoring-form" className="teacher-exam-builder" onSubmit={saveExam}>
        <fieldset className="teacher-exam-builder__main" disabled={readOnly || saving || leadSaving}>
          <ExamSection number="1" title="Paper details" description="Define the academic context." kind="paper">
            <label className="teacher-exam-field">
              <span>Exam title <em>*</em></span>
              <input aria-label="Exam title" required value={title} maxLength={255} onChange={(event) => setTitle(event.target.value)} placeholder="e.g. Computer Studies CA2" />
            </label>
            <FieldSelect label="Subject *">
              <SelectControl
                label="Subject"
                value={subjectId}
                options={teacherData.subjects.map((subject) => ({ value: subject.id, label: subject.name }))}
                onChange={(value) => {
                  setSubjectId(value)
                  setLeadTeacherId('')
                  setLeadTeacherName('Administrator')
                  setBankId(teacherData.banks.find((bank) => bank.curriculumSubjectId === value)?.id || '')
                }}
                disabled={editing || readOnly}
                placeholder="Choose subject"
              />
            </FieldSelect>
            <FieldSelect label="Assessment scheme *">
              <SelectControl
                label="Assessment scheme"
                value={schemeId}
                options={teacherData.assessmentSchemes.map((scheme) => ({ value: scheme.id, label: scheme.name }))}
                onChange={(value) => {
                  setSchemeId(value)
                  setComponentId(teacherData.assessmentComponents.find((item) => item.schemeId === value)?.id || '')
                }}
                disabled={readOnly}
                placeholder="Choose scheme"
              />
            </FieldSelect>
            <FieldSelect label="Assessment component *">
              <SelectControl
                label="Assessment component"
                value={componentId}
                options={components.map((component) => ({ value: component.id, label: component.name, description: `${component.maximumScore} marks` }))}
                onChange={setComponentId}
                disabled={readOnly || !components.length}
                placeholder="Choose component"
              />
            </FieldSelect>
          </ExamSection>

          <ExamSection number="2" title="Authoring ownership" description="Coordinate this shared paper." kind="ownership">
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
                <span>{(actor?.display_name || 'You').slice(0, 1)}</span>
                <div><small>Lead author</small><strong>{leadName}</strong></div>
              </div>
            )}
            <p className="exam-ownership-help">
              <RiInformationLine size={18} />
              {isAdmin ? 'You may assign an eligible teacher to coordinate authoring.' : 'Teachers share the paper. The lead coordinates its details and submission.'}
            </p>
            <div className="exam-ownership-status">
              <StatusBadge tone="info">Shared {editingExam?.statusLabel.toLowerCase() || 'draft'}</StatusBadge>
              {editing && isAdmin && !readOnly && (
                <button type="button" className="exam-text-action" onClick={saveLead} disabled={leadSaving || leadTeacherId === (editingExam.leadTeacherId || '')}>
                  {leadSaving ? 'Updating...' : 'Update lead'}
                </button>
              )}
              {leadMessage && <small role="status">{leadMessage}</small>}
            </div>
          </ExamSection>

          <ExamSection number="3" title="Exam appearance" description="Folder colour preview." kind="appearance">
            <div className="exam-palette" role="group" aria-label="Folder colour preview">
              {FOLDER_COLORS.map(([name, color]) => (
                <button key={name} type="button" title={name} aria-label={`${name} folder`} aria-pressed={folderColor === color} style={{ '--swatch': color }} onClick={() => setFolderColor(color)}>
                  {folderColor === color && <RiCheckLine size={18} />}
                </button>
              ))}
            </div>
            <div className="exam-folder-preview">
              <ExamFolder color={folderColor} size={52} />
              <p><strong>Preview only</strong><small>Folder colours are not saved yet.</small></p>
            </div>
          </ExamSection>

          <ExamSection number="4" title="Questions" description="Choose the source and selection method." kind="questions">
            <FieldSelect label="Question bank *">
              <SelectControl label="Question bank" value={bankId} options={subjectBanks.map((bank) => ({ value: bank.id, label: bank.name }))} onChange={setBankId} disabled={editing || !subjectBanks.length || readOnly} placeholder="Choose bank" />
            </FieldSelect>
            <label className="teacher-exam-field">
              <span>Number of questions <em>*</em></span>
              <input aria-label="Number of questions" type="number" min="1" required value={questionCount} disabled={editing} onChange={(event) => setQuestionCount(event.target.value)} />
              <small>{questionCount || 0} required &middot; <b>{activeBankQuestions} available</b></small>
              {capacityIssue && <small className="teacher-exam-field__error">{capacityIssue}</small>}
            </label>
            <fieldset className="teacher-exam-selection" disabled={editing || readOnly}>
              <legend>Question selection method</legend>
              <div>
                <SelectionCard value="random" current={selectionMode} onChange={setSelectionMode} title="Random selection" description="Select from the bank." />
                <SelectionCard value="manual" current={selectionMode} onChange={setSelectionMode} title="Manual selection" description="Choose specific questions." />
              </div>
            </fieldset>
            {selectionMode === 'manual' && <p className="exam-section-note">Save the draft before adding specific questions. A manual paper cannot be submitted until its questions are selected.</p>}
            {editing && <p className="exam-section-note">The question source is fixed here to preserve existing selections.</p>}
          </ExamSection>

          <ExamSection number="5" title="Exam settings" description="Configure delivery for students." kind="settings">
            <label className="teacher-exam-field">
              <span>Duration <em>*</em></span>
              <div className="teacher-exam-input-suffix">
                <input aria-label="Duration in minutes" type="number" min="1" required value={durationMinutes} onChange={(event) => setDurationMinutes(event.target.value)} />
                <span>minutes</span>
              </div>
            </label>
            <ToggleSwitch checked={shuffleQuestions} onChange={setShuffleQuestions} label="Shuffle questions" />
            <ToggleSwitch checked={shuffleOptions} onChange={setShuffleOptions} label="Shuffle answer options" />
          </ExamSection>

          <ExamSection number="6" title="Schedule" description="Optional - this can be set later." kind="schedule">
            <label className="teacher-exam-field">
              <span>Scheduled start <small>(optional)</small></span>
              <input aria-label="Scheduled start" type="datetime-local" value={scheduledStartAt} onChange={(event) => setScheduledStartAt(event.target.value)} />
            </label>
            <label className="teacher-exam-field">
              <span>Latest normal start <small>(optional)</small></span>
              <input aria-label="Latest normal start" type="datetime-local" value={latestNormalStartAt} min={scheduledStartAt || undefined} onChange={(event) => setLatestNormalStartAt(event.target.value)} />
            </label>
            <label className="teacher-exam-field teacher-exam-field--wide">
              <span>Student instructions <small>(optional)</small></span>
              <textarea aria-label="Student instructions" rows="3" value={instructions} onChange={(event) => setInstructions(event.target.value)} placeholder="Instructions students will see before they start." />
            </label>
          </ExamSection>
        </fieldset>

        <aside className="exam-summary" aria-label="Draft examination summary">
          <header><Icon name="exam" size={19} /><div><h2>Exam summary</h2><p>Live preview of your examination.</p></div></header>
          <div className="exam-summary__preview"><ExamFolder color={folderColor} size={78} /><span className={`exam-status exam-status--${editingExam?.status || 'draft'}`}>{editingExam?.statusLabel || 'Draft'}</span></div>
          <h3>{title.trim() || 'Untitled examination'}</h3>
          <p className="exam-summary__context">{selectedSubject?.name || 'Choose subject'} &middot; {selectedComponent?.name || 'Choose component'}</p>
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
                <li><RiCheckboxBlankCircleLine size={17} /><span>Schedule & instructions optional</span></li>
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

function ToggleSwitch({ checked, onChange, label }) {
  return (
    <button type="button" className={`teacher-exam-switch ${checked ? 'is-on' : ''}`} role="switch" aria-checked={checked} onClick={() => onChange(!checked)}>
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
