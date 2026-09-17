import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  RiAddLine,
  RiArrowGoBackLine,
  RiCloseCircleLine,
  RiDeleteBinLine,
  RiEdit2Line,
  RiPauseCircleLine,
  RiPlayCircleLine,
  RiRefreshLine,
  RiSearchLine,
  RiSendPlaneLine,
  RiShieldCheckLine,
  RiStopCircleLine,
} from '@remixicon/react'
import { Icon } from '../../../shared/icons/Icon'
import { Notice, SelectControl, StatusBadge } from '../../../shared/ui'

const PAGE_SIZE = 10
const tabs = ['all', 'draft', 'submitted', 'sealed', 'active', 'suspended', 'closed', 'cancelled']

export function AdminExamsPage({ state, adminData, gateway, onNavigate }) {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('all')
  const [subjectId, setSubjectId] = useState('all')
  const [componentId, setComponentId] = useState('all')
  const [page, setPage] = useState(1)
  const [menuExamId, setMenuExamId] = useState(null)
  const [pending, setPending] = useState(null)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const menuRef = useRef(null)

  useEffect(() => {
    if (!menuExamId) return undefined
    const close = (event) => {
      if (event.type === 'keydown' && event.key === 'Escape') setMenuExamId(null)
      if (event.type === 'pointerdown' && menuRef.current && !menuRef.current.contains(event.target)) setMenuExamId(null)
    }
    document.addEventListener('pointerdown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('pointerdown', close)
      document.removeEventListener('keydown', close)
    }
  }, [menuExamId])

  const counts = useMemo(() => {
    const result = Object.fromEntries(tabs.map((item) => [item, 0]))
    result.all = adminData.exams.length
    adminData.exams.forEach((exam) => { if (result[exam.status] !== undefined) result[exam.status] += 1 })
    return result
  }, [adminData.exams])

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return adminData.exams.filter((exam) => {
      if (status !== 'all' && exam.status !== status) return false
      if (subjectId !== 'all' && exam.curriculumSubjectId !== subjectId) return false
      if (componentId !== 'all' && exam.assessmentComponentId !== componentId) return false
      if (!needle) return true
      return `${exam.title} ${exam.subjectName} ${exam.assessmentName}`.toLowerCase().includes(needle)
    })
  }, [adminData.exams, componentId, query, status, subjectId])

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const visible = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  useEffect(() => { if (page > pageCount) setPage(pageCount) }, [page, pageCount])

  const setFilter = (setter) => (value) => { setter(value); setPage(1) }
  const request = (exam, action) => {
    setMenuExamId(null)
    setPending({ exam, action })
    setReason('')
    setError('')
  }

  const confirm = async () => {
    if (!pending) return
    if (requiresReason(pending.action) && !reason.trim()) {
      setError('Enter a reason before continuing with this lifecycle action.')
      return
    }
    setBusy(true)
    setError('')
    const { exam, action } = pending
    try {
      if (action === 'submit') await gateway.exams.submitExam(exam.id, exam.authoringVersion || 1)
      if (action === 'delete') await gateway.exams.deleteDraftExam(exam.id, exam.authoringVersion || 1)
      if (action === 'return-draft') await gateway.exams.returnExamToDraft(exam.id)
      if (action === 'seal') await gateway.exams.sealExam(exam.id)
      if (action === 'revision') await gateway.exams.createRevision(exam.id)
      if (action === 'activate') await gateway.exams.activateExam(exam.id)
      if (action === 'suspend') await gateway.exams.suspendExam(exam.id, reason.trim())
      if (action === 'resume') await gateway.exams.resumeExam(exam.id, reason.trim() || undefined)
      if (action === 'close') await gateway.exams.closeExam(exam.id)
      if (action === 'cancel') await gateway.exams.cancelExam(exam.id, reason.trim())
      await adminData.refresh()
      setPending(null)
      setReason('')
    } catch (requestError) {
      setError(requestError.userMessage || `Weave could not ${action.replace('-', ' ')} this examination.`)
    } finally {
      setBusy(false)
    }
  }

  const subjectOptions = [{ value: 'all', label: 'All subjects' }, ...adminData.subjects.map((subject) => ({ value: subject.id, label: subject.name, description: subject.code || undefined }))]
  const componentOptions = [{ value: 'all', label: 'All components' }, ...adminData.assessmentComponents.map((component) => ({ value: component.id, label: component.name, description: `${component.maximumScore} marks` }))]

  return (
    <div className="teacher-reference-page teacher-exams-page admin-exams-page">
      <div className="teacher-page-heading teacher-exams-heading">
        <div>
          <div className="teacher-page-title-line"><span className="teacher-page-title-icon"><Icon name="calendar" size={27} /></span><h1>Examinations</h1></div>
          <p>Create papers and control the full administrator examination lifecycle from review through closure.</p>
        </div>
        <button className="teacher-primary-action" type="button" onClick={() => onNavigate('create-exam', { selectedExamId: null })}><RiAddLine size={18} /> Create Exam</button>
      </div>

      {adminData.error && <Notice tone="danger">{adminData.error}</Notice>}
      {adminData.warning && <Notice tone="warning">{adminData.warning}</Notice>}

      <nav className="teacher-tab-row teacher-exam-tabs" aria-label="Exam status filters">
        {tabs.map((tab) => <button key={tab} type="button" className={status === tab ? 'active' : ''} aria-current={status === tab ? 'page' : undefined} onClick={() => setFilter(setStatus)(tab)}>{titleCase(tab)} <span>{counts[tab] || 0}</span></button>)}
      </nav>

      <div className="teacher-exam-filters teacher-exam-filters--refined">
        <label className="teacher-search-control teacher-search-control--grow"><RiSearchLine size={18} /><input aria-label="Search examinations" type="search" value={query} onChange={(event) => { setQuery(event.target.value); setPage(1) }} placeholder="Search by title, subject, or assessment..." /></label>
        <SelectControl label="Exam subject filter" value={subjectId} options={subjectOptions} onChange={setFilter(setSubjectId)} />
        <SelectControl label="Assessment component filter" value={componentId} options={componentOptions} onChange={setFilter(setComponentId)} />
      </div>

      <section className="teacher-exam-collection" aria-label="School examinations" aria-busy={adminData.loading}>
        <div className="teacher-exam-collection__header" aria-hidden="true"><span>Examination</span><span>Academic context</span><span>Paper</span><span>Schedule</span><span>Status</span><span>Updated</span><span>Actions</span></div>
        {visible.map((exam) => (
          <article className="teacher-exam-entity" key={exam.id}>
            <div className="teacher-exam-entity__title">
              <span className="teacher-exam-entity__icon"><Icon name="exam" size={20} /></span>
              <div><h2>{exam.title}</h2><p>{formatSelectionMode(exam.selectionMode)} · Revision {exam.revisionNumber || 1}</p></div>
            </div>
            <div className="teacher-exam-entity__stack" data-label="Academic context"><strong>{exam.subjectName}</strong><span>{exam.assessmentName}</span></div>
            <div className="teacher-exam-entity__stack" data-label="Paper"><strong>{exam.questionCount} {exam.questionCount === 1 ? 'question' : 'questions'}</strong><span>{exam.durationMinutes} min</span></div>
            <div className="teacher-exam-entity__stack" data-label="Schedule"><strong>{exam.scheduledStartAt ? formatDate(exam.scheduledStartAt) : 'Not scheduled'}</strong><span>{exam.scheduledStartAt ? formatTime(exam.scheduledStartAt) : 'Timing not set'}</span></div>
            <div data-label="Status"><StatusBadge tone={statusTone(exam.status)}>{exam.statusLabel}</StatusBadge></div>
            <div className="teacher-exam-entity__updated" data-label="Updated">{formatDate(exam.updatedAt)}</div>
            <div className="teacher-exam-entity__actions" data-label="Actions">
              <div className="teacher-exam-lifecycle" ref={menuExamId === exam.id ? menuRef : undefined}>
                <button className="teacher-exam-lifecycle__trigger" type="button" aria-label={`Lifecycle actions for ${exam.title}`} aria-expanded={menuExamId === exam.id} onClick={() => setMenuExamId((current) => current === exam.id ? null : exam.id)}><Icon name="moreVertical" size={19} /></button>
                {menuExamId === exam.id && <AdminLifecycleMenu exam={exam} onEdit={() => { setMenuExamId(null); onNavigate('create-exam', { selectedExamId: exam.id }) }} onAction={(action) => request(exam, action)} />}
              </div>
            </div>
          </article>
        ))}
        {!adminData.loading && visible.length === 0 && <div className="teacher-exam-collection__empty"><span><Icon name="calendar" size={24} /></span><strong>{adminData.exams.length ? 'No examinations match these filters' : 'No examinations yet'}</strong><p>{adminData.exams.length ? 'Adjust the search or lifecycle filters.' : 'Create the first draft examination for this school.'}</p></div>}
        {adminData.loading && <div className="teacher-exam-collection__empty"><strong>Loading examinations…</strong></div>}
        <div className="teacher-exam-pagination teacher-exam-pagination--refined"><span>{filtered.length === 0 ? '0 exams' : `Showing ${(page - 1) * PAGE_SIZE + 1}–${Math.min(page * PAGE_SIZE, filtered.length)} of ${filtered.length} exams`}</span><div><button type="button" disabled={page === 1} onClick={() => setPage((value) => value - 1)}>‹</button><span>{page} / {pageCount}</span><button type="button" disabled={page === pageCount} onClick={() => setPage((value) => value + 1)}>›</button></div></div>
      </section>

      {pending && <LifecycleModal pending={pending} reason={reason} setReason={setReason} error={error} busy={busy} onCancel={() => { if (!busy) { setPending(null); setReason(''); setError('') } }} onConfirm={confirm} />}
    </div>
  )
}

