import { useEffect, useState } from 'react'
import { RiSearchLine } from '@remixicon/react'
import { Notice } from '../ui'
import { FormattedText } from '../ui/FormattedText'

export function ManualQuestionPicker({
  bankId,
  exam,
  gateway,
  selectedIds,
  onChange,
  disabled,
  onBusyChange,
  onSaved,
  actorId,
  canManageAllSelections = false,
}) {
  const [resource, setResource] = useState({ loading: true, questions: [], selections: [], version: null, error: '' })
  const [query, setQuery] = useState('')
  const [selectedOnly, setSelectedOnly] = useState(false)
  const [busy, setBusy] = useState(false)
  const [previews, setPreviews] = useState({})
  const [retry, setRetry] = useState(0)
  const [stagedAddIds, setStagedAddIds] = useState([])
  const examId = exam?.id
  const limit = Number(exam?.questionCount)
  const contributionMode = Boolean(examId && !canManageAllSelections)
  const contributionStorageKey = contributionMode && actorId
    ? `weave-cbt:manual-contribution:${examId}:${actorId}:${bankId}`
    : ''

  useEffect(() => {
    let cancelled = false
    Promise.all([
      gateway.questions.listQuestionsForBank(bankId, { include_archived: Boolean(examId) }),
      examId ? gateway.exams.listManualQuestions(examId) : Promise.resolve([]),
      examId ? gateway.exams.getExam(examId) : Promise.resolve(null),
    ]).then(([questions, selections, current]) => {
      if (cancelled) return

      const persistedIds = new Set(selections.map((row) => row.question_id))
      const activeQuestionIds = new Set(questions.filter((question) => question.is_active).map((question) => question.id))
      const restored = contributionMode
        ? readStagedAdditions(contributionStorageKey).filter((questionId) => activeQuestionIds.has(questionId) && !persistedIds.has(questionId))
        : []

      setStagedAddIds(restored)
      persistStagedAdditions(contributionStorageKey, restored)
      setResource({ loading: false, questions, selections, version: current?.authoring_version ?? current?.authoringVersion ?? null, error: '' })
    }).catch((error) => {
      if (!cancelled) setResource((previous) => ({ ...previous, loading: false, error: error.userMessage || 'Could not load the question bank. Please retry.' }))
    })
    return () => { cancelled = true }
  }, [bankId, contributionMode, contributionStorageKey, examId, gateway, retry])

  const persistedIds = examId ? resource.selections.map((row) => row.question_id) : []
  const ids = examId
    ? contributionMode
      ? [...persistedIds, ...stagedAddIds.filter((questionId) => !persistedIds.includes(questionId))]
      : persistedIds
    : selectedIds
  const selected = new Set(ids)
  const staged = new Set(stagedAddIds)
  const selectionByQuestion = new Map(resource.selections.map((row) => [row.question_id, row]))
  const visible = resource.questions.filter((question) => (question.is_active || selected.has(question.id)) && (!selectedOnly || selected.has(question.id)) && question.prompt.toLowerCase().includes(query.trim().toLowerCase()))
  const stagedCount = stagedAddIds.length
  const selectionOverLimit = Number.isFinite(limit) && ids.length > limit

  const canRemoveSelectedQuestion = (questionId) => {
    if (!examId || canManageAllSelections || staged.has(questionId)) return true
    const selection = selectionByQuestion.get(questionId)
    return Boolean(actorId && selection?.added_by_actor_id && String(selection.added_by_actor_id) === String(actorId))
  }

  const stageAdditions = (nextIds) => {
    setStagedAddIds(nextIds)
    persistStagedAdditions(contributionStorageKey, nextIds)
  }

  const toggle = async (questionId) => {
    if (disabled || busy) return
    if (selected.has(questionId) && !canRemoveSelectedQuestion(questionId)) return
    if (!examId) {
      onChange(selected.has(questionId) ? ids.filter((id) => id !== questionId) : [...ids, questionId])
      return
    }

    if (contributionMode && staged.has(questionId)) {
      stageAdditions(stagedAddIds.filter((id) => id !== questionId))
      return
    }

    if (contributionMode && !selected.has(questionId)) {
      stageAdditions([...stagedAddIds, questionId])
      return
    }

    setBusy(true)
    onBusyChange?.(true)
    try {
      const removing = selected.has(questionId)
      const updated = removing
        ? await gateway.exams.removeManualQuestion(examId, questionId, resource.version)
        : await gateway.exams.addManualQuestions(examId, [questionId], resource.version)
      // Lead/admin mutations and removals of already-saved contributor questions are committed immediately.
      setResource((previous) => ({
        ...previous,
        version: updated.authoring_version ?? updated.authoringVersion ?? previous.version,
        error: '',
        selections: removing
          ? previous.selections.filter((row) => row.question_id !== questionId)
          : [...previous.selections, { question_id: questionId, added_by_actor_id: actorId }],
      }))
      await onSaved?.()
    } catch (error) {
      setResource((previous) => ({ ...previous, error: error.userMessage || 'Could not update the selection. Reload the questions before trying again.' }))
    } finally {
      setBusy(false)
      onBusyChange?.(false)
    }
  }

  const saveContribution = async () => {
    if (!contributionMode || disabled || busy || resource.loading || resource.error || !stagedCount || selectionOverLimit) return
    setBusy(true)
    onBusyChange?.(true)
    try {
      const expectedVersion = resource.version ?? exam?.authoringVersion ?? exam?.authoring_version ?? 1
      const updated = await gateway.exams.addManualQuestions(examId, stagedAddIds, expectedVersion)
      const committedIds = [...stagedAddIds]
      setResource((previous) => ({
        ...previous,
        version: updated.authoring_version ?? updated.authoringVersion ?? previous.version,
        error: '',
        selections: [
          ...previous.selections,
          ...committedIds.map((questionId) => ({ question_id: questionId, added_by_actor_id: actorId })),
        ],
      }))
      stageAdditions([])
      await onSaved?.()
    } catch (error) {
      setResource((previous) => ({
        ...previous,
        error: error.userMessage || 'Could not save your contribution. Your staged questions are still on this device; reload the questions and try again.',
      }))
    } finally {
      setBusy(false)
      onBusyChange?.(false)
    }
  }

  return (
    <div className="exam-manual-picker" aria-busy={resource.loading || busy}>
      <div className="exam-manual-picker__heading"><div><h3>Choose questions</h3><p>{examId
        ? contributionMode
          ? 'New picks are kept on this device until you save your contribution. Removing one of your already-saved questions is applied immediately.'
          : 'Changes to this selection are saved immediately.'
        : 'Your selected questions will be added when you create the draft.'}</p></div><strong>{ids.length} / {limit} selected</strong></div>
      <div className="exam-manual-picker__tools">
        <label className="teacher-search-control"><RiSearchLine size={17} /><input aria-label="Search bank questions" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search this question bank" /></label>
        <button type="button" className="exam-text-action" aria-pressed={selectedOnly} onClick={() => setSelectedOnly(!selectedOnly)}>{selectedOnly ? 'Show all' : 'Selected only'}</button>
      </div>
      {resource.error && <div className="exam-manual-picker__error"><Notice tone="danger">{resource.error}</Notice> <button type="button" className="exam-text-action" disabled={busy} onClick={() => { setResource((previous) => ({ ...previous, loading: true, error: '' })); setRetry((value) => value + 1) }}>Reload questions</button></div>}
      {resource.loading ? <p role="status">Loading bank questions…</p> : <div className="exam-manual-picker__list">
        {visible.map((question) => {
          const selectionLocked = selected.has(question.id) && !canRemoveSelectedQuestion(question.id)
          return <div key={question.id} className={`exam-manual-question${selected.has(question.id) ? ' is-selected' : ''}`}>
            <label>
              <input type="checkbox" aria-label={`Select question: ${question.prompt}`} checked={selected.has(question.id)} disabled={disabled || busy || Boolean(resource.error) || selectionLocked || (!selected.has(question.id) && (!question.is_active || ids.length >= limit))} onChange={() => toggle(question.id)} />
              <div><FormattedText text={question.prompt} /><small>{question.question_type.replaceAll('_', ' ')}{!question.is_active ? ' · Archived — remove before submission' : ''}{staged.has(question.id) ? ' · Not saved yet' : ''}</small></div>
            </label>
            <details onToggle={(event) => { const open = event.currentTarget.open; setPreviews((previous) => ({ ...previous, [question.id]: open })) }}><summary>Preview question</summary>
              {question.instruction && <FormattedText text={question.instruction} />}
              {previews[question.id] && question.image_asset_id && <QuestionImage gateway={gateway} questionId={question.id} />}
              <ol>{question.options.map((option) => <li key={option.id}><FormattedText text={option.text} />{option.is_correct && <small>Correct answer</small>}{previews[question.id] && option.image_asset_id && <QuestionImage gateway={gateway} questionId={question.id} optionId={option.id} />}</li>)}</ol>
            </details>
          </div>
        })}
        {!visible.length && <p>{resource.questions.length ? 'No questions match this view.' : 'This bank has no available questions.'}</p>}
      </div>}
      {contributionMode && (
        <div className="exam-manual-picker__tools">
          <p role="status">{stagedCount
            ? `${stagedCount} question${stagedCount === 1 ? '' : 's'} waiting to be saved.`
            : 'No unsaved question additions.'}</p>
          <button type="button" className="teacher-primary-action" disabled={disabled || busy || Boolean(resource.error) || !stagedCount || selectionOverLimit} onClick={saveContribution}>
            {busy ? 'Saving contribution...' : 'Save contribution'}
          </button>
        </div>
      )}
      <p className="exam-section-note">Select {limit} questions before submitting the paper for review. {selectionOverLimit ? 'Remove the extra staged selections to match the question count.' : ''}</p>
    </div>
  )
}

