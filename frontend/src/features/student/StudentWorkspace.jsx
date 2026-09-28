import { useEffect, useMemo, useRef, useState } from 'react'
import { DashboardSchoolIdentity, Notice, StatusBadge } from '../../shared/ui'
import { FormattedText } from '../../shared/ui/FormattedText'
import './student.css'
import { getLocalBrandLogoSrc } from '../../api/branding'
import { RiCheckboxCircleFill, RiFlagFill, RiLogoutBoxRLine, RiDatabase2Line } from '@remixicon/react'

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
      <main className="premium-exam-shell premium-exam-shell--submitted">
        <StudentExamSubmittedCard result={submitted} onLogout={returnToSignIn} />
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

    const answeredCount = questions.filter((question) => question.selected_option_ids.length > 0).length
    const isSaving = Object.values(savingByQuestion).includes('Saving...')
    const unansweredCount = questions.length - answeredCount

    return (
      <main className="premium-exam-shell premium-exam-shell--session">
        <div className="premium-exam-frame">
          <aside className="premium-exam-rail premium-exam-sidebar" aria-label="Exam progress">
            <div className="premium-exam-rail-brand">
              <DashboardSchoolIdentity schoolName={branding?.school_name || schoolName || 'School'} logoSrc={getLocalBrandLogoSrc(branding)} />
            </div>
            <div className="premium-exam-rail-timer">
              <ExamCountdownTimer remaining={remaining} totalSeconds={attempt.time_limit_seconds} />
            </div>
            <div className="premium-question-nav">
              <div className="premium-question-nav__head">
                <h3>Questions</h3>
                <span className="premium-question-nav__meta">{answeredCount} of {questions.length} answered</span>
              </div>
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
            <div className="premium-exam-rail-submit">
              <button
                type="button"
                className="premium-exam-rail-submit-btn"
                disabled={isSaving}
                onClick={() => submitAttempt({ gateway, setSubmitted, dispatch, setAttemptError })}
              >
                Submit exam
              </button>
              {unansweredCount > 0 && (
                <p className="premium-exam-rail-submit-note">{unansweredCount} question{unansweredCount === 1 ? '' : 's'} not answered</p>
              )}
            </div>
          </aside>
          <div className="premium-exam-stage">
            <StudentExamHeader
              title={attempt.exam_title}
              branding={branding}
              schoolName={schoolName}
              serverName={serverName}
              candidateName={candidateName}
              candidateInitial={candidateInitial}
              onLogout={returnToSignIn}
              layout="session"
            />
            <div className="premium-exam-content">
            <div className="premium-exam-content__scroll">
            <div className="premium-question-header">
              <h2>Question {exam.index + 1} of {questions.length}</h2>
              <div className="premium-question-toolbar">
                {current.selected_option_ids.length > 0 && (
                  <button
                    type="button"
                    className="premium-clear-choice"
                    disabled={savingByQuestion[current.id] === 'Saving...'}
                    onClick={() => saveAnswer({ question: current, clearSelection: true, gateway, setAttempt, setSavingByQuestion, setAttemptError, pendingSaves })}
                  >
                    Clear choice
                  </button>
                )}
                <label className="premium-mark-review"><input type="checkbox" checked={Boolean(current.is_flagged)} disabled={savingByQuestion[current.id] === 'Saving...'} onChange={() => saveAnswer({ question: current, flagged: !current.is_flagged, gateway, setAttempt, setSavingByQuestion, setAttemptError, pendingSaves })} /> Mark for review</label>
              </div>
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
            {attemptError && <div className="premium-exam-content__notice"><Notice tone="danger">{attemptError}</Notice></div>}
            </div>
            <div className="premium-exam-footer premium-exam-footer--dock">
              <button className="premium-btn-secondary" onClick={() => dispatch({ type: 'exam', patch: { index: Math.max(0, exam.index - 1) } })} disabled={exam.index === 0}>Previous</button>
              {exam.index < questions.length - 1 ? (
                <button className="premium-btn-primary" onClick={() => dispatch({ type: 'exam', patch: { index: exam.index + 1 } })}>Save and next</button>
              ) : (
                <button className="premium-btn-primary" disabled={isSaving} onClick={() => submitAttempt({ gateway, setSubmitted, dispatch, setAttemptError })}>Submit exam</button>
              )}
            </div>
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
          {starting ? 'Checking exam status...' : noExam ? 'Waiting for an exam...' : waiting ? 'Waiting for activation...' : suspended ? 'Waiting for exam to resume...' : 'Start Exam'}
        </button>
        <button className="premium-btn-secondary" type="button" onClick={returnToSignIn} style={{width: '100%', marginTop: '12px'}}>Logout</button>
      </section>
    </main>
  )
}

const SUBMISSION_SCORE_RADIUS = 58
const SUBMISSION_SCORE_CIRCUMFERENCE = 2 * Math.PI * SUBMISSION_SCORE_RADIUS