function AdminLifecycleMenu({ exam, onEdit, onAction }) {
  const actions = lifecycleActions(exam)
  return (
    <div className="teacher-exam-lifecycle__menu admin-exam-lifecycle__menu" role="dialog" aria-label={`Lifecycle for ${exam.title}`}>
      <div className="teacher-exam-lifecycle__heading"><div><strong>Exam lifecycle</strong><span>{exam.statusLabel}</span></div><small>v{exam.authoringVersion || 1}</small></div>
      {exam.status === 'draft' && <button type="button" onClick={onEdit}><RiEdit2Line size={18} /><span><strong>Edit draft</strong><small>Update metadata, timing and delivery settings.</small></span></button>}
      {actions.map((action) => (
        <button key={action.key} type="button" disabled={action.disabled} className={action.danger ? 'teacher-exam-lifecycle__danger' : ''} onClick={() => onAction(action.key)}>
          <action.Icon size={18} />
          <span><strong>{action.label}</strong><small>{action.copy}</small></span>
        </button>
      ))}
      {!actions.length && exam.status !== 'draft' && <div className="teacher-exam-lifecycle__info"><Icon name="info" size={18} /><p>This examination is preserved in its current terminal lifecycle state.</p></div>}
    </div>
  )
}

function lifecycleActions(exam) {
  if (exam.status === 'draft') return [
    { key: 'submit', label: 'Submit for review', copy: 'Validate the paper and move it to submitted.', Icon: RiSendPlaneLine },
    { key: 'delete', label: 'Delete draft', copy: 'Permanently remove this draft.', Icon: RiDeleteBinLine, danger: true },
  ]
  if (exam.status === 'submitted') return [
    { key: 'return-draft', label: 'Return to draft', copy: 'Reopen teacher authoring before sealing.', Icon: RiArrowGoBackLine },
    { key: 'seal', label: 'Seal examination', copy: 'Freeze questions, options and eligible target classes.', Icon: RiShieldCheckLine },
  ]
  if (exam.status === 'sealed') return [
    { key: 'activate', label: 'Activate examination', copy: exam.rosterStatus === 'ready' ? 'Open this sealed paper for candidates.' : 'Candidate roster must be ready before activation.', Icon: RiPlayCircleLine, disabled: exam.rosterStatus !== 'ready' },
    { key: 'revision', label: 'Create revision', copy: 'Start a new editable revision from this sealed paper.', Icon: RiRefreshLine },
    { key: 'cancel', label: 'Cancel examination', copy: 'Cancel this sealed revision with an audit reason.', Icon: RiCloseCircleLine, danger: true },
  ]
  if (exam.status === 'active') return [
    { key: 'suspend', label: 'Suspend examination', copy: 'Temporarily pause the live examination.', Icon: RiPauseCircleLine },
    { key: 'close', label: 'Close examination', copy: 'End the live examination normally.', Icon: RiStopCircleLine },
    { key: 'cancel', label: 'Cancel examination', copy: 'Cancel the live examination with a reason.', Icon: RiCloseCircleLine, danger: true },
  ]
  if (exam.status === 'suspended') return [
    { key: 'resume', label: 'Resume examination', copy: 'Return the suspended examination to active.', Icon: RiPlayCircleLine },
    { key: 'close', label: 'Close examination', copy: 'Close the examination while suspended.', Icon: RiStopCircleLine },
    { key: 'cancel', label: 'Cancel examination', copy: 'Cancel the suspended examination with a reason.', Icon: RiCloseCircleLine, danger: true },
  ]
  if (exam.status === 'cancelled') return [
    { key: 'revision', label: 'Create revision', copy: 'Start a clean revision from this cancelled paper.', Icon: RiRefreshLine },
  ]
  return []
}

