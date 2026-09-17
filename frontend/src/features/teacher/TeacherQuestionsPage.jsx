import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { RiArchiveLine, RiDeleteBinLine, RiEdit2Line, RiImageAddLine, RiMore2Line, RiRefreshLine, RiSearchLine } from '@remixicon/react'
import { Icon } from '../../shared/icons/Icon'
import { Notice, SelectControl, StatusBadge } from '../../shared/ui'
import './questions-page.css'
import './question-lifecycle-modal.css'

const PAGE_SIZE = 10
const LIFECYCLE_POPOVER_WIDTH = 320
const LIFECYCLE_POPOVER_GAP = 8
const LIFECYCLE_VIEWPORT_PADDING = 12

export function TeacherQuestionsPage({ state, dispatch, teacherData, gateway }) {
  const [query, setQuery] = useState('')
  const [bankId, setBankId] = useState('all')
  const [tab, setTab] = useState('all')
  const [page, setPage] = useState(1)
  const [lifecycleQuestionId, setLifecycleQuestionId] = useState(null)
  const [lifecyclePosition, setLifecyclePosition] = useState(null)
  const [lifecycleBusyId, setLifecycleBusyId] = useState(null)
  const [pendingLifecycleAction, setPendingLifecycleAction] = useState(null)
  const [lifecycleModalError, setLifecycleModalError] = useState('')
  const lifecycleRef = useRef(null)

  useEffect(() => {
    const preferredBank = state.staff.selectedBankId
    if (preferredBank && teacherData.banks.some((bank) => bank.id === preferredBank)) {
      setBankId(preferredBank)
      setPage(1)
    }
  }, [state.staff.selectedBankId, teacherData.banks])

  const counts = useMemo(() => ({
    all: teacherData.questions.length,
    single: teacherData.questions.filter((question) => question.type === 'Single choice').length,
    multiple: teacherData.questions.filter((question) => question.type === 'Multiple choice').length,
    archived: teacherData.questions.filter((question) => question.status === 'Archived').length,
  }), [teacherData.questions])

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return teacherData.questions.filter((question) => {
      if (bankId !== 'all' && question.bankId !== bankId) return false
      if (tab === 'single' && question.type !== 'Single choice') return false
      if (tab === 'multiple' && question.type !== 'Multiple choice') return false
      if (tab === 'archived' && question.status !== 'Archived') return false
      if (tab !== 'archived' && tab !== 'all' && question.status === 'Archived') return false
      if (!needle) return true
      return `${question.prompt} ${question.bankName} ${question.type}`.toLowerCase().includes(needle)
    })
  }, [bankId, query, tab, teacherData.questions])

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const visibleQuestions = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  useEffect(() => {
    if (page > pageCount) setPage(pageCount)
  }, [page, pageCount])

  const closeLifecycle = () => {
    setLifecycleQuestionId(null)
    setLifecyclePosition(null)
  }

  const closeLifecycleConfirmation = () => {
    if (lifecycleBusyId) return
    setPendingLifecycleAction(null)
    setLifecycleModalError('')
  }

  useEffect(() => {
    if (!lifecycleQuestionId) return undefined
    const closeOnOutsideClick = (event) => {
      if (!lifecycleRef.current?.contains(event.target)) closeLifecycle()
    }
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') closeLifecycle()
    }
    const closeOnViewportChange = () => closeLifecycle()
    document.addEventListener('pointerdown', closeOnOutsideClick)
    document.addEventListener('keydown', closeOnEscape)
    window.addEventListener('resize', closeOnViewportChange)
    window.addEventListener('scroll', closeOnViewportChange, true)
    return () => {
      document.removeEventListener('pointerdown', closeOnOutsideClick)
      document.removeEventListener('keydown', closeOnEscape)
      window.removeEventListener('resize', closeOnViewportChange)
      window.removeEventListener('scroll', closeOnViewportChange, true)
    }
  }, [lifecycleQuestionId])

  useEffect(() => {
    if (!pendingLifecycleAction) return undefined
    const closeOnEscape = (event) => {
      if (event.key === 'Escape' && !lifecycleBusyId) closeLifecycleConfirmation()
    }
    document.addEventListener('keydown', closeOnEscape)
    return () => document.removeEventListener('keydown', closeOnEscape)
  }, [pendingLifecycleAction, lifecycleBusyId])

  const setFilter = (setter) => (value) => {
    setter(value)
    setPage(1)
  }

  const editQuestion = (question) => {
    dispatch({
      type: 'staff',
      patch: {
        section: 'edit-question',
        selectedBankId: question.bankId,
        selectedQuestionId: question.id,
        editingQuestion: question,
      },
    })
  }

  const previewQuestion = (question) => {
    dispatch({
      type: 'staff',
      patch: {
        section: 'preview-question',
        selectedBankId: question.bankId,
        selectedQuestionId: question.id,
        editingQuestion: null,
      },
    })
  }

  const createQuestion = () => {
    const selectedBankId = bankId === 'all' ? teacherData.banks[0]?.id : bankId
    dispatch({ type: 'staff', patch: { section: 'create-question', selectedBankId, selectedQuestionId: null, editingQuestion: null } })
  }

  const requestLifecycleAction = (question, action) => {
    closeLifecycle()
    setLifecycleModalError('')
    setPendingLifecycleAction({ question, action })
  }

  const confirmLifecycleAction = async () => {
    if (!pendingLifecycleAction) return
    const { question, action } = pendingLifecycleAction
    setLifecycleModalError('')
    setLifecycleBusyId(question.id)
    try {
      if (action === 'archive') await gateway.questions.archiveQuestion(question.id)
      if (action === 'reactivate') await gateway.questions.reactivateQuestion(question.id)
      if (action === 'delete') await gateway.questions.deleteUnusedQuestion(question.id)
      await teacherData.refresh()
      setPendingLifecycleAction(null)
    } catch (error) {
      setLifecycleModalError(error.userMessage || `Weave could not ${action} this question.`)
    } finally {
      setLifecycleBusyId(null)
    }
  }

  const toggleLifecycle = (question, trigger) => {
    if (lifecycleQuestionId === question.id) return closeLifecycle()
    setLifecyclePosition(getLifecyclePopoverPosition(trigger))
    setLifecycleQuestionId(question.id)
  }

  const lifecycleConfirmation = pendingLifecycleAction ? getLifecycleConfirmationCopy(pendingLifecycleAction.action) : null
  const bankOptions = [{ value: 'all', label: 'All question banks' }, ...teacherData.banks.map((bank) => ({ value: bank.id, label: bank.name, description: `${bank.count || 0} questions` }))]

  return (
    <div className="teacher-reference-page teacher-questions-page">
      <div className="teacher-page-heading">
        <div>
          <div className="teacher-page-title-line">
            <span className="teacher-page-title-icon"><Icon name="fileText" size={27} /></span>
            <h1>Questions</h1>
          </div>
          <p>Browse and author questions inside the banks available to your current teaching scope.</p>
        </div>
        <button className="teacher-primary-action" type="button" disabled={teacherData.banks.length === 0} onClick={createQuestion}>
          <Icon name="plus" size={18} /> Add Question
        </button>
      </div>

      {teacherData.error && <Notice tone="danger">{teacherData.error}</Notice>}

      <div className="teacher-question-toolbar">
        <SelectControl label="Question bank filter" value={bankId} options={bankOptions} onChange={setFilter(setBankId)} />
        <label className="teacher-search-control teacher-search-control--grow">
          <RiSearchLine size={19} aria-hidden="true" />
          <input aria-label="Search questions" type="search" value={query} onChange={(event) => { setQuery(event.target.value); setPage(1) }} placeholder="Search questions..." />
        </label>
      </div>

      <nav className="teacher-tab-row" aria-label="Question filters">
        <TabButton label="All" value="all" current={tab} count={counts.all} onClick={setFilter(setTab)} />
        <TabButton label="Single Choice" value="single" current={tab} count={counts.single} onClick={setFilter(setTab)} />
        <TabButton label="Multiple Choice" value="multiple" current={tab} count={counts.multiple} onClick={setFilter(setTab)} />
        <TabButton label="Archived" value="archived" current={tab} count={counts.archived} onClick={setFilter(setTab)} />
      </nav>

      <section className="teacher-question-list" aria-busy={teacherData.loading} aria-label="Questions">
        <div className="teacher-question-list__header" aria-hidden="true">
          <span>Question</span><span>Bank</span><span>Type</span><span>Status</span><span>Version</span><span>Actions</span>
        </div>

        {visibleQuestions.map((question, index) => (
          <article className="teacher-question-row" key={question.id}>
            <button className="teacher-question-row__preview" type="button" aria-label={`Preview question: ${question.prompt}`} onClick={() => previewQuestion(question)} />
            <div className="teacher-question-row__question">
              <span className="teacher-question-row__number">{(page - 1) * PAGE_SIZE + index + 1}</span>
              <div>
                <h2>{question.prompt}</h2>
                {(question.image || question.options?.some((option) => option.image_asset_id)) && <small><RiImageAddLine size={15} aria-hidden="true" /> Includes media</small>}
              </div>
            </div>
            <span className="teacher-question-row__bank" title={question.bankName}>{question.bankName}</span>
            <span><span className="teacher-type-pill">{question.type}</span></span>
            <span><StatusBadge tone={question.status === 'Ready' ? 'success' : 'warning'}>{question.status}</StatusBadge></span>
            <span className="teacher-question-row__version">v{question.version}</span>
            <div className="teacher-question-row__actions">
              <button type="button" className="teacher-question-edit" disabled={question.status === 'Archived'} onClick={() => editQuestion(question)}>
                <RiEdit2Line size={15} /> Edit
              </button>
              <div ref={lifecycleQuestionId === question.id ? lifecycleRef : undefined} className="teacher-question-lifecycle">
                <button type="button" className="teacher-question-lifecycle__trigger" aria-label={`Question lifecycle for ${question.prompt}`} aria-haspopup="dialog" aria-expanded={lifecycleQuestionId === question.id} onClick={(event) => toggleLifecycle(question, event.currentTarget)}>
                  <RiMore2Line size={20} aria-hidden="true" />
                </button>
                {lifecycleQuestionId === question.id && lifecyclePosition && (
                  <div className="teacher-question-lifecycle__card" role="dialog" aria-label={`Lifecycle for ${question.prompt}`} data-placement={lifecyclePosition.placement} style={lifecyclePosition.style}>
                    <div className="teacher-question-lifecycle__heading"><strong>Question lifecycle</strong><span>{question.status}</span></div>
                    <p>{question.status === 'Archived' ? 'Reactivate this question to return it to active authoring.' : 'Archive this question without deleting its history or exam references.'}</p>
                    <button type="button" onClick={() => requestLifecycleAction(question, question.status === 'Archived' ? 'reactivate' : 'archive')}>
                      {question.status === 'Archived' ? <RiRefreshLine size={18} /> : <RiArchiveLine size={18} />}
                      <span><strong>{question.status === 'Archived' ? 'Reactivate question' : 'Archive question'}</strong><small>{question.status === 'Archived' ? 'Make it available for authoring again.' : 'Hide it from active authoring.'}</small></span>
                    </button>
                    <button type="button" className="teacher-question-lifecycle__delete" onClick={() => requestLifecycleAction(question, 'delete')}>
                      <RiDeleteBinLine size={18} /><span><strong>Delete permanently</strong><small>Only unused questions can be deleted. Used questions must be archived.</small></span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          </article>
        ))}

        {!teacherData.loading && visibleQuestions.length === 0 && <div className="teacher-question-list__empty"><strong>No matching questions</strong><p>Try another bank, filter, or search term.</p></div>}
        {teacherData.loading && <div className="teacher-question-list__empty">Loading questions…</div>}
      </section>

      <div className="teacher-question-pagination">
        <span>{filtered.length === 0 ? '0 questions' : `Showing ${(page - 1) * PAGE_SIZE + 1}–${Math.min(page * PAGE_SIZE, filtered.length)} of ${filtered.length} questions`}</span>
        <div>
          <button type="button" disabled={page === 1} onClick={() => setPage((current) => current - 1)} aria-label="Previous page">‹</button>
          <span>{page} / {pageCount}</span>
          <button type="button" disabled={page === pageCount} onClick={() => setPage((current) => current + 1)} aria-label="Next page">›</button>
        </div>
      </div>

      {pendingLifecycleAction && lifecycleConfirmation && typeof document !== 'undefined' && createPortal(
        <div className="teacher-lifecycle-confirm-backdrop" onMouseDown={(event) => { if (event.currentTarget === event.target) closeLifecycleConfirmation() }}>
          <section className={`teacher-lifecycle-confirm-modal${pendingLifecycleAction.action === 'delete' ? ' teacher-lifecycle-confirm-modal--danger' : ''}`} role="alertdialog" aria-modal="true" aria-labelledby="teacher-lifecycle-confirm-title" aria-describedby="teacher-lifecycle-confirm-description">
            <div className="teacher-lifecycle-confirm-modal__heading">
              <span className="teacher-lifecycle-confirm-modal__icon" aria-hidden="true">{pendingLifecycleAction.action === 'delete' ? <RiDeleteBinLine size={22} /> : pendingLifecycleAction.action === 'reactivate' ? <RiRefreshLine size={22} /> : <RiArchiveLine size={22} />}</span>
              <div><h2 id="teacher-lifecycle-confirm-title">{lifecycleConfirmation.title}</h2><p id="teacher-lifecycle-confirm-description">{lifecycleConfirmation.subtitle}</p></div>
            </div>
            <div className="teacher-lifecycle-confirm-modal__question"><span>Question</span><strong>{pendingLifecycleAction.question.prompt}</strong></div>
            <p className="teacher-lifecycle-confirm-modal__warning">{lifecycleConfirmation.warning}</p>
            {lifecycleModalError && <Notice tone="danger">{lifecycleModalError}</Notice>}
            <div className="teacher-lifecycle-confirm-modal__actions">
              <button type="button" className="teacher-lifecycle-confirm-modal__cancel" disabled={lifecycleBusyId === pendingLifecycleAction.question.id} onClick={closeLifecycleConfirmation}>Cancel</button>
              <button type="button" className={`teacher-lifecycle-confirm-modal__confirm${pendingLifecycleAction.action === 'delete' ? ' teacher-lifecycle-confirm-modal__confirm--danger' : ''}`} disabled={lifecycleBusyId === pendingLifecycleAction.question.id} onClick={confirmLifecycleAction}>{lifecycleBusyId === pendingLifecycleAction.question.id ? lifecycleConfirmation.busyLabel : lifecycleConfirmation.confirmLabel}</button>
            </div>
          </section>
        </div>,
        document.body,
      )}
    </div>
  )
}

function TabButton({ label, value, current, count, onClick }) {
  return <button type="button" className={current === value ? 'active' : ''} onClick={() => onClick(value)}>{label} <span>{count}</span></button>
}

function getLifecycleConfirmationCopy(action) {
  if (action === 'delete') return { title: 'Delete this question permanently?', subtitle: 'This action is only allowed for questions that have never been used by an exam.', warning: 'Permanent deletion cannot be undone. If this question has exam history, the backend will reject the deletion and you should archive it instead.', confirmLabel: 'Confirm delete', busyLabel: 'Deleting…' }
  if (action === 'reactivate') return { title: 'Reactivate this question?', subtitle: 'The question will return to active authoring.', warning: 'After reactivation, the question can be selected for future exam papers again, provided its question bank is active.', confirmLabel: 'Confirm reactivate', busyLabel: 'Reactivating…' }
  return { title: 'Archive this question?', subtitle: 'The question will be removed from active authoring without deleting its history.', warning: 'Existing exam references are preserved. You can reactivate the question later if the containing question bank remains active.', confirmLabel: 'Confirm archive', busyLabel: 'Archiving…' }
}

function getLifecyclePopoverPosition(trigger) {
  const viewportWidth = typeof window === 'undefined' ? 1280 : window.innerWidth
  const viewportHeight = typeof window === 'undefined' ? 800 : window.innerHeight
  const rect = trigger.getBoundingClientRect()
  const width = Math.min(LIFECYCLE_POPOVER_WIDTH, Math.max(240, viewportWidth - (LIFECYCLE_VIEWPORT_PADDING * 2)))
  const left = Math.max(LIFECYCLE_VIEWPORT_PADDING, Math.min(rect.right - width, viewportWidth - width - LIFECYCLE_VIEWPORT_PADDING))
  const availableBelow = Math.max(0, viewportHeight - rect.bottom - LIFECYCLE_POPOVER_GAP - LIFECYCLE_VIEWPORT_PADDING)
  const availableAbove = Math.max(0, rect.top - LIFECYCLE_POPOVER_GAP - LIFECYCLE_VIEWPORT_PADDING)
  const placement = availableBelow < 230 && availableAbove > availableBelow ? 'top' : 'bottom'
  const maxHeight = Math.max(150, Math.min(320, placement === 'top' ? availableAbove : availableBelow))
  if (placement === 'top') return { placement, style: { left, width, maxHeight, bottom: viewportHeight - rect.top + LIFECYCLE_POPOVER_GAP, top: 'auto' } }
  return { placement, style: { left, width, maxHeight, top: rect.bottom + LIFECYCLE_POPOVER_GAP, bottom: 'auto' } }
}
