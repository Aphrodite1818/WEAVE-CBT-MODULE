import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  RiArrowLeftLine,
  RiCloseCircleLine,
  RiPauseCircleLine,
  RiPlayCircleLine,
  RiSearchLine,
  RiStopCircleLine,
} from '@remixicon/react'
import { buildAcademicLevels, listSubjectsForLevel } from '../../../shared/academics/authoringScope'
import { Icon } from '../../../shared/icons/Icon'
import { Notice, SelectControl } from '../../../shared/ui'
import '../admin-exam-operations.css'

const OPERATIONAL_STATUSES = new Set(['sealed', 'active', 'suspended', 'closing', 'cancelling', 'closed', 'cancelled'])
const LIVE_STATUSES = new Set(['active', 'suspended', 'closing', 'cancelling'])
const TERMINAL_STATUSES = new Set(['closed', 'cancelled'])
const POLLABLE_STATUSES = new Set(['sealed', 'active', 'suspended', 'closing', 'cancelling'])
const TABS = [
  ['today', 'Today'],
  ['ready', 'Ready'],
  ['live', 'Live'],
  ['upcoming', 'Upcoming'],
  ['completed', 'Completed'],
]

export function ExamOperations({ adminData, onNavigate }) {
  const [tab, setTab] = useState('today')
  const [query, setQuery] = useState('')
  const [levelId, setLevelId] = useState('all')
  const [subjectId, setSubjectId] = useState('all')
  const now = new Date()

  const operationalExams = useMemo(
    () => adminData.exams.filter((exam) => OPERATIONAL_STATUSES.has(exam.status)),
    [adminData.exams],
  )
  const levels = useMemo(() => buildAcademicLevels(adminData.subjects), [adminData.subjects])
  const levelSubjects = useMemo(
    () => levelId === 'all' ? [] : listSubjectsForLevel(adminData.subjects, levelId),
    [adminData.subjects, levelId],
  )

  const refreshExams = adminData.refreshExams
  useEffect(() => {
    if (!operationalExams.some((exam) => POLLABLE_STATUSES.has(exam.status))) return undefined
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') void refreshExams({ silent: true })
    }, 5000)
    return () => window.clearInterval(timer)
  }, [operationalExams, refreshExams])

  const counts = useMemo(() => Object.fromEntries(
    TABS.map(([key]) => [key, operationalExams.filter((exam) => matchesTab(exam, key, now)).length]),
  ), [operationalExams])

  const metrics = useMemo(() => ({
    today: operationalExams.filter((exam) => isScheduledToday(exam, now)).length,
    ready: operationalExams.filter((exam) => exam.status === 'sealed' && exam.rosterStatus === 'ready').length,
    live: operationalExams.filter((exam) => LIVE_STATUSES.has(exam.status)).length,
    attention: operationalExams.filter(needsAttention).length,
  }), [operationalExams])

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return operationalExams
      .filter((exam) => matchesTab(exam, tab, now))
      .filter((exam) => levelId === 'all' || exam.academicLevelId === levelId)
      .filter((exam) => subjectId === 'all' || exam.curriculumSubjectId === subjectId)
      .filter((exam) => !needle || `${exam.title} ${exam.academicLevelName} ${exam.subjectName} ${exam.assessmentName}`.toLowerCase().includes(needle))
      .sort(compareOperationalExams)
  }, [levelId, operationalExams, query, subjectId, tab])

  const levelOptions = [
    { value: 'all', label: 'All levels' },
    ...levels.map((level) => ({ value: level.id, label: level.name })),
  ]
  const subjectOptions = [
    { value: 'all', label: 'All subjects' },
    ...levelSubjects.map((subject) => ({ value: subject.id, label: subject.name, description: subject.code || undefined })),
  ]

  const changeLevel = (nextLevelId) => {
    setLevelId(nextLevelId)
    setSubjectId('all')
  }

  return (
    <div className="teacher-reference-page admin-ops-page">
      <div className="teacher-page-heading admin-ops-heading">
        <div>
          <div className="teacher-page-title-line">
            <span className="teacher-page-title-icon"><Icon name="operations" size={27} /></span>
            <h1>Exam Operations</h1>
          </div>
          <p>Run scheduled examinations, control live sittings and respond to examination-day events.</p>
        </div>
      </div>

      {adminData.error && <Notice tone="danger">{adminData.error}</Notice>}
      {adminData.warning && <Notice tone="warning">{adminData.warning}</Notice>}

      <section className="admin-ops-metrics" aria-label="Examination operations summary">
        <OperationsMetric icon="calendar" label="Scheduled today" value={metrics.today} helper="Operational papers on today's timetable" />
        <OperationsMetric icon="check" label="Ready to start" value={metrics.ready} helper="Sealed papers with ready rosters" tone="ready" />
        <OperationsMetric icon="bolt" label="Live examinations" value={metrics.live} helper="Active or transitioning sittings" tone="live" />
        <OperationsMetric icon="flag" label="Need attention" value={metrics.attention} helper="Suspended or roster-health issues" tone={metrics.attention ? 'attention' : ''} />
      </section>

      <nav className="teacher-tab-row admin-ops-tabs" aria-label="Operation views">
        {TABS.map(([key, label]) => (
          <button key={key} type="button" className={tab === key ? 'active' : ''} aria-current={tab === key ? 'page' : undefined} onClick={() => setTab(key)}>
            {label} <span>{counts[key] || 0}</span>
          </button>
        ))}
      </nav>

      <div className="admin-ops-filters">
        <label className="teacher-search-control teacher-search-control--grow">
          <RiSearchLine size={18} aria-hidden="true" />
          <input
            aria-label="Search operational examinations"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by exam, level, subject, or assessment..."
          />
        </label>
        <SelectControl label="Operations level filter" value={levelId} options={levelOptions} onChange={changeLevel} />
        <SelectControl
          label="Operations subject filter"
          value={subjectId}
          options={subjectOptions}
          onChange={setSubjectId}
          disabled={levelId === 'all'}
        />
      </div>

      <section className="admin-ops-schedule" aria-label={`${TABS.find(([key]) => key === tab)?.[1] || 'Exam'} operations`} aria-busy={adminData.loading}>
        <div className="admin-ops-schedule__heading">
          <div>
            <span>{TABS.find(([key]) => key === tab)?.[1]}</span>
            <strong>{viewDescription(tab)}</strong>
          </div>
          <small>{filtered.length} {filtered.length === 1 ? 'examination' : 'examinations'}</small>
        </div>

        <div className="admin-ops-list">
          {filtered.map((exam) => (
            <OperationalExamRow key={exam.id} exam={exam} onOpen={() => onNavigate('operation-detail', { selectedExamId: exam.id })} />
          ))}

          {!adminData.loading && filtered.length === 0 && (
            <div className="admin-ops-empty">
              <span><Icon name="operations" size={28} /></span>
              <div>
                <strong>No examinations in this view</strong>
                <p>{emptyCopy(tab, operationalExams.length)}</p>
              </div>
            </div>
          )}
          {adminData.loading && <div className="admin-ops-empty"><div><strong>Loading examination operations…</strong></div></div>}
        </div>
      </section>
    </div>
  )
}

