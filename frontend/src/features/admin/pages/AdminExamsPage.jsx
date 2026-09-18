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
import { ExamCard, ExamViewToggle } from '../../../shared/exams/ExamCard'
import { examStatuses } from '../../../shared/exams/examPermissions'
import '../../../shared/exams/exam-workspace.css'
import { Icon } from '../../../shared/icons/Icon'
import { Notice, SelectControl } from '../../../shared/ui'

const PAGE_SIZE = 12
const POPOVER_WIDTH = 330
const VIEWPORT_GAP = 12
const tabs = examStatuses

export function AdminExamsPage({ adminData, gateway, onNavigate }) {
  const [view, setView] = useState('grid')
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('all')
  const [subjectId, setSubjectId] = useState('all')
  const [componentId, setComponentId] = useState('all')
  const [requestedPage, setPage] = useState(1)
  const [menuExamId, setMenuExamId] = useState(null)
  const [menuPosition, setMenuPosition] = useState(null)
  const [pending, setPending] = useState(null)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const menuRef = useRef(null)

  const closeMenu = () => {
    setMenuExamId(null)
    setMenuPosition(null)
  }

  useEffect(() => {
    if (!menuExamId) return undefined
    const closeOutside = (event) => {
      if (!menuRef.current?.contains(event.target) && !event.target.closest?.('.teacher-exam-lifecycle__trigger')) closeMenu()
    }
    const closeEscape = (event) => {
      if (event.key === 'Escape') closeMenu()
    }
    const closeViewport = (event) => { if (!menuRef.current?.contains(event.target) && !event.target.closest?.('.teacher-exam-lifecycle__trigger')) closeMenu() }
    document.addEventListener('pointerdown', closeOutside)
    document.addEventListener('keydown', closeEscape)
    window.addEventListener('resize', closeViewport)
    window.addEventListener('scroll', closeViewport, true)
    return () => {
      document.removeEventListener('pointerdown', closeOutside)
      document.removeEventListener('keydown', closeEscape)
      window.removeEventListener('resize', closeViewport)
      window.removeEventListener('scroll', closeViewport, true)
    }
  }, [menuExamId])

  useEffect(() => {
    if (!pending) return undefined
    const closeEscape = (event) => {
      if (event.key === 'Escape' && !busy) {
        setPending(null)
        setReason('')
        setError('')
      }
    }
    document.addEventListener('keydown', closeEscape)
    return () => document.removeEventListener('keydown', closeEscape)
  }, [pending, busy])

  const counts = useMemo(() => {
    const result = Object.fromEntries(tabs.map((item) => [item, 0]))
    result.all = adminData.exams.length
    adminData.exams.forEach((exam) => {
      if (result[exam.status] !== undefined) result[exam.status] += 1
    })
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
  const page = Math.min(requestedPage, pageCount)
  const visible = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)


  const setFilter = (setter) => (value) => {
    setter(value)
    setPage(1)
  }

  const toggleMenu = (exam, trigger) => {
    if (menuExamId === exam.id) {
      closeMenu()
      return
    }
    setMenuPosition(getPopoverPosition(trigger))
    setMenuExamId(exam.id)
  }

  const request = (exam, action) => {
    closeMenu()
    setPending({ exam, action })
    setReason('')
    setError('')
  }

  const cancelPending = () => {
    if (busy) return
    setPending(null)
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

  const subjectOptions = [
    { value: 'all', label: 'All subjects' },
    ...adminData.subjects.map((subject) => ({
      value: subject.id,
      label: subject.name,
      description: subject.code || undefined,
    })),
  ]
  const componentOptions = [
    { value: 'all', label: 'All components' },
    ...adminData.assessmentComponents.map((component) => ({
      value: component.id,
      label: component.name,
      description: `${component.maximumScore} marks`,
    })),
  ]

  return (
    <div className="teacher-reference-page teacher-exams-page admin-exams-page">
      <div className="teacher-page-heading teacher-exams-heading">
        <div>
          <div className="teacher-page-title-line">
            <span className="teacher-page-title-icon"><Icon name="calendar" size={27} /></span>
            <h1>Examinations</h1>
          </div>
          <p>Create papers and control the full administrator examination lifecycle from review through closure.</p>
        </div>
        <button className="teacher-primary-action" type="button" onClick={() => onNavigate('create-exam', { selectedExamId: null })}>
          <RiAddLine size={18} /> Create Exam
        </button>
      </div>

      {adminData.error && <Notice tone="danger">{adminData.error}</Notice>}
      {adminData.warning && <Notice tone="warning">{adminData.warning}</Notice>}

      <nav className="teacher-tab-row teacher-exam-tabs" aria-label="Exam status filters">
        {tabs.map((tab) => (
          <button key={tab} type="button" className={status === tab ? 'active' : ''} aria-current={status === tab ? 'page' : undefined} onClick={() => setFilter(setStatus)(tab)}>
            {titleCase(tab)} <span>{counts[tab] || 0}</span>
          </button>
        ))}
      </nav>

      <div className="teacher-exam-filters teacher-exam-filters--refined exam-filters">
        <label className="teacher-search-control teacher-search-control--grow">
          <RiSearchLine size={18} aria-hidden="true" />
          <input aria-label="Search examinations" type="search" value={query} onChange={(event) => { setQuery(event.target.value); setPage(1) }} placeholder="Search by title, subject, or assessment..." />
        </label>
        <SelectControl label="Exam subject filter" value={subjectId} options={subjectOptions} onChange={setFilter(setSubjectId)} />
        <SelectControl label="Assessment component filter" value={componentId} options={componentOptions} onChange={setFilter(setComponentId)} />
        <ExamViewToggle value={view} onChange={setView} />
      </div>

      <section className={`exam-collection exam-collection--${view}`} aria-label="School examinations" aria-busy={adminData.loading}>
        {visible.map((exam) => (
          <ExamCard key={exam.id} exam={exam}
            onOpen={() => onNavigate('create-exam', { selectedExamId: exam.id })}
            onEdit={exam.status === 'draft' ? () => onNavigate('create-exam', { selectedExamId: exam.id }) : undefined}>
              <div className="teacher-exam-lifecycle" ref={menuExamId === exam.id ? menuRef : undefined}>
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
                  <AdminLifecycleMenu
                    exam={exam}
                    style={menuPosition}
                    menuRef={menuRef}
                    onOpen={() => { closeMenu(); onNavigate('create-exam', { selectedExamId: exam.id }) }}
                    onEdit={() => { closeMenu(); onNavigate('create-exam', { selectedExamId: exam.id }) }}
                    onAction={(action) => request(exam, action)}
                  />
                )}
              </div>
          </ExamCard>
        ))}

        {!adminData.loading && visible.length === 0 && (
          <div className="teacher-exam-collection__empty">
            <span><Icon name="calendar" size={24} /></span>
            <strong>{adminData.exams.length ? 'No examinations match these filters' : 'No examinations yet'}</strong>
            <p>{adminData.exams.length ? 'Adjust the search or lifecycle filters.' : 'Create the first draft examination for this school.'}</p>
          </div>
        )}
        {adminData.loading && <div className="teacher-exam-collection__empty"><strong>Loading examinations…</strong></div>}

        <div className="teacher-exam-pagination teacher-exam-pagination--refined">
          <span>{filtered.length === 0 ? '0 exams' : `Showing ${(page - 1) * PAGE_SIZE + 1}–${Math.min(page * PAGE_SIZE, filtered.length)} of ${filtered.length} exams`}</span>
          <div>
            <button type="button" aria-label="Previous page" disabled={page === 1} onClick={() => setPage(page - 1)}>‹</button>
            <span>{page} / {pageCount}</span>
            <button type="button" aria-label="Next page" disabled={page === pageCount} onClick={() => setPage(page + 1)}>›</button>
          </div>
        </div>
      </section>

      {pending && <LifecycleModal pending={pending} reason={reason} setReason={setReason} error={error} busy={busy} onCancel={cancelPending} onConfirm={confirm} />}
    </div>
  )
}

