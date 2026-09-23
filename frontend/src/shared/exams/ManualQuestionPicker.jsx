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
  const examId = exam?.id
  const limit = Number(exam?.questionCount)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      gateway.questions.listQuestionsForBank(bankId, { include_archived: Boolean(examId) }),
      examId ? gateway.exams.listManualQuestions(examId) : Promise.resolve([]),
      examId ? gateway.exams.getExam(examId) : Promise.resolve(null),
    ]).then(([questions, selections, current]) => {
      if (!cancelled) setResource({ loading: false, questions, selections, version: current?.authoring_version, error: '' })
    }).catch((error) => {
      if (!cancelled) setResource((previous) => ({ ...previous, loading: false, error: error.userMessage || 'Could not load the question bank. Please retry.' }))
    })
    return () => { cancelled = true }
  }, [bankId, examId, gateway, retry])

  const ids = examId ? resource.selections.map((row) => row.question_id) : selectedIds
  const selected = new Set(ids)
  const selectionByQuestion = new Map(resource.selections.map((row) => [row.question_id, row]))
  const visible = resource.questions.filter((question) => (question.is_active || selected.has(question.id)) && (!selectedOnly || selected.has(question.id)) && question.prompt.toLowerCase().includes(query.trim().toLowerCase()))

  const canRemoveSelectedQuestion = (questionId) => {
    if (!examId || canManageAllSelections) return true
    const selection = selectionByQuestion.get(questionId)
    return Boolean(actorId && selection?.added_by_actor_id && String(selection.added_by_actor_id) === String(actorId))
  }

  const toggle = async (questionId) => {
    if (disabled || busy) return
    if (selected.has(questionId) && !canRemoveSelectedQuestion(questionId)) return
    if (!examId) {
      onChange(selected.has(questionId) ? ids.filter((id) => id !== questionId) : [...ids, questionId])
      return
    }
    setBusy(true)
    onBusyChange(true)
    try {
      const removing = selected.has(questionId)
      const updated = removing
        ? await gateway.exams.removeManualQuestion(examId, questionId, resource.version)
        : await gateway.exams.addManualQuestions(examId, [questionId], resource.version)
      // The mutation is already committed; reflect it before refreshing surrounding data.
      setResource((previous) => ({
        ...previous,
        version: updated.authoring_version,
        error: '',
        selections: removing
          ? previous.selections.filter((row) => row.question_id !== questionId)
          : [...previous.selections, { question_id: questionId, added_by_actor_id: actorId }],
      }))
      await onSaved()
    } catch (error) {
      setResource((previous) => ({ ...previous, error: error.userMessage || 'Could not update the selection. Reload the questions before trying again.' }))
    } finally {
      setBusy(false)
      onBusyChange(false)
    }
  }

  return (
    <div className="exam-manual-picker" aria-busy={resource.loading || busy}>
      <div className="exam-manual-picker__heading"><div><h3>Choose questions</h3><p>{examId ? 'Changes to this selection are saved immediately.' : 'Your selected questions will be added when you create the draft.'}</p></div><strong>{ids.length} / {limit} selected</strong></div>
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
              <div><FormattedText text={question.prompt} /><small>{question.question_type.replaceAll('_', ' ')}{!question.is_active ? ' · Archived — remove before submission' : ''}</small></div>
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
      <p className="exam-section-note">Select {limit} questions before submitting the paper for review. {ids.length > limit ? 'Remove the extra selections to match the question count.' : ''}</p>
    </div>
  )
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
