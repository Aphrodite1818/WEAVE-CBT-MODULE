import { useCallback, useEffect, useReducer, useRef } from 'react'
import { weaveGateway } from './gateway'
import { appReducer, createInitialState } from './state/appState'

function toStudentResolution(session) {
  return {
    state: session.availability,
    statusMessage: session.status_message,
    exam: session.exam_id ? {
      id: session.exam_id,
      title: session.exam_title,
      scheduledStartAt: session.scheduled_start_at,
      activatedAt: session.activated_at,
    } : null,
    candidate: {
      id: session.candidate_id || null,
      name: session.display_name,
      studentId: session.student_id,
    },
    isMakeup: session.is_makeup,
  }
}

export function useAppController() {
  const [state, dispatch] = useReducer(appReducer, undefined, createInitialState)
  const pairPending = useRef(false)

  const boot = useCallback(async (signal) => {
    dispatch({ type: 'bootStart' })
    weaveGateway.branding.getBranding({ signal })
      .then((branding) => dispatch({ type: 'brandingSuccess', branding }))
      .catch(() => null)
    try {
      const status = await weaveGateway.installation.getInstallationStatus({ signal })
      dispatch({ type: 'bootSuccess', status })
    } catch (error) {
      if (error.name !== 'AbortError') {
        dispatch({ type: 'bootFailure', message: error.userMessage || 'Weave could not reach the local backend.' })
      }
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    boot(controller.signal)
    return () => controller.abort()
  }, [boot])

  const pair = useCallback(async (form) => {
    if (pairPending.current) return
    pairPending.current = true
    dispatch({ type: 'setupStart' })
    try {
      const status = await weaveGateway.installation.pairInstallation(form)
      dispatch({ type: 'setupSuccess', status })
      weaveGateway.branding.getBranding()
        .then((branding) => dispatch({ type: 'brandingSuccess', branding }))
        .catch(() => null)
    } catch (error) {
      if (error.status === 409) {
        try {
          const status = await weaveGateway.installation.getInstallationStatus()
          if (status.configured) {
            dispatch({ type: 'setupSuccess', status })
            weaveGateway.branding.getBranding()
              .then((branding) => dispatch({ type: 'brandingSuccess', branding }))
              .catch(() => null)
            return
          }
        } catch { /* Keep the setup values available for a retry. */ }
      }
      dispatch({ type: 'setupFailure', message: error.userMessage || 'Pairing failed. Try again.' })
    } finally {
      pairPending.current = false
    }
  }, [])

  const signInStaff = useCallback(async ({ email, password }) => {
    dispatch({ type: 'authStart' })
    try {
      const session = await weaveGateway.auth.loginStaff({ email, password })
      if (session.role === 'teacher') {
        dispatch({ type: 'authSuccess', session, view: 'staff' })
        dispatch({ type: 'staff', patch: { section: 'overview' } })
      } else if (session.role === 'admin') {
        dispatch({ type: 'authSuccess', session, view: 'sync-check' })
        dispatch({ type: 'syncChecking' })
        try {
          const status = await weaveGateway.sync.getSyncStatus()
          dispatch({ type: 'syncStatus', status })
        } catch (error) {
          dispatch({ type: 'syncFailure', message: error.userMessage || 'Could not check server readiness.' })
        }
      } else {
        weaveGateway.auth.signOutStaff()
        dispatch({ type: 'authFailure', message: 'This account has no CBT staff workspace.' })
      }
    } catch (error) {
      dispatch({ type: 'authFailure', message: error.userMessage || 'Staff sign in failed.' })
    }
  }, [])

  const signInStudent = useCallback(async ({ admissionNumber, password }) => {
    dispatch({ type: 'authStart' })
    try {
      const session = await weaveGateway.auth.loginStudent({ admissionNumber, password })
      dispatch({ type: 'authSuccess', session, view: 'student', examStage: 'lobby' })
      dispatch({ type: 'studentResolution', resolution: toStudentResolution(session) })
    } catch (error) {
      dispatch({ type: 'authFailure', message: error.userMessage || 'Student sign in failed.' })
    }
  }, [])

  useEffect(() => {
    const waitingState = state.studentResolution?.state
    const shouldPoll = (
      state.session?.type === 'student'
      && state.view === 'student'
      && state.exam.stage === 'lobby'
      && (waitingState === 'no_exam' || waitingState === 'waiting_for_activation')
    )
    if (!shouldPoll) return undefined

    let cancelled = false
    const refresh = async () => {
      try {
        const session = await weaveGateway.auth.getStudentStatus()
        if (!cancelled) {
          dispatch({ type: 'studentResolution', resolution: toStudentResolution(session) })
        }
      } catch (error) {
        if (!cancelled && error.status === 401) {
          dispatch({ type: 'signOut' })
        }
      }
    }

    const interval = window.setInterval(refresh, 5000)
    return () => {
      cancelled = true
      window.clearInterval(interval)
    }
  }, [
    state.session?.type,
    state.view,
    state.exam.stage,
    state.studentResolution?.state,
  ])

  const signOut = useCallback(async () => {
    if (state.session?.type === 'student') await weaveGateway.auth.logoutStudent().catch(() => null)
    if (state.session?.type === 'staff') weaveGateway.auth.signOutStaff()
    dispatch({ type: 'signOut' })
  }, [state.session])

  return { state, dispatch, boot, pair, signInStaff, signInStudent, signOut }
}