function LifecycleModal({ pending, reason, setReason, error, busy, onCancel, onConfirm }) {
  const copy = lifecycleCopy(pending.action)
  return createPortal(
    <div className="teacher-exam-confirm-backdrop" onMouseDown={(event) => { if (event.currentTarget === event.target && !busy) onCancel() }}>
      <section className={`teacher-exam-confirm-modal${copy.danger ? ' is-danger' : ''}`} role="alertdialog" aria-modal="true">
        <div className="teacher-exam-confirm-modal__heading"><span><copy.Icon size={22} /></span><div><h2>{copy.title}</h2><p>{copy.description}</p></div></div>
        <div className="teacher-exam-confirm-modal__exam"><span>Examination</span><strong>{pending.exam.title}</strong><small>{pending.exam.subjectName} · {pending.exam.assessmentName}</small></div>
        {copy.reason && <label className="admin-exam-reason"><span>Reason</span><textarea rows="3" value={reason} onChange={(event) => setReason(event.target.value)} placeholder={copy.reasonPlaceholder} /></label>}
        <p className="teacher-exam-confirm-modal__warning">{copy.warning}</p>
        {error && <Notice tone="danger">{error}</Notice>}
        <div className="teacher-exam-confirm-modal__actions"><button type="button" className="teacher-exam-confirm-modal__cancel" disabled={busy} onClick={onCancel}>Cancel</button><button type="button" className={`teacher-exam-confirm-modal__confirm${copy.danger ? ' is-danger' : ''}`} disabled={busy} onClick={onConfirm}>{busy ? 'Working…' : copy.confirm}</button></div>
      </section>
    </div>,
    document.body,
  )
}

