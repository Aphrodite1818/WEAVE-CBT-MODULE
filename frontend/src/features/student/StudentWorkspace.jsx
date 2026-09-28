import { useEffect, useMemo, useRef, useState } from 'react'
import { DashboardSchoolIdentity, Metric, Notice, StatusBadge } from '../../shared/ui'
import { FormattedText } from '../../shared/ui/FormattedText'
import './student.css'
import { getLocalBrandLogoSrc } from '../../api/branding'
import { RiFlagFill, RiLogoutBoxRLine, RiDatabase2Line } from '@remixicon/react'

const HEARTBEAT_RETRY_MS = 10_000

export function StudentWorkspace({ exam, resolution, gateway, dispatch, returnToSignIn, branding, schoolName, serverName = 'Local CBT server', onExamSuspended }) {
  const [attempt, setAttempt] = useState(null)
  const [attemptError, setAttemptError] = useState('')
  const [savingByQuestion, setSavingByQuestion] = useState({})
  const [submitted, setSubmitted] = useState(null)
  const [starting, setStarting] = useState(false)
  const [suspension, setSuspension] = useState(null)
  const suspensionHandled = useRef(false)
  const startPending = useRef(false)
  const pendingSaves = useRef(new Set())
  const [clock, setClock] = useState(() => Date.now())
  const isSuspended = exam.stage === 'active' && Boolean(suspension || attempt?.exam_suspended || resolution?.state === 'suspended')
  const remaining = Math.max(0, (attempt?.remaining_seconds || 0) - (attempt?.exam_suspended || attempt?.status !== 'in_progress' ? 0 : Math.floor(Math.max(0, clock - (attempt?.clock_received_at || clock)) / 1000)))
  useEffect(() => {
    if (exam.stage !== 'active' || !attempt?.id || submitted || isSuspended) return undefined
    const tick = () => setClock(Date.now())
    const timer = window.setInterval(tick, 250)
    document.addEventListener('visibilitychange', tick)
    return () => { window.clearInterval(timer); document.removeEventListener('visibilitychange', tick) }
  }, [exam.stage, attempt?.id, submitted, isSuspended])
  const questions = useMemo(() => attempt?.questions || [], [attempt])
  const current = questions[exam.index] || questions[0]
  const candidateName = resolution?.candidate?.name?.trim() || 'Student'
  const candidateInitial = Array.from(candidateName)[0].toLocaleUpperCase()
  useEffect(() => {
    if (!isSuspended || suspensionHandled.current) return
    suspensionHandled.current = true
    onExamSuspended?.(suspension?.message || (resolution?.state === 'suspended' ? resolution.statusMessage : undefined))
  }, [isSuspended, onExamSuspended, resolution, suspension])

  useEffect(() => {
    if (exam.stage === 'active') return
    suspensionHandled.current = false
    setSuspension(null)
    setAttempt(null)
  }, [exam.stage])

  useEffect(() => {
    if (exam.stage !== 'active') return undefined
    let cancelled = false
    gateway.attempts
      .getCurrentAttempt()
      .then((currentAttempt) => {
        if (!cancelled) setAttempt({ ...currentAttempt, clock_received_at: Date.now() })
      })
      .catch(() => null)
    return () => {
      cancelled = true
    }
  }, [exam.stage, gateway])

  useEffect(() => {
    if (exam.stage !== 'active' || !attempt?.id || submitted || isSuspended) return undefined

    let stopped = false
    let timerId = null

    const schedule = (milliseconds) => {
      if (!stopped) timerId = window.setTimeout(sendHeartbeat, milliseconds)
    }

    const sendHeartbeat = async () => {
      try {
        const heartbeat = await gateway.attempts.heartbeatCurrentAttempt()
        if (stopped) return
        setAttempt((currentAttempt) => currentAttempt
          ? {
              ...currentAttempt,
              remaining_seconds: heartbeat.remaining_seconds,
              clock_received_at: Date.now(),
              status: heartbeat.status,
              exam_suspended: heartbeat.exam_suspended,
            }
          : currentAttempt)
        const nextSeconds = Number(heartbeat.next_heartbeat_after_seconds) || 20
        schedule(Math.max(5, nextSeconds) * 1000)
      } catch {
        try {
          const status = await gateway.auth.getStudentStatus()
          if (!stopped && status.availability === 'suspended') { setSuspension({ message: status.status_message }); return }
        } catch { /* A network failure alone must not end an attempt. */ }
        // Heartbeat loss is monitoring evidence, not an academic-state change.
        // Keep the student UI usable and retry; answer saves/submission surface
        // their own errors separately.
        schedule(HEARTBEAT_RETRY_MS)
      }
    }

    sendHeartbeat()

    const handleVisibility = () => {
      if (!document.hidden && !stopped) {
        if (timerId) window.clearTimeout(timerId)
        sendHeartbeat()
      }
    }
    document.addEventListener('visibilitychange', handleVisibility)

    return () => {
      stopped = true
      if (timerId) window.clearTimeout(timerId)
      document.removeEventListener('visibilitychange', handleVisibility)
    }
  }, [attempt?.id, exam.stage, gateway, submitted, isSuspended])

  if (isSuspended) return <main className="premium-exam-shell"><section className="premium-lobby-card"><h1>Exam currently suspended</h1><p>Returning you to the waiting room. Your session and saved answers are protected.</p></section></main>

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
          <StudentExamHeader title={resolution?.exam?.title || 'Current examination'} branding={branding} schoolName={schoolName} serverName={serverName} candidateName={candidateName} candidateInitial={candidateInitial} onLogout={returnToSignIn} />
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
        <StudentExamHeader title={attempt.exam_title} branding={branding} schoolName={schoolName} serverName={serverName} candidateName={candidateName} candidateInitial={candidateInitial} onLogout={returnToSignIn} />
        <div className="premium-exam-layout">
          <aside className="premium-exam-sidebar">
            <div className="premium-timer-box"><span>Time remaining</span><strong>{formatRemaining(remaining)}</strong></div>
            <div className="premium-question-nav">
              <h3>Questions</h3>
              <div className="premium-nav-grid">
                {questions.map((question, index) => (
                  <button
                    key={question.id}
                    aria-label={`Question ${index + 1}${question.is_flagged ? ', marked for review' : ''}`}
                    aria-current={index === exam.index ? 'step' : undefined}
                    className={`nav-btn ${question.is_flagged ? 'flagged' : ''} ${index === exam.index ? 'current' : ''} ${question.selected_option_ids.length > 0 && index !== exam.index ? 'answered' : ''}`}
                    onClick={() => dispatch({ type: 'exam', patch: { index } })}
                  >
                    {index + 1}{question.is_flagged && <RiFlagFill className="premium-review-flag" size={12} aria-hidden="true" />}
                  </button>
                ))}
              </div>
            </div>
          </aside>
          <div className="premium-exam-content">
            <div className="premium-question-header">
              <h2>Question {exam.index + 1} of {questions.length}</h2>
              <label className="premium-mark-review"><input type="checkbox" checked={Boolean(current.is_flagged)} disabled={savingByQuestion[current.id] === 'Saving...'} onChange={() => saveAnswer({ question: current, flagged: !current.is_flagged, gateway, setAttempt, setSavingByQuestion, setAttemptError, pendingSaves })} /> Mark for review</label>
            </div>
            {current.instruction && <p className="premium-question-instruction"><FormattedText text={current.instruction} /></p>}
            <div className="premium-question-prompt"><FormattedText text={current.prompt} /></div>
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
                      disabled={savingByQuestion[current.id] === 'Saving...'}
                      onChange={() => saveAnswer({ question: current, optionId: option.id, gateway, setAttempt, setSavingByQuestion, setAttemptError, pendingSaves })}
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
              <button className="premium-btn-secondary" onClick={() => dispatch({ type: 'exam', patch: { index: Math.max(0, exam.index - 1) } })} disabled={exam.index === 0}>Previous</button>
              {exam.index < questions.length - 1 ? (
                <button className="premium-btn-primary" onClick={() => dispatch({ type: 'exam', patch: { index: exam.index + 1 } })}>Save and next</button>
              ) : (
                <button className="premium-btn-primary" disabled={Object.values(savingByQuestion).includes('Saving...')} onClick={() => submitAttempt({ gateway, setSubmitted, dispatch, setAttemptError })}>Submit exam</button>
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
  const suspended = state === 'suspended'
  const unavailable = noExam || waiting || suspended
  const ready = state === 'ready' || state === 'makeup'
  const title = noExam ? 'No exam available yet' : resolution?.exam?.title || 'Current examination'
  const statusLabel = noExam ? 'Waiting room' : waiting ? 'Waiting for activation' : suspended ? 'Exam suspended' : state === 'makeup' ? 'Makeup exam ready' : 'Exam ready'

  return (
    <main className="premium-exam-shell" style={{justifyContent: 'center', alignItems: 'center'}}>
      <section className="premium-lobby-card">
        <StatusBadge tone={unavailable ? 'warning' : 'success'}>{statusLabel}</StatusBadge>
        <h1>{title}</h1>
        <p>{resolution?.statusMessage || (noExam ? 'Stay on this page. Weave will update automatically when an exam becomes available.' : 'Check the details below before you begin.')}</p>
        {unavailable && <Notice>Weave is checking the local CBT server automatically. You do not need to sign in again.</Notice>}
        {ready && <Notice>Your examination has been resolved from the local CBT server and is ready to open.</Notice>}
        {attemptError && <Notice tone="danger">{attemptError}</Notice>}
        <button className="premium-btn-primary" style={{width: '100%', marginTop: '24px'}} disabled={unavailable || starting} onClick={() => startAttempt({ gateway, setAttempt, dispatch, setAttemptError, setStarting, onExamSuspended, startPending, expectedExamId: resolution?.exam?.id })}>
          {starting ? 'Checking exam status...' : noExam ? 'Waiting for an exam...' : waiting ? 'Waiting for activation...' : suspended ? 'Waiting for exam to resume...' : 'Start Exam ->'}
        </button>
        <button className="premium-btn-secondary" type="button" onClick={returnToSignIn} style={{width: '100%', marginTop: '12px'}}>Logout</button>
      </section>
    </main>
  )
}

function StudentExamHeader({ title, branding, schoolName, serverName, candidateName, candidateInitial, onLogout }) {
  return <header className="premium-exam-header">
    <div className="premium-exam-header-left"><DashboardSchoolIdentity schoolName={branding?.school_name || schoolName || 'School'} logoSrc={getLocalBrandLogoSrc(branding)} /></div>
    <div className="premium-exam-server" title={serverName}><span><RiDatabase2Line size={18} aria-hidden="true" /></span><div><small>CBT server</small><strong>{serverName}</strong></div></div>
    <div className="premium-exam-header-right">
      <div className="premium-student-identity"><span className="student-avatar" aria-hidden="true">{candidateInitial}</span><strong className="premium-student-name" title={candidateName}>{candidateName}</strong></div>
      <button className="premium-student-logout" type="button" onClick={onLogout}><RiLogoutBoxRLine size={17} aria-hidden="true" /><span>Logout</span></button>
    </div>
    <div className="premium-exam-title"><h1>{title}</h1></div>
  </header>
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

async function startAttempt({ gateway, setAttempt, dispatch, setAttemptError, setStarting, onExamSuspended, startPending, expectedExamId }) {
  if (startPending.current) return
  startPending.current = true
  setStarting(true)
  setAttemptError('')
  try {
    const status = await gateway.auth.getStudentStatus()
    if (status.availability === 'suspended') { onExamSuspended?.(status.status_message); return }
    if (!['ready', 'makeup'].includes(status.availability) || status.exam_id !== expectedExamId) {
      setAttemptError(status.status_message || 'This examination is not currently available. Please wait for your invigilator.')
      return
    }
    // The start endpoint remains authoritative if the exam changes after this check.
    const attempt = await gateway.attempts.startCurrentAttempt()
    if (attempt.exam_suspended) { onExamSuspended?.(); return }
    setAttempt({ ...attempt, clock_received_at: Date.now() })
    dispatch({ type: 'exam', patch: { stage: 'active', index: 0 } })
  } catch (error) {
    try {
      const status = await gateway.auth.getStudentStatus()
      if (status.availability === 'suspended') { onExamSuspended?.(status.status_message); return }
    } catch { /* Preserve the start failure when status is unavailable. */ }
    setAttemptError(error.userMessage || 'Weave could not start this attempt. Please try again.')
  } finally {
    startPending.current = false
    setStarting(false)
  }
}

async function saveAnswer({ question, optionId, flagged = question.is_flagged, gateway, setAttempt, setSavingByQuestion, setAttemptError, pendingSaves }) {
  if (pendingSaves.current.has(question.id)) return
  pendingSaves.current.add(question.id)
  const selectedOptionIds = optionId === undefined ? question.selected_option_ids
    : question.question_type === 'multiple_choice'
      ? question.selected_option_ids.includes(optionId)
        ? question.selected_option_ids.filter((id) => id !== optionId)
        : [...question.selected_option_ids, optionId]
      : [optionId]
  const mutationSequence = question.mutation_sequence + 1
  setAttemptError('')
  setSavingByQuestion((current) => ({ ...current, [question.id]: 'Saving...' }))
  setAttempt((currentAttempt) => ({
    ...currentAttempt,
    questions: currentAttempt.questions.map((item) => item.id === question.id ? { ...item, selected_option_ids: selectedOptionIds, is_flagged: flagged, mutation_sequence: mutationSequence } : item),
  }))
  try {
    const saved = await gateway.attempts.saveCurrentAnswer(question.id, {
      mutation_sequence: mutationSequence,
      selected_option_ids: selectedOptionIds,
      is_flagged: flagged,
    })
    setAttempt((currentAttempt) => ({
      ...currentAttempt,
      remaining_seconds: saved.remaining_seconds,
      clock_received_at: Date.now(),
      questions: currentAttempt.questions.map((item) => item.id === question.id ? { ...item, selected_option_ids: saved.selected_option_ids, mutation_sequence: saved.mutation_sequence, is_flagged: saved.is_flagged } : item),
    }))
    setSavingByQuestion((current) => ({ ...current, [question.id]: 'Saved' }))
  } catch (error) {
    setAttempt((currentAttempt) => ({
      ...currentAttempt,
      questions: currentAttempt.questions.map((item) => item.id === question.id ? { ...item, selected_option_ids: question.selected_option_ids, is_flagged: question.is_flagged } : item),
    }))
    setSavingByQuestion((current) => ({ ...current, [question.id]: 'Not saved' }))
    setAttemptError(error.userMessage || 'Your change could not be saved. Please try again.')
  } finally {
    pendingSaves.current.delete(question.id)
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