function AdminLifecycleMenu({ exam, style, menuRef, onOpen, onEdit, onAction }) {
  const actions = lifecycleActions(exam)
  return createPortal(
    <div ref={menuRef} className="teacher-exam-lifecycle__menu admin-exam-lifecycle__menu" role="dialog" aria-label={`Lifecycle for ${exam.title}`} style={style}>
      <div className="teacher-exam-lifecycle__heading">
        <div><strong>Exam lifecycle</strong><span>{exam.statusLabel}</span></div>
        <small>v{exam.authoringVersion || 1}</small>
      </div>
      <button type="button" onClick={onOpen}><Icon name="exam" size={18} /><span><strong>{['closing', 'cancelling'].includes(exam.status) ? 'View progress' : 'View examination'}</strong><small>Open the paper and its current settings.</small></span></button>
      {exam.status === 'draft' && (
        <button type="button" onClick={onEdit}><RiEdit2Line size={18} /><span><strong>Edit draft</strong><small>Update metadata, timing and delivery settings.</small></span></button>
      )}
      {exam.status === 'draft' && <button type="button" onClick={onEdit}><Icon name="users" size={18} /><span><strong>Change lead</strong><small>Assign an eligible teacher in authoring ownership.</small></span></button>}
      {actions.map((action) => {
        const ActionIcon = action.Icon
        return (
          <button key={action.key} type="button" disabled={action.disabled} className={action.danger ? 'teacher-exam-lifecycle__danger' : ''} onClick={() => onAction(action.key)}>
            <ActionIcon size={18} />
            <span><strong>{action.label}</strong><small>{action.copy}</small></span>
          </button>
        )
      })}
      {!actions.length && exam.status !== 'draft' && (
        <div className="teacher-exam-lifecycle__info"><Icon name="info" size={18} /><p>{['closing', 'cancelling'].includes(exam.status) ? 'Finalization is in progress. Reverse actions are unavailable.' : 'This examination is read-only.'}</p></div>
      )}
    </div>, document.body
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
  const ModalIcon = copy.Icon
  return createPortal(
    <div className="teacher-exam-confirm-backdrop" onMouseDown={(event) => { if (event.currentTarget === event.target && !busy) onCancel() }}>
      <section className={`teacher-exam-confirm-modal${copy.danger ? ' is-danger' : ''}`} role="alertdialog" aria-modal="true" aria-labelledby="admin-exam-confirm-title" aria-describedby="admin-exam-confirm-description">
        <div className="teacher-exam-confirm-modal__heading">
          <span><ModalIcon size={22} /></span>
          <div><h2 id="admin-exam-confirm-title">{copy.title}</h2><p id="admin-exam-confirm-description">{copy.description}</p></div>
        </div>
        <div className="teacher-exam-confirm-modal__exam"><span>Examination</span><strong>{pending.exam.title}</strong><small>{pending.exam.subjectName} · {pending.exam.assessmentName}</small></div>
        {copy.reason && (
          <label className="admin-exam-reason"><span>Reason {requiresReason(pending.action) ? '' : '(optional)'}</span><textarea rows="3" value={reason} onChange={(event) => setReason(event.target.value)} placeholder={copy.reasonPlaceholder} /></label>
        )}
        <p className="teacher-exam-confirm-modal__warning">{copy.warning}</p>
        {error && <Notice tone="danger">{error}</Notice>}
        <div className="teacher-exam-confirm-modal__actions">
          <button type="button" className="teacher-exam-confirm-modal__cancel" disabled={busy} onClick={onCancel}>Cancel</button>
          <button type="button" className={`teacher-exam-confirm-modal__confirm${copy.danger ? ' is-danger' : ''}`} disabled={busy} onClick={onConfirm}>{busy ? 'Working…' : copy.confirm}</button>
        </div>
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
  const [title, description, confirm, IconComponent, danger, reason] = entries[action]
  return {
    title,
    description,
    confirm,
    Icon: IconComponent,
    danger,
    reason,
    reasonPlaceholder: action === 'resume' ? 'Optional note for resuming this exam.' : 'Explain why this lifecycle action is required.',
    warning: action === 'seal'
      ? 'Sealing freezes the executable paper. Further authoring requires a new revision.'
      : 'Weave will enforce the backend lifecycle rules and reject stale or invalid transitions.',
  }
}

function getPopoverPosition(trigger) {
  const rect = trigger.getBoundingClientRect()
  const width = Math.min(POPOVER_WIDTH, Math.max(260, window.innerWidth - VIEWPORT_GAP * 2))
  const left = Math.max(VIEWPORT_GAP, Math.min(rect.right - width, window.innerWidth - width - VIEWPORT_GAP))
  const below = Math.max(0, window.innerHeight - rect.bottom - VIEWPORT_GAP)
  const above = Math.max(0, rect.top - VIEWPORT_GAP)
  const placeAbove = below < 300 && above > below
  const maxHeight = Math.max(220, Math.min(520, placeAbove ? above : below))
  return placeAbove
    ? { position: 'fixed', width, left, maxHeight, bottom: window.innerHeight - rect.top + 8, top: 'auto', right: 'auto' }
    : { position: 'fixed', width, left, maxHeight, top: rect.bottom + 8, bottom: 'auto', right: 'auto' }
}

function requiresReason(action) { return action === 'suspend' || action === 'cancel' }
function titleCase(value) { return String(value).replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()) }

