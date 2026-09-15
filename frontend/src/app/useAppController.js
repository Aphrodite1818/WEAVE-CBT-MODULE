import { useCallback, useEffect, useReducer, useRef } from 'react'
import { weaveGateway } from './gateway'
import { appReducer, createInitialState } from './state/appState'

const NAV_STATE_KEY = 'weave.cbt.navigation'
const teacherSections = new Set(['overview', 'question-banks', 'bank-detail', 'questions', 'create-question', 'exams', 'create-exam'])
const adminSections = new Set(['dashboard', 'exams', 'question-banks', 'students', 'invigilators', 'results', 'reports', 'settings'])

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

  const restoreSession = useCallback(async () => {
    const savedNavigation = readNavigationState()
    const preferredType = savedNavigation?.sessionType
    const restorers = preferredType === 'student'
      ? [restoreStudentSession, restoreStaffSession]
      : [restoreStaffSession, restoreStudentSession]

    for (const restore of restorers) {
      if (await restore(dispatch, savedNavigation)) return true
    }
    return false
  }, [])

  const boot = useCallback(async (signal) => {
    dispatch({ type: 'bootStart' })
    weaveGateway.branding.getBranding({ signal })
      .then((branding) => dispatch({ type: 'brandingSuccess', branding }))
      .catch(() => null)
    try {
      const status = await weaveGateway.installation.getInstallationStatus({ signal })
      dispatch({ type: 'bootSuccess', status, view: status.configured ? 'boot' : undefined })
      if (status.configured) {
        const restored = await restoreSession()
        if (!restored) dispatch({ type: 'view', view: 'landing' })
      }
    } catch (error) {
      if (error.name !== 'AbortError') {
        dispatch({ type: 'bootFailure', message: error.userMessage || 'Weave could not reach the local backend.' })
      }
    }
  }, [restoreSession])

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
        weaveGateway.auth.signOutStaff().catch(() => weaveGateway.auth.clearStaffSession())
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

  useEffect(() => {
    persistNavigationState({
      view: state.view,
      sessionType: state.session?.type,
      role: state.session?.role,
      staffSection: state.staff.section,
      examStage: state.exam.stage,
    })
  }, [state.view, state.session?.type, state.session?.role, state.staff.section, state.exam.stage])

  const signOut = useCallback(async () => {
    if (state.session?.type === 'student') await weaveGateway.auth.logoutStudent().catch(() => null)
    if (state.session?.type === 'staff') await weaveGateway.auth.signOutStaff().catch(() => weaveGateway.auth.clearStaffSession())
    clearNavigationState()
    dispatch({ type: 'signOut' })
  }, [state.session])

  return { state, dispatch, boot, pair, signInStaff, signInStudent, signOut }
}

async function restoreStudentSession(dispatch) {
  try {
    const session = await weaveGateway.auth.getStudentStatus()
    dispatch({ type: 'authSuccess', session, view: 'student', examStage: 'lobby' })
    dispatch({ type: 'studentResolution', resolution: toStudentResolution(session) })
    return true
  } catch {
    return false
  }
}

async function restoreStaffSession(dispatch, savedNavigation) {
  try {
    const session = await weaveGateway.auth.refreshStaff()
    if (session.role === 'teacher') {
      dispatch({ type: 'authSuccess', session, view: 'staff' })
      dispatch({ type: 'staff', patch: { section: staffSectionForRole(session.role, savedNavigation?.staffSection) } })
      return true
    }
    if (session.role === 'admin') {
      dispatch({ type: 'authSuccess', session, view: 'sync-check' })
      dispatch({ type: 'staff', patch: { section: staffSectionForRole(session.role, savedNavigation?.staffSection) } })
      dispatch({ type: 'syncChecking' })
      try {
        const status = await weaveGateway.sync.getSyncStatus()
        dispatch({ type: 'syncStatus', status })
      } catch (error) {
        dispatch({ type: 'syncFailure', message: error.userMessage || 'Could not check server readiness.' })
      }
      return true
    }
    await weaveGateway.auth.signOutStaff().catch(() => weaveGateway.auth.clearStaffSession())
    return false
  } catch {
    weaveGateway.auth.clearStaffSession()
    return false
  }
}

function staffSectionForRole(role, section) {
  if (role === 'teacher' && teacherSections.has(section)) return section
  if (role === 'admin' && adminSections.has(section)) return section
  return role === 'admin' ? 'dashboard' : 'overview'
}

function readNavigationState() {
  try {
    const raw = window.localStorage.getItem(NAV_STATE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function persistNavigationState({ view, sessionType, role, staffSection, examStage }) {
  if (sessionType === 'staff' && view === 'staff') {
    window.localStorage.setItem(NAV_STATE_KEY, JSON.stringify({
      sessionType: 'staff',
      role,
      staffSection,
    }))
    return
  }
  if (sessionType === 'student' && view === 'student') {
    window.localStorage.setItem(NAV_STATE_KEY, JSON.stringify({
      sessionType: 'student',
      examStage,
    }))
  }
}

function clearNavigationState() {
  window.localStorage.removeItem(NAV_STATE_KEY)
}