export function ExamOperationsDetail({ state, adminData, gateway, onNavigate }) {
  const exam = adminData.exams.find((item) => item.id === state.staff.selectedExamId)
  const [pendingAction, setPendingAction] = useState(null)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const refreshExams = adminData.refreshExams

  useEffect(() => {
    if (!exam || !POLLABLE_STATUSES.has(exam.status)) return undefined
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') void refreshExams({ silent: true })
    }, 4000)
    return () => window.clearInterval(timer)
  }, [exam?.id, exam?.status, refreshExams])

  if (!exam) {
    return (
      <div className="teacher-reference-page admin-ops-detail">
        <button className="admin-ops-back" type="button" onClick={() => onNavigate('operations')}><RiArrowLeftLine size={17} /> Back to operations</button>
        <Notice tone="warning">The selected examination is no longer available.</Notice>
      </div>
    )
  }

  const controls = controlsFor(exam)
  const openAction = (action) => {
    setPendingAction(action)
    setReason('')
    setError('')
  }
  const closeModal = () => {
    if (busy) return
    setPendingAction(null)
    setReason('')
    setError('')
  }
  const confirmAction = async () => {
    if (!pendingAction) return
    if (requiresReason(pendingAction) && !reason.trim()) {
      setError('Enter a reason before continuing with this examination action.')
      return
    }
    setBusy(true)
    setError('')
    try {
      if (pendingAction === 'activate') await gateway.exams.activateExam(exam.id)
      if (pendingAction === 'suspend') await gateway.exams.suspendExam(exam.id, reason.trim())
      if (pendingAction === 'resume') await gateway.exams.resumeExam(exam.id, reason.trim() || undefined)
      if (pendingAction === 'close') await gateway.exams.closeExam(exam.id)
      if (pendingAction === 'cancel') await gateway.exams.cancelExam(exam.id, reason.trim())
      await refreshExams({ silent: false })
      setPendingAction(null)
      setReason('')
    } catch (requestError) {
      setError(requestError.userMessage || `Weave could not ${pendingAction} this examination.`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="teacher-reference-page admin-ops-detail">
      <button className="admin-ops-back" type="button" onClick={() => onNavigate('operations')}><RiArrowLeftLine size={17} /> Back to operations</button>

      <div className="admin-ops-detail__hero">
        <div className="admin-ops-detail__identity">
          <span className="admin-ops-detail__icon"><Icon name="operations" size={27} /></span>
          <div>
            <div className="admin-ops-detail__eyebrow">{[exam.academicLevelName, exam.subjectName, exam.assessmentName].filter(Boolean).join(' · ')}</div>
            <h1>{exam.title}</h1>
            <p>{scheduleSentence(exam)}</p>
          </div>
        </div>
        <ExamState status={exam.status} />
      </div>

      {operationNotice(exam)}
      {adminData.error && <Notice tone="danger">{adminData.error}</Notice>}

      <section className="admin-ops-detail__metrics" aria-label="Examination control summary">
        <DetailMetric label="Scheduled start" value={formatSchedule(exam.scheduledStartAt)} helper={exam.latestNormalStartAt ? `Normal entry until ${formatClock(exam.latestNormalStartAt)}` : 'No normal-entry cutoff supplied'} />
        <DetailMetric label="Candidate roster" value={String(exam.rosterCandidateCount || 0)} helper={`Roster ${rosterLabel(exam.rosterStatus).toLowerCase()} · v${exam.rosterVersion || 0}`} />
        <DetailMetric label="Duration" value={`${exam.durationMinutes || 0} min`} helper={`${exam.questionCount || 0} questions in the sealed paper`} />
        <DetailMetric label="Operational state" value={exam.statusLabel} helper={stateHelper(exam.status)} />
      </section>

      <div className="admin-ops-detail__grid">
        <section className="admin-ops-control-panel">
          <div className="admin-ops-section-heading">
            <div><span>Exam controls</span><strong>{controlHeading(exam.status)}</strong></div>
            <ExamState status={exam.status} compact />
          </div>

          <div className="admin-ops-control-panel__body">
            <div className="admin-ops-control-copy">
              <span className="admin-ops-control-copy__icon"><ControlStateIcon status={exam.status} /></span>
              <div>
                <strong>{controlMessage(exam)}</strong>
                <p>{controlDescription(exam)}</p>
              </div>
            </div>

            {controls.length > 0 ? (
              <div className="admin-ops-actions">
                {controls.map((control) => {
                  const ActionIcon = control.Icon
                  return (
                    <button
                      key={control.action}
                      type="button"
                      className={`admin-ops-action admin-ops-action--${control.tone || 'neutral'}`}
                      disabled={control.disabled}
                      onClick={() => openAction(control.action)}
                    >
                      <span><ActionIcon size={19} /></span>
                      <div><strong>{control.label}</strong><small>{control.copy}</small></div>
                    </button>
                  )
                })}
              </div>
            ) : (
              <div className="admin-ops-readonly"><Icon name="info" size={18} /><span>{terminalControlCopy(exam.status)}</span></div>
            )}
          </div>
        </section>

        <aside className="admin-ops-context-panel">
          <div className="admin-ops-section-heading"><div><span>Operational context</span><strong>Exam resources</strong></div></div>
          <button type="button" onClick={() => onNavigate('roster-detail', { selectedExamId: exam.id })}>
            <span><Icon name="roster" size={19} /></span>
            <div><strong>Candidate roster</strong><small>{exam.rosterCandidateCount || 0} candidates · {rosterLabel(exam.rosterStatus)}</small></div>
            <Icon name="chevronRight" size={17} />
          </button>
          <button type="button" onClick={() => onNavigate('create-exam', { selectedExamId: exam.id })}>
            <span><Icon name="exam" size={19} /></span>
            <div><strong>Examination paper</strong><small>View the sealed paper and authoring record</small></div>
            <Icon name="chevronRight" size={17} />
          </button>
          <div className="admin-ops-context-panel__meta">
            <div><span>Roster health</span><RosterState status={exam.rosterStatus} /></div>
            <div><span>Revision</span><strong>Revision {exam.revisionNumber || 1}</strong></div>
            <div><span>Assessment</span><strong>{exam.assessmentName}</strong></div>
          </div>
        </aside>
      </div>

      {pendingAction && (
        <OperationConfirmModal
          exam={exam}
          action={pendingAction}
          reason={reason}
          setReason={setReason}
          error={error}
          busy={busy}
          onCancel={closeModal}
          onConfirm={confirmAction}
        />
      )}
    </div>
  )
}

function OperationsMetric({ icon, label, value, helper, tone = '' }) {
  return (
    <article className={`admin-ops-metric${tone ? ` admin-ops-metric--${tone}` : ''}`}>
      <span className="admin-ops-metric__icon"><Icon name={icon} size={20} /></span>
      <div><span>{label}</span><strong>{value}</strong><small>{helper}</small></div>
    </article>
  )
}

function OperationalExamRow({ exam, onOpen }) {
  const schedule = exam.scheduledStartAt ? new Date(exam.scheduledStartAt) : null
  return (
    <article className={`admin-ops-exam-row${needsAttention(exam) ? ' admin-ops-exam-row--attention' : ''}`}>
      <div className="admin-ops-exam-row__time">
        <strong>{schedule ? formatClock(exam.scheduledStartAt) : '—'}</strong>
        <span>{schedule ? formatDay(exam.scheduledStartAt) : 'Unscheduled'}</span>
      </div>
      <div className="admin-ops-exam-row__main">
        <div className="admin-ops-exam-row__topline">
          <span>{[exam.academicLevelName, exam.subjectName].filter(Boolean).join(' · ') || 'Examination'}</span>
          <ExamState status={exam.status} compact />
        </div>
        <h2>{exam.title}</h2>
        <p>{exam.assessmentName} · {exam.durationMinutes || 0} min · {exam.questionCount || 0} questions</p>
      </div>
      <div className="admin-ops-exam-row__health">
        <div><span>Roster</span><strong>{exam.rosterCandidateCount || 0} candidates</strong></div>
        <RosterState status={exam.rosterStatus} />
      </div>
      <button className="admin-ops-exam-row__open" type="button" onClick={onOpen}>
        <span>{LIVE_STATUSES.has(exam.status) ? 'Open control room' : exam.status === 'sealed' ? 'Prepare sitting' : 'View summary'}</span>
        <Icon name="chevronRight" size={17} />
      </button>
    </article>
  )
}

function DetailMetric({ label, value, helper }) {
  return <div className="admin-ops-detail-metric"><span>{label}</span><strong>{value}</strong><small>{helper}</small></div>
}

function ExamState({ status, compact = false }) {
  return <span className={`admin-ops-state admin-ops-state--${status}${compact ? ' is-compact' : ''}`}>{titleCase(status)}</span>
}

function RosterState({ status }) {
  return <span className={`admin-ops-roster-state admin-ops-roster-state--${status}`}>{rosterLabel(status)}</span>
}

function ControlStateIcon({ status }) {
  if (status === 'active' || status === 'sealed') return <RiPlayCircleLine size={24} />
  if (status === 'suspended') return <RiPauseCircleLine size={24} />
  if (status === 'closing' || status === 'closed') return <RiStopCircleLine size={24} />
  if (status === 'cancelling' || status === 'cancelled') return <RiCloseCircleLine size={24} />
  return <Icon name="operations" size={24} />
}

function controlsFor(exam) {
  if (exam.status === 'sealed') return [
    {
      action: 'activate',
      label: 'Activate examination',
      copy: exam.rosterStatus === 'ready' ? 'Open this sitting to candidates on the prepared roster.' : 'The candidate roster must be ready before activation.',
      Icon: RiPlayCircleLine,
      tone: 'primary',
      disabled: exam.rosterStatus !== 'ready',
    },
    { action: 'cancel', label: 'Cancel sitting', copy: 'Invalidate this sitting with a required audit reason.', Icon: RiCloseCircleLine, tone: 'danger' },
  ]
  if (exam.status === 'active') return [
    { action: 'suspend', label: 'Suspend examination', copy: 'Temporarily pause the live sitting while preserving candidate time.', Icon: RiPauseCircleLine, tone: 'warning' },
    { action: 'close', label: 'Close examination', copy: 'Permanently finish the sitting and finalize unfinished attempts.', Icon: RiStopCircleLine },
    { action: 'cancel', label: 'Cancel sitting', copy: 'Invalidate this sitting and terminate unfinished attempts.', Icon: RiCloseCircleLine, tone: 'danger' },
  ]
  if (exam.status === 'suspended') return [
    { action: 'resume', label: 'Resume examination', copy: 'Return this paused sitting to active execution.', Icon: RiPlayCircleLine, tone: 'primary' },
    { action: 'close', label: 'Close examination', copy: 'Permanently finish the sitting while it is suspended.', Icon: RiStopCircleLine },
    { action: 'cancel', label: 'Cancel sitting', copy: 'Invalidate the suspended sitting with an audit reason.', Icon: RiCloseCircleLine, tone: 'danger' },
  ]
  return []
}

function OperationConfirmModal({ exam, action, reason, setReason, error, busy, onCancel, onConfirm }) {
  const copy = operationCopy(action)
  const ActionIcon = copy.Icon
  return createPortal(
    <div className="admin-ops-confirm-backdrop" onMouseDown={(event) => { if (event.currentTarget === event.target && !busy) onCancel() }}>
      <section className={`admin-ops-confirm${copy.danger ? ' is-danger' : ''}`} role="alertdialog" aria-modal="true" aria-labelledby="admin-ops-confirm-title" aria-describedby="admin-ops-confirm-description">
        <div className="admin-ops-confirm__heading">
          <span><ActionIcon size={22} /></span>
          <div><h2 id="admin-ops-confirm-title">{copy.title}</h2><p id="admin-ops-confirm-description">{copy.description}</p></div>
        </div>
        <div className="admin-ops-confirm__exam"><span>Examination</span><strong>{exam.title}</strong><small>{exam.subjectName} · {exam.assessmentName}</small></div>
        {copy.reason && (
          <label className="admin-ops-confirm__reason">
            <span>Reason {requiresReason(action) ? '' : '(optional)'}</span>
            <textarea rows="3" value={reason} onChange={(event) => setReason(event.target.value)} placeholder={copy.placeholder} />
          </label>
        )}
        <div className={`admin-ops-confirm__warning${copy.danger ? ' is-danger' : ''}`}><Icon name="info" size={17} /><span>{copy.warning}</span></div>
        {error && <Notice tone="danger">{error}</Notice>}
        <div className="admin-ops-confirm__actions">
          <button type="button" className="admin-ops-confirm__cancel" disabled={busy} onClick={onCancel}>Go back</button>
          <button type="button" className={`admin-ops-confirm__submit${copy.danger ? ' is-danger' : ''}`} disabled={busy} onClick={onConfirm}>{busy ? 'Working…' : copy.confirm}</button>
        </div>
      </section>
    </div>,
    document.body,
  )
}

function operationCopy(action) {
  const copy = {
    activate: {
      title: 'Activate this examination?',
      description: 'Candidates on the prepared roster will be allowed to start this sitting.',
      confirm: 'Activate examination',
      Icon: RiPlayCircleLine,
      warning: 'Activation moves this paper into execution. Later Weave enrollment changes will not rewrite the active sitting roster.',
    },
    suspend: {
      title: 'Suspend this examination?',
      description: 'The live sitting will pause while candidate execution state remains protected.',
      confirm: 'Suspend examination',
      Icon: RiPauseCircleLine,
      reason: true,
      placeholder: 'Explain why the live examination is being suspended.',
      warning: 'Use suspension for a temporary operational interruption that may be resumed.',
    },
    resume: {
      title: 'Resume this examination?',
      description: 'The suspended sitting will return to active execution.',
      confirm: 'Resume examination',
      Icon: RiPlayCircleLine,
      reason: true,
      placeholder: 'Optional note explaining why the sitting is being resumed.',
      warning: 'Candidates will be able to continue according to the backend attempt lifecycle rules.',
    },
    close: {
      title: 'Close this examination?',
      description: 'Closing permanently ends this sitting and begins finalization of unfinished attempts.',
      confirm: 'Close examination',
      Icon: RiStopCircleLine,
      warning: 'Once closing begins, this sitting cannot return to ACTIVE. Suspend instead if the exam may need to continue.',
    },
    cancel: {
      title: 'Cancel this examination sitting?',
      description: 'Cancellation invalidates the sitting and terminates unfinished execution.',
      confirm: 'Cancel sitting',
      Icon: RiCloseCircleLine,
      danger: true,
      reason: true,
      placeholder: 'State the administrative reason for cancelling this sitting.',
      warning: 'Cancellation is an invalidation action, not a temporary pause. This transition cannot be reversed.',
    },
  }
  return copy[action]
}

function operationNotice(exam) {
  if (exam.rosterStatus === 'stale') return <Notice tone="warning">Enrollment changed in Weave. The roster is being reconciled automatically; activation remains unavailable until it returns to Ready.</Notice>
  if (exam.rosterStatus === 'failed') return <Notice tone="danger">{exam.rosterError || 'The candidate roster could not be prepared or reconciled. Resolve the roster issue before running this examination.'}</Notice>
  if (exam.status === 'suspended') return <Notice tone="warning">This examination is suspended. Candidate execution remains paused until an administrator resumes, closes or cancels the sitting.</Notice>
  if (exam.status === 'closing') return <Notice tone="neutral">This examination is closing. Finalization is in progress and lifecycle controls are locked.</Notice>
  if (exam.status === 'cancelling') return <Notice tone="warning">This examination is being cancelled. Finalization is in progress and lifecycle controls are locked.</Notice>
  return null
}

function controlHeading(status) {
  if (status === 'sealed') return 'Prepare and start the sitting'
  if (status === 'active') return 'Live examination controls'
  if (status === 'suspended') return 'Suspended examination controls'
  if (status === 'closing') return 'Closing in progress'
  if (status === 'cancelling') return 'Cancellation in progress'
  return 'Read-only examination state'
}

function controlMessage(exam) {
  if (exam.status === 'sealed') return exam.rosterStatus === 'ready' ? 'This examination is ready for operational activation.' : 'This examination is waiting for a healthy candidate roster.'
  if (exam.status === 'active') return 'This examination is currently open to eligible candidates.'
  if (exam.status === 'suspended') return 'Candidate execution is temporarily paused.'
  if (exam.status === 'closing') return 'The backend is finalizing this examination.'
  if (exam.status === 'cancelling') return 'The backend is invalidating this sitting.'
  if (exam.status === 'closed') return 'This examination has been permanently closed.'
  if (exam.status === 'cancelled') return 'This examination sitting has been cancelled.'
  return 'No operational controls are available.'
}

function controlDescription(exam) {
  if (exam.status === 'sealed') return exam.rosterStatus === 'ready'
    ? 'Activate when the examination centre is ready. Operational actions are audited by the backend lifecycle.'
    : `Roster status is ${rosterLabel(exam.rosterStatus)}. Open the roster to inspect preparation or reconciliation.`
  if (exam.status === 'active') return 'Use Suspend for a recoverable interruption. Close only when the sitting is genuinely finished.'
  if (exam.status === 'suspended') return 'Resume to continue the same sitting, or close/cancel it if execution should not continue.'
  if (exam.status === 'closing' || exam.status === 'cancelling') return 'This transition is irreversible. Controls will remain unavailable until finalization completes.'
  return 'Historical execution state remains available for operational review.'
}

function terminalControlCopy(status) {
  if (status === 'closing') return 'Finalization is in progress. Reverse lifecycle actions are unavailable.'
  if (status === 'cancelling') return 'Cancellation finalization is in progress. Reverse lifecycle actions are unavailable.'
  if (status === 'closed') return 'This sitting is closed and read-only. Use Examinations if a new paper revision is required.'
  if (status === 'cancelled') return 'This sitting is cancelled and read-only. A replacement revision is created from the Examinations workspace.'
  return 'No operational actions are currently available.'
}

function matchesTab(exam, tab, now) {
  if (tab === 'today') return isScheduledToday(exam, now) || LIVE_STATUSES.has(exam.status)
  if (tab === 'ready') return exam.status === 'sealed'
  if (tab === 'live') return LIVE_STATUSES.has(exam.status)
  if (tab === 'upcoming') return exam.status === 'sealed' && isFutureDay(exam.scheduledStartAt, now)
  if (tab === 'completed') return TERMINAL_STATUSES.has(exam.status)
  return true
}

function compareOperationalExams(left, right) {
  const priority = { active: 0, suspended: 1, closing: 2, cancelling: 3, sealed: 4, closed: 5, cancelled: 6 }
  const statusDelta = (priority[left.status] ?? 9) - (priority[right.status] ?? 9)
  if (statusDelta !== 0) return statusDelta
  const leftTime = left.scheduledStartAt ? new Date(left.scheduledStartAt).getTime() : Number.MAX_SAFE_INTEGER
  const rightTime = right.scheduledStartAt ? new Date(right.scheduledStartAt).getTime() : Number.MAX_SAFE_INTEGER
  return leftTime - rightTime
}

function needsAttention(exam) {
  return ['stale', 'failed'].includes(exam.rosterStatus) || ['suspended', 'cancelling'].includes(exam.status)
}

function isScheduledToday(exam, now) {
  if (!exam.scheduledStartAt) return false
  const date = new Date(exam.scheduledStartAt)
  return date.getFullYear() === now.getFullYear() && date.getMonth() === now.getMonth() && date.getDate() === now.getDate()
}

function isFutureDay(value, now) {
  if (!value) return false
  const date = new Date(value)
  const startOfTomorrow = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1)
  return date >= startOfTomorrow
}