function readStagedAdditions(storageKey) {
  if (!storageKey || typeof window === 'undefined') return []
  try {
    const parsed = JSON.parse(window.localStorage.getItem(storageKey) || '{}')
    return Array.isArray(parsed.questionIds) ? [...new Set(parsed.questionIds.filter(Boolean).map(String))] : []
  } catch {
    return []
  }
}

function persistStagedAdditions(storageKey, questionIds) {
  if (!storageKey || typeof window === 'undefined') return
  try {
    if (questionIds.length) {
      window.localStorage.setItem(storageKey, JSON.stringify({ questionIds }))
    } else {
      window.localStorage.removeItem(storageKey)
    }
  } catch {
    // Local storage is only a resilience layer. The in-memory draft still works for this page visit.
  }
}

function QuestionImage({ gateway, questionId, optionId }) {
  const [url, setUrl] = useState('')
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    let cancelled = false
    let objectUrl
    const request = optionId ? gateway.questions.getQuestionOptionImage(questionId, optionId) : gateway.questions.getQuestionImage(questionId)
    request.then((blob) => {
      if (!cancelled) { objectUrl = URL.createObjectURL(blob); setUrl(objectUrl) }
    }).catch(() => { if (!cancelled) setFailed(true) })
    return () => { cancelled = true; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [gateway, questionId, optionId])
  if (failed) return <p role="status">Image could not be loaded.</p>
  return url ? <img src={url} alt={optionId ? 'Answer option illustration' : 'Question illustration'} /> : <span>Loading image…</span>
}
