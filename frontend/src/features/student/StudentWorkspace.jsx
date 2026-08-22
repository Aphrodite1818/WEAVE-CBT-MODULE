import { useEffect, useMemo, useState } from 'react'
import { LeafLogo, Metric, Notice, PageTitle, Panel, StatusBadge } from '../../components/ui'

export function StudentWorkspace({ exam, resolution, gateway, dispatch, returnToSignIn }) {
  const [attempt, setAttempt] = useState(null)
  const [attemptError, setAttemptError] = useState('')
  const [savingByQuestion, setSavingByQuestion] = useState({})
  const [submitted, setSubmitted] = useState(null)
  const questions = useMemo(() => attempt?.questions || [], [attempt])
  const current = questions[exam.index] || questions[0]
  const answeredCount = useMemo(
    () => questions.filter((question) => question.selected_option_ids.length > 0).length,
    [questions],
  )

  useEffect(() => {
    if (exam.stage !== 'active') return undefined
    let cancelled = false
    gateway.attempts
      .getCurrentAttempt()
      .then((currentAttempt) => {
        if (!cancelled) setAttempt(currentAttempt)
      })
      .catch(() => null)
    return () => {
      cancelled = true
    }
  }, [exam.stage, gateway])

  if (exam.stage === 'submitted' || submitted) {
    return (
      <main className="auth-shell">
        <section className="submission-card">
          <StatusBadge tone="success">Submitted</StatusBadge>
          <h1>Submission received</h1>
          <p>Your Leaf session has ended. Answer editing is now closed.</p>
          {submitted && <Metric label="Score" value={`${submitted.raw_score} / ${submitted.raw_max_score}`} helper={`${submitted.percentage}%`} />}
          <button className="button button--primary" onClick={returnToSignIn}>Return to sign in</button>
        </section>
      </main>
    )
  }

  if (exam.stage === 'active') {
    if (!attempt || !current) {
      return (
        <main className="exam-shell">
          <header className="exam-header">
            <LeafLogo />
            <div>
              <strong>{resolution?.exam?.title || 'Current examination'}</strong>
              <span>Preparing questions</span>
            </div>
          </header>
          <section className="review-state">
            <Panel title="Loading exam">
              <p>Leaf is opening your active attempt.</p>
              {attemptError && <Notice tone="danger">{attemptError}</Notice>}
            </Panel>
          </section>
        </main>
      )
    }

    return (
      <main className="exam-shell">
        <header className="exam-header">
          <LeafLogo />
          <div>
            <strong>{attempt.exam_title}</strong>
            <span>{attempt.is_makeup ? 'Makeup examination' : 'Normal examination'}</span>
          </div>
          <div className="exam-timer"><span>Remaining</span><strong>{formatRemaining(attempt.remaining_seconds)}</strong></div>
        </header>
        <section className="review-state">
          <PageTitle title={`Question ${exam.index + 1}`} subtitle={current.question_type.replaceAll('_', ' ')} />
          <Panel title={current.prompt}>
            <div className="options-list">
              {current.options.map((option) => (
                <label key={option.id} className={`option-row ${current.selected_option_ids.includes(option.id) ? 'selected' : ''}`}>
                  <input
                    type="radio"
                    checked={current.selected_option_ids.includes(option.id)}
                    onChange={() => saveAnswer({ question: current, optionId: option.id, gateway, setAttempt, setSavingByQuestion, setAttemptError })}
                  />
                  <span>{option.position}</span>
                  <strong>{option.text}</strong>
                </label>
              ))}
            </div>
          </Panel>
          <div className="toolbar">
            <button className="button button--secondary" onClick={() => dispatch({ type: 'exam', patch: { index: Math.max(0, exam.index - 1) } })}>Previous</button>
            <button className="button button--secondary" onClick={() => dispatch({ type: 'exam', patch: { index: Math.min(questions.length - 1, exam.index + 1) } })}>Next</button>
            <button className="button button--primary" onClick={() => submitAttempt({ gateway, setSubmitted, dispatch, setAttemptError })}>Submit</button>
          </div>
          <Metric label="Answered" value={`${answeredCount} / ${questions.length}`} helper={savingByQuestion[current.id] || 'Saved'} />
          {attemptError && <Notice tone="danger">{attemptError}</Notice>}
        </section>
      </main>
    )
  }

  const unavailable = resolution?.state === 'waiting_for_activation'
  return (
    <main className="auth-shell">
      <section className="student-lobby">
        <StatusBadge tone={unavailable ? 'warning' : 'success'}>{resolution?.state?.replaceAll('_', ' ') || 'Resolved'}</StatusBadge>
        <h1>{resolution?.exam?.title || 'Current examination'}</h1>
        <Notice>Leaf resolved your examination from the local CBT backend.</Notice>
        {attemptError && <Notice tone="danger">{attemptError}</Notice>}
        <button
          className="button button--primary"
          disabled={unavailable}
          onClick={() => startAttempt({ gateway, setAttempt, dispatch, setAttemptError })}
        >
          Start Exam
        </button>
      </section>
    </main>
  )
}

async function startAttempt({ gateway, setAttempt, dispatch, setAttemptError }) {
  setAttemptError('')
  try {
    const attempt = await gateway.attempts.startCurrentAttempt()
    setAttempt(attempt)
    dispatch({ type: 'exam', patch: { stage: 'active', index: 0 } })
  } catch (error) {
    setAttemptError(error.userMessage || 'Leaf could not start this attempt.')
  }
}

async function saveAnswer({ question, optionId, gateway, setAttempt, setSavingByQuestion, setAttemptError }) {
  const selectedOptionIds = [optionId]
  const mutationSequence = question.mutation_sequence + 1
  setAttemptError('')
  setSavingByQuestion((current) => ({ ...current, [question.id]: 'Saving...' }))
  setAttempt((currentAttempt) => ({
    ...currentAttempt,
    questions: currentAttempt.questions.map((item) =>
      item.id === question.id ? { ...item, selected_option_ids: selectedOptionIds, mutation_sequence: mutationSequence } : item,
    ),
  }))

  try {
    const saved = await gateway.attempts.saveCurrentAnswer(question.id, {
      mutation_sequence: mutationSequence,
      selected_option_ids: selectedOptionIds,
      is_flagged: question.is_flagged,
    })
    setAttempt((currentAttempt) => ({
      ...currentAttempt,
      remaining_seconds: saved.remaining_seconds,
      questions: currentAttempt.questions.map((item) =>
        item.id === question.id
          ? { ...item, selected_option_ids: saved.selected_option_ids, mutation_sequence: saved.mutation_sequence, is_flagged: saved.is_flagged }
          : item,
      ),
    }))
    setSavingByQuestion((current) => ({ ...current, [question.id]: 'Saved' }))
  } catch (error) {
    setSavingByQuestion((current) => ({ ...current, [question.id]: 'Not saved' }))
    setAttemptError(error.userMessage || 'That answer is visible here, but it has not safely saved yet.')
  }
}

async function submitAttempt({ gateway, setSubmitted, dispatch, setAttemptError }) {
  setAttemptError('')
  try {
    const result = await gateway.attempts.submitCurrentAttempt()
    setSubmitted(result)
    dispatch({ type: 'exam', patch: { stage: 'submitted' } })
  } catch (error) {
    setAttemptError(error.userMessage || 'Leaf could not submit the attempt.')
  }
}

function formatRemaining(seconds) {
  const safe = Math.max(0, Number(seconds) || 0)
  const minutes = Math.floor(safe / 60)
  const remainder = safe % 60
  return `${minutes}:${String(remainder).padStart(2, '0')}`
}
