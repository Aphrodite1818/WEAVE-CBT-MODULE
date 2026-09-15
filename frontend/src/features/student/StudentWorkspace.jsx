import { useEffect, useMemo, useState } from 'react'
import { Metric, Notice, StatusBadge, WeaveLogo } from '../../shared/ui'
import './student.css'

export function StudentWorkspace({ exam, resolution, gateway, dispatch, returnToSignIn }) {
  const [attempt, setAttempt] = useState(null)
  const [attemptError, setAttemptError] = useState('')
  const [, setSavingByQuestion] = useState({})
  const [submitted, setSubmitted] = useState(null)
  const questions = useMemo(() => attempt?.questions || [], [attempt])
  const current = questions[exam.index] || questions[0]
  const candidateName = resolution?.candidate?.name || 'Amina Okafor'

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
      <main className="premium-exam-shell" style={{justifyContent: 'center', alignItems: 'center'}}>
        <section className="premium-lobby-card">
          <StatusBadge tone="success">Exam submitted.</StatusBadge>
          <h1>Submission received</h1>
          <p>Your answers have been received by the school server.<br/>You can no longer change your answers.</p>
          {submitted && <Metric label="Score" value={`${submitted.raw_score} / ${submitted.raw_max_score}`} helper={`${submitted.percentage}%`} />}
          <button className="premium-btn-primary" onClick={returnToSignIn} style={{width: '100%', marginTop: '16px'}}>Return to sign in</button>
        </section>
      </main>
    )
  }

  if (exam.stage === 'active') {
    if (!attempt || !current) {
      return (
        <main className="premium-exam-shell">
          <header className="premium-exam-header">
            <div className="premium-exam-header-left">
              <WeaveLogo />
              <div className="premium-exam-title">
                <strong>{resolution?.exam?.title || 'Current examination'}</strong>
                <span>Preparing questions</span>
              </div>
            </div>
          </header>
          <section className="premium-lobby-card">
            <h2>Loading exam</h2>
            <p>Weave is opening your active attempt.</p>
            {attemptError && <Notice tone="danger">{attemptError}</Notice>}
          </section>
        </main>
      )
    }

    return (
      <main className="premium-exam-shell">
        <header className="premium-exam-header">
          <div className="premium-exam-header-left">
            <WeaveLogo />
            <div className="premium-exam-title">
              <strong>{attempt.exam_title}</strong>
              <span>{attempt.is_makeup ? 'Makeup examination' : 'Normal examination'}</span>
            </div>
          </div>
          <div className="premium-exam-header-right">
            <div className="student-avatar" style={{fontSize: '10px'}}>(AD)</div>
            <strong style={{fontSize: '14px', color: '#0F172A'}}>{candidateName}</strong>
          </div>
        </header>
        <div className="premium-exam-layout">
          <aside className="premium-exam-sidebar">
            <div className="premium-timer-box">
              <span>Time remaining</span>
              <strong>{formatRemaining(attempt.remaining_seconds)}</strong>
            </div>
            <div className="premium-question-nav">
              <h3>Questions</h3>
              <div className="premium-nav-grid">
                {questions.map((question, index) => (
                  <button
                    key={question.id}
                    className={`nav-btn ${index === exam.index ? 'current' : ''} ${question.selected_option_ids.length > 0 && index !== exam.index ? 'answered' : ''}`}
                    onClick={() => dispatch({ type: 'exam', patch: { index } })}
                  >
                    {index + 1}
                  </button>
                ))}
              </div>
            </div>
          </aside>
          <div className="premium-exam-content">
            <div className="premium-question-header">
              <h2>Question {exam.index + 1} of {questions.length}</h2>
              <label className="premium-mark-review"><input type="checkbox" /> Mark for review</label>
            </div>
            <div className="premium-question-prompt">{current.prompt || 'What is the value of x in the equation 2x + 3 = 11?'}</div>
            <div className="premium-options-list">
              {current.options.map((option, index) => (
                <label key={option.id} className={`premium-option ${current.selected_option_ids.includes(option.id) ? 'selected' : ''}`}>
                  <input
                    type="radio"
                    style={{display: 'none'}}
                    checked={current.selected_option_ids.includes(option.id)}
                    onChange={() => saveAnswer({ question: current, optionId: option.id, gateway, setAttempt, setSavingByQuestion, setAttemptError })}
                  />
                  <div className="premium-option-letter">{['A', 'B', 'C', 'D', 'E'][index % 5]}</div>
                  <div className="premium-option-text">{option.text || option.position}</div>
                </label>
              ))}
            </div>
            {attemptError && <div style={{marginTop: '24px'}}><Notice tone="danger">{attemptError}</Notice></div>}
            <div className="premium-exam-footer">
              <button className="premium-btn-secondary" onClick={() => dispatch({ type: 'exam', patch: { index: Math.max(0, exam.index - 1) } })} disabled={exam.index === 0}>
                &lt; Previous
              </button>
              {exam.index < questions.length - 1 ? (
                <button className="premium-btn-primary" onClick={() => dispatch({ type: 'exam', patch: { index: exam.index + 1 } })}>
                  Save and next &gt;
                </button>
              ) : (
                <button className="premium-btn-primary" onClick={() => submitAttempt({ gateway, setSubmitted, dispatch, setAttemptError })}>
                  Submit exam
                </button>
              )}
            </div>
          </div>
        </div>
      </main>
    )
  }

  const unavailable = resolution?.state === 'waiting_for_activation'
  return (
    <main className="premium-exam-shell" style={{justifyContent: 'center', alignItems: 'center'}}>
      <section className="premium-lobby-card">
        <StatusBadge tone={unavailable ? 'warning' : 'success'}>{resolution?.state?.replaceAll('_', ' ') || 'Resolved'}</StatusBadge>
        <h1>{resolution?.exam?.title || 'Current examination'}</h1>
        <p>Check the details below before you begin.</p>
        <Notice>Weave resolved your examination from the local CBT backend.</Notice>
        {attemptError && <Notice tone="danger">{attemptError}</Notice>}
        <button className="premium-btn-primary" style={{width: '100%', marginTop: '24px'}} disabled={unavailable} onClick={() => startAttempt({ gateway, setAttempt, dispatch, setAttemptError })}>
          Start Exam &rarr;
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
    setAttemptError(error.userMessage || 'Weave could not start this attempt.')
  }
}

async function saveAnswer({ question, optionId, gateway, setAttempt, setSavingByQuestion, setAttemptError }) {
  const selectedOptionIds = [optionId]
  const mutationSequence = question.mutation_sequence + 1
  setAttemptError('')
  setSavingByQuestion((current) => ({ ...current, [question.id]: 'Saving...' }))
  setAttempt((currentAttempt) => ({
    ...currentAttempt,
    questions: currentAttempt.questions.map((item) => item.id === question.id ? { ...item, selected_option_ids: selectedOptionIds, mutation_sequence: mutationSequence } : item),
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
      questions: currentAttempt.questions.map((item) => item.id === question.id ? { ...item, selected_option_ids: saved.selected_option_ids, mutation_sequence: saved.mutation_sequence, is_flagged: saved.is_flagged } : item),
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
    setAttemptError(error.userMessage || 'Weave could not submit the attempt.')
  }
}

function formatRemaining(seconds) {
  const safe = Math.max(0, Number(seconds) || 0)
  const minutes = Math.floor(safe / 60)
  const remainder = safe % 60
  return `${minutes}:${String(remainder).padStart(2, '0')}`
}