function StudentExamSubmittedCard({ result, onLogout }) {
  const scoreValue = result ? `${result.raw_score} / ${result.raw_max_score}` : null
  const percentage = result ? Math.min(100, Math.max(0, Number.parseFloat(result.percentage) || 0)) : null
  const progress = percentage === null ? 0 : percentage / 100
  const offset = SUBMISSION_SCORE_CIRCUMFERENCE * (1 - progress)

  return (
    <section className="premium-submission-card" aria-labelledby="submission-title">
      <div className="premium-submission-card__glow" aria-hidden="true" />
      <div className="premium-submission-card__hero">
        <span className="premium-submission-card__icon" aria-hidden="true">
          <RiCheckboxCircleFill size={40} />
        </span>
        <h1 id="submission-title">Exam submitted</h1>
        <p className="premium-submission-card__lead">Your answers are saved. You may sign out when ready.</p>
      </div>
      {result && (
        <div className="premium-submission-score" aria-label={`Score ${scoreValue}, ${result.percentage} percent`}>
          <div className="premium-submission-score__ring">
            <svg viewBox="0 0 140 140" aria-hidden="true">
              <circle className="premium-submission-score__track" cx="70" cy="70" r={SUBMISSION_SCORE_RADIUS} />
              <circle
                className="premium-submission-score__progress"
                cx="70"
                cy="70"
                r={SUBMISSION_SCORE_RADIUS}
                style={{ strokeDasharray: SUBMISSION_SCORE_CIRCUMFERENCE, strokeDashoffset: offset }}
              />
            </svg>
            <div className="premium-submission-score__face">
              <strong>{result.percentage}%</strong>
              <span>{scoreValue}</span>
            </div>
          </div>
        </div>
      )}
      <button className="premium-btn-primary premium-submission-card__logout" type="button" onClick={onLogout}>Logout</button>
    </section>
  )
}

function StudentExamHeader({ title, branding, schoolName, serverName, candidateName, candidateInitial, onLogout, layout = 'standalone' }) {
  const session = layout === 'session'
  return (
    <header className={`premium-exam-header${session ? ' premium-exam-header--session' : ''}`}>
      <div className="premium-exam-header__inner">
        <div className="premium-exam-header-left">
          {!session && <DashboardSchoolIdentity schoolName={branding?.school_name || schoolName || 'School'} logoSrc={getLocalBrandLogoSrc(branding)} />}
          {session && (
            <div className="premium-exam-session-title premium-exam-session-title--solo">
              <p className="premium-exam-session-eyebrow">Examination</p>
              <h1>{title}</h1>
            </div>
          )}
        </div>
        <div className="premium-exam-server" title={serverName}>
          <span><RiDatabase2Line size={18} aria-hidden="true" /></span>
          <div><small>CBT server</small><strong>{serverName}</strong></div>
        </div>
        <div className="premium-exam-header-right">
          {session ? (
            <div className="premium-exam-header-account">
              <span className="student-avatar" aria-hidden="true">{candidateInitial}</span>
              <strong className="premium-student-name" title={candidateName}>{candidateName}</strong>
              <button className="premium-student-logout" type="button" onClick={onLogout} aria-label="Logout">
                <RiLogoutBoxRLine size={18} aria-hidden="true" />
              </button>
            </div>
          ) : (
            <>
              <div className="premium-student-identity"><span className="student-avatar" aria-hidden="true">{candidateInitial}</span><strong className="premium-student-name" title={candidateName}>{candidateName}</strong></div>
              <button className="premium-student-logout" type="button" onClick={onLogout}><RiLogoutBoxRLine size={17} aria-hidden="true" /><span>Logout</span></button>
            </>
          )}
        </div>
        {!session && title && <div className="premium-exam-title"><h1>{title}</h1></div>}
      </div>
    </header>
  )
}

function ExamCountdownTimer({ remaining, totalSeconds }) {
  const radius = 50
  const circumference = 2 * Math.PI * radius
  const safeTotal = Math.max(Number(totalSeconds) || 0, Number(remaining) || 0, 1)
  const progress = Math.min(1, Math.max(0, (Number(remaining) || 0) / safeTotal))
  const offset = circumference * (1 - progress)
  const urgent = remaining <= 300
  const critical = remaining <= 120

  return (
    <div
      className={`premium-exam-timer${urgent ? ' is-urgent' : ''}${critical ? ' is-critical' : ''}`}
      role="timer"
      aria-live="off"
      aria-label={`Time remaining ${formatRemaining(remaining)}`}
    >
      <div className="premium-exam-timer__ring">
        <svg viewBox="0 0 120 120" aria-hidden="true">
          <circle className="premium-exam-timer__track" cx="60" cy="60" r={radius} />
          <circle
            className="premium-exam-timer__progress"
            cx="60"
            cy="60"
            r={radius}
            style={{ strokeDasharray: circumference, strokeDashoffset: offset }}
          />
        </svg>
        <div className="premium-exam-timer__face">
          <span className="premium-exam-timer__label">Time left</span>
          <strong className="premium-exam-timer__value" key={Math.floor(remaining / 60)}>{formatRemaining(remaining)}</strong>
        </div>
      </div>
    </div>
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

async function saveAnswer({ question, optionId, clearSelection = false, flagged = question.is_flagged, gateway, setAttempt, setSavingByQuestion, setAttemptError, pendingSaves }) {
  if (pendingSaves.current.has(question.id)) return
  pendingSaves.current.add(question.id)
  const selectedOptionIds = clearSelection ? []
    : optionId === undefined ? question.selected_option_ids
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