function viewDescription(tab) {
  if (tab === 'today') return 'Today’s examination timetable'
  if (tab === 'ready') return 'Sealed papers waiting for execution'
  if (tab === 'live') return 'Active and transitioning examination sittings'
  if (tab === 'upcoming') return 'Future sealed examinations'
  return 'Closed and cancelled examination sittings'
}

function emptyCopy(tab, total) {
  if (!total) return 'Operational examinations appear here after a paper is sealed.'
  if (tab === 'today') return 'No operational examinations are scheduled for today. Check Ready or Upcoming for other sittings.'
  if (tab === 'live') return 'There are no examinations currently running or transitioning.'
  if (tab === 'ready') return 'There are no sealed examinations waiting for activation.'
  if (tab === 'upcoming') return 'There are no future sealed examinations matching these filters.'
  return 'There are no completed examination sittings matching these filters.'
}

function scheduleSentence(exam) {
  if (!exam.scheduledStartAt) return 'No scheduled start time is attached to this examination.'
  return `Scheduled ${formatSchedule(exam.scheduledStartAt)} · ${exam.durationMinutes || 0} minutes`
}

function formatSchedule(value) {
  if (!value) return 'Not scheduled'
  const date = new Date(value)
  return new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' }).format(date)
}

function formatClock(value) {
  if (!value) return '—'
  return new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' }).format(new Date(value))
}

function formatDay(value) {
  if (!value) return 'Unscheduled'
  return new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short' }).format(new Date(value))
}

function stateHelper(status) {
  if (status === 'sealed') return 'Waiting for operational activation'
  if (status === 'active') return 'Candidates may currently execute this sitting'
  if (status === 'suspended') return 'Live execution is temporarily paused'
  if (status === 'closing') return 'Finalizing saved candidate work'
  if (status === 'cancelling') return 'Invalidating the current sitting'
  if (status === 'closed') return 'Execution has finished permanently'
  if (status === 'cancelled') return 'This sitting was invalidated'
  return 'Operational state'
}

function rosterLabel(status) {
  const labels = {
    not_prepared: 'Not prepared',
    pending: 'Pending',
    building: 'Building',
    ready: 'Ready',
    stale: 'Stale',
    failed: 'Failed',
  }
  return labels[status] || titleCase(status)
}

function requiresReason(action) {
  return action === 'suspend' || action === 'cancel'
}

function titleCase(value) {
  return String(value || '').replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}