function lifecycleCopy(action) {
  const entries = {
    submit: ['Submit this examination?', 'The paper will be validated and move to administrator review.', 'Submit for review', RiSendPlaneLine, false, false],
    delete: ['Delete this draft examination?', 'This permanently removes the draft paper.', 'Delete draft', RiDeleteBinLine, true, false],
    'return-draft': ['Return this examination to draft?', 'Teacher authoring will reopen for this submitted paper.', 'Return to draft', RiArrowGoBackLine, false, false],
    seal: ['Seal this examination?', 'Questions, options, component score and target classes will be frozen.', 'Seal examination', RiShieldCheckLine, false, false],
    revision: ['Create a new examination revision?', 'A new editable revision will be created without changing the historical revision.', 'Create revision', RiRefreshLine, false, false],
    activate: ['Activate this examination?', 'Candidates on the prepared roster will be able to start the exam.', 'Activate exam', RiPlayCircleLine, false, false],
    suspend: ['Suspend this examination?', 'Active execution will be paused until an administrator resumes it.', 'Suspend exam', RiPauseCircleLine, false, true],
    resume: ['Resume this examination?', 'The suspended examination will become active again.', 'Resume exam', RiPlayCircleLine, false, true],
    close: ['Close this examination?', 'This ends the operational lifecycle and preserves the completed paper.', 'Close exam', RiStopCircleLine, false, false],
    cancel: ['Cancel this examination?', 'Cancellation is permanent for this revision and requires an audit reason.', 'Cancel exam', RiCloseCircleLine, true, true],
  }
  const [title, description, confirm, Icon, danger, reason] = entries[action]
  return { title, description, confirm, Icon, danger, reason, reasonPlaceholder: action === 'resume' ? 'Optional note for resuming this exam.' : 'Explain why this lifecycle action is required.', warning: action === 'seal' ? 'Sealing freezes the executable paper. Further authoring requires a new revision.' : 'Weave will enforce the backend lifecycle rules and reject stale or invalid transitions.' }
}

function requiresReason(action) { return action === 'suspend' || action === 'cancel' }
function titleCase(value) { return String(value).replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()) }
function formatSelectionMode(mode) { return mode === 'manual' ? 'Manual selection' : 'Random selection' }
function formatDate(value) { if (!value) return '—'; const date = new Date(value); return Number.isNaN(date.getTime()) ? '—' : date.toLocaleDateString() }
function formatTime(value) { if (!value) return '—'; const date = new Date(value); return Number.isNaN(date.getTime()) ? '—' : date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' }) }
function statusTone(status) { if (status === 'active' || status === 'closed') return 'success'; if (status === 'draft') return 'warning'; if (status === 'cancelled' || status === 'suspended') return 'danger'; return 'info' }
