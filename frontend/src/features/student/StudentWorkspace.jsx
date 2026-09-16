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
  const candidateName = resolution?.candidate?.name || 'Student'

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
          <button className="premium-btn-primary" onClick={returnToSignIn} style={{width: '100%', marginTop: '16px'}}>Logout</button>
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
              <div className="premium-exam-title"><strong>{resolution?.exam?.title || 'Current examination'}</strong><span>Preparing questions</span></div>
            </div>
            <button className="premium-student-logout" type="button" onClick={returnToSignIn}>Logout</button>
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
            <div className="premium-exam-title"><strong>{attempt.exam_title}</strong><span>{attempt.is_makeup ? 'Makeup examination' : 'Normal examination'}</span></div>
          </div>
          <div className="premium-exam-header-right">
            <div className="student-avatar" style={{fontSize: '10px'}}>(AD)</div>
            <strong style={{fontSize: '14px', color: '#0F172A'}}>{candidateName}</strong>
            <button className="premium-student-logout" type="button" onClick={returnToSignIn}>Logout</button>
          </div>
        </header>
        <div className="premium-exam-layout">
          <aside className="premium-exam-sidebar">
            <div className="premium-timer-box"><span>Time remaining</span><strong>{formatRemaining(attempt.remaining_seconds)}</strong></div>
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
              <label className="premium-mark-review"><input type="checkbox" checked={Boolean(current.is_flagged)} readOnly /> Mark for review</label>
            </div>
            {current.instruction && <p className="premium-question-instruction">{current.instruction}</p>}
            <div className="premium-question-prompt">{current.prompt}</div>
            {current.image_asset_id && (
              <div className="premium-question-media">
                <AttemptMedia gateway={gateway} questionId={current.id} alt="Question illustration" />
              </div>
            )}
            <div className="premium-options-list">
              {current.options.map((option, index) => {
                const selected = current.selected_option_ids.includes(option.id)
                return (
                  <label key={option.id} className={`premium-option ${selected ? 'selected' : ''}`}>
                    <input
                      type={current.question_type === 'multiple_choice' ? 'checkbox' : 'radio'}
                      style={{display: 'none'}}
                      checked={selected}
                      onChange={() => saveAnswer({ question: current, optionId: option.id, gateway, setAttempt, setSavingByQuestion, setAttemptError })}
                    />
                    <div className="premium-option-letter">{optionLetter(index)}</div>
                    <div className="premium-option-content">
                      {option.text && <div className="premium-option-text">{option.text}</div>}
                      {option.image_asset_id && (
                        <div className="premium-option-media">
                          <AttemptMedia gateway={gateway} questionId={current.id} optionId={option.id} alt={`Option ${optionLetter(index)}`} />
                        </div>
                      )}
                    </div>
                  </label>
                )
              })}
            </div>
            {attemptError && <div style={{marginTop: '24px'}}><Notice tone="danger">{attemptError}</Notice></div>}
            <div className="premium-exam-footer">
              <button className="premium-btn-secondary" onClick={() => dispatch({ type: 'exam', patch: { index: Math.max(0, exam.index - 1) } })} disabled={exam.index === 0}>&lt; Previous</button>
              {exam.index < questions.length - 1 ? (
                <button className="premium-btn-primary" onClick={() => dispatch({ type: 'exam', patch: { index: exam.index + 1 } })}>Save and next &gt;</button>
              ) : (
                <button className="premium-btn-primary" onClick={() => submitAttempt({ gateway, setSubmitted, dispatch, setAttemptError })}>Submit exam</button>
              )}
            </div>
          </div>
        </div>
      </main>
    )
  }

  const state = resolution?.state || 'no_exam'
  const noExam = state === 'no_exam'
  const waiting = state === 'waiting_for_activation'
  const unavailable = noExam || waiting
  const ready = state === 'ready' || state === 'makeup'
  const title = noExam ? 'No exam available yet' : resolution?.exam?.title || 'Current examination'
  const statusLabel = noExam ? 'Waiting room' : waiting ? 'Waiting for activation' : state === 'makeup' ? 'Makeup exam ready' : 'Exam ready'

  return (
    <main className="premium-exam-shell" style={{justifyContent: 'center', alignItems: 'center'}}>
      <section className="premium-lobby-card">
        <StatusBadge tone={unavailable ? 'warning' : 'success'}>{statusLabel}</StatusBadge>
        <h1>{title}</h1>
        <p>{resolution?.statusMessage || (noExam ? 'Stay on this page. Weave will update automatically when an exam becomes available.' : 'Check the details below before you begin.')}</p>
        {unavailable && <Notice>Weave is checking the local CBT server automatically. You do not need to sign in again.</Notice>}
        {ready && <Notice>Your examination has been resolved from the local CBT server and is ready to open.</Notice>}
        {attemptError && <Notice tone="danger">{attemptError}</Notice>}
        <button className="premium-btn-primary" style={{width: '100%', marginTop: '24px'}} disabled={unavailable} onClick={() => startAttempt({ gateway, setAttempt, dispatch, setAttemptError })}>
          {noExam ? 'Waiting for an exam...' : waiting ? 'Waiting for activation...' : 'Start Exam ->'}
        </button>
        <button className="premium-btn-secondary" type="button" onClick={returnToSignIn} style={{width: '100%', marginTop: '12px'}}>Logout</button>
      </section>
    </main>
  )
}

function AttemptMedia({ gateway, questionId, optionId, alt }) {
  const [url, setUrl] = useState('')
  useEffect(() => {
    let cancelled = false
    let objectUrl = ''
    const request = optionId
      ? gateway.attempts.getCurrentOptionImage(questionId, optionId)
      : gateway.attempts.getCurrentQuestionImage(questionId)
    request.then((blob) => {
      if (cancelled) return
      objectUrl = URL.createObjectURL(blob)
      setUrl(objectUrl)
    }).catch(() => null)
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [gateway, optionId, questionId])
  return url ? <img src={url} alt={alt} /> : <span className="premium-media-loading">Loading image…</span>
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
  const selectedOptionIds = question.question_type === 'multiple_choice'
    ? question.selected_option_ids.includes(optionId)
      ? question.selected_option_ids.filter((id) => id !== optionId)
      : [...question.selected_option_ids, optionId]
    : [optionId]
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

function optionLetter(index) {
  return String.fromCharCode(65 + (index % 26))
}

function formatRemaining(seconds) {
  const safe = Math.max(0, Number(seconds) || 0)
  const minutes = Math.floor(safe / 60)
  const remainder = safe % 60
  return `${minutes}:${String(remainder).padStart(2, '0')}`
}
