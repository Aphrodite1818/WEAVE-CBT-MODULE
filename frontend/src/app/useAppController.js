import { useCallback, useEffect, useReducer, useRef } from 'react'
import { weaveGateway } from './gateway'
import { appReducer, createInitialState } from './state/appState'

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
      const session = await weaveGateway.auth.loginStudent({ admissionNumber, pin: password })
      const resolution = {
        state: session.availability,
        exam: { id: session.exam_id, title: session.exam_title, scheduledStartAt: session.scheduled_start_at },
        candidate: { id: session.candidate_id, name: session.display_name, studentId: session.student_id },
        isMakeup: session.is_makeup,
      }
      dispatch({ type: 'authSuccess', session, view: 'student', examStage: 'lobby' })
      dispatch({ type: 'studentResolution', resolution })
    } catch (error) {
      dispatch({ type: 'authFailure', message: error.userMessage || 'Student sign in failed.' })
    }
  }, [])

  const signOut = useCallback(async () => {
    if (state.session?.type === 'student') await weaveGateway.auth.logoutStudent().catch(() => null)
    if (state.session?.type === 'staff') weaveGateway.auth.signOutStaff()
    dispatch({ type: 'signOut' })
  }, [state.session])

  return { state, dispatch, boot, pair, signInStaff, signInStudent, signOut }
}
