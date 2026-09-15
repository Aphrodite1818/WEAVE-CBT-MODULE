import { useCallback, useEffect, useReducer, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { weaveGateway } from './gateway'
import { appReducer, createInitialState } from './state/appState'

const NAV_STATE_KEY = 'weave.cbt.navigation'
const teacherSections = new Set(['overview', 'question-banks', 'bank-detail', 'questions', 'create-question', 'exams', 'create-exam'])
const adminSections = new Set(['dashboard', 'exams', 'question-banks', 'students', 'invigilators', 'results', 'reports', 'settings'])
const setupViews = new Set(['welcome', 'pairing-code', 'server-name', 'pairing', 'paired-success'])

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
  const navigate = useNavigate()
  const location = useLocation()
  const [state, rawDispatch] = useReducer(appReducer, undefined, createInitialState)
  const pairPending = useRef(false)
  const stateRef = useRef(state)
  const locationPathRef = useRef(location.pathname)
  const navigateRef = useRef(navigate)

  useEffect(() => {
    stateRef.current = state
  }, [state])

  useEffect(() => {
    locationPathRef.current = location.pathname
  }, [location.pathname])

  useEffect(() => {
    navigateRef.current = navigate
  }, [navigate])

  const routeDispatch = useCallback((action) => {
    rawDispatch(action)
    const current = stateRef.current
    const nextPath = pathForAction(action, current)
    if (nextPath) navigate(nextPath)
  }, [navigate])

  const restoreSession = useCallback(async () => {
    const savedNavigation = readNavigationState()
    const routeNavigation = routeToNavigation(routeFromPath(locationPathRef.current))
    const navigationTarget = { ...savedNavigation, ...routeNavigation }
    const preferredType = navigationTarget?.sessionType
    const restorers = preferredType === 'student'
      ? [restoreStudentSession, restoreStaffSession]
      : [restoreStaffSession, restoreStudentSession]

    for (const restore of restorers) {
      if (await restore(rawDispatch, navigationTarget, navigateRef.current)) return true
    }
    return false
  }, [])

  const boot = useCallback(async (signal) => {
    rawDispatch({ type: 'bootStart' })
    weaveGateway.branding.getBranding({ signal })
      .then((branding) => rawDispatch({ type: 'brandingSuccess', branding }))
      .catch(() => null)
    try {
      const status = await weaveGateway.installation.getInstallationStatus({ signal })
      rawDispatch({ type: 'bootSuccess', status, view: status.configured ? 'boot' : undefined })
      if (status.configured) {
        const restored = await restoreSession()
        if (!restored) applyRouteToState(routeFromPath(locationPathRef.current), stateRef.current, rawDispatch, navigateRef.current)
      } else {
        const route = routeFromPath(locationPathRef.current)
        if (setupViews.has(route.view)) {
          rawDispatch({ type: 'view', view: route.view })
          navigateRef.current(pathForView(route.view), { replace: true })
        } else {
          navigateRef.current('/setup', { replace: true })
        }
      }
    } catch (error) {
      if (error.name !== 'AbortError') {
        rawDispatch({ type: 'bootFailure', message: error.userMessage || 'Weave could not reach the local backend.' })
      }
    }
  }, [restoreSession])

  useEffect(() => {
    const controller = new AbortController()
    boot(controller.signal)
    return () => controller.abort()
  }, [boot])

  useEffect(() => {
    if (state.installation.loading) return
    if (!state.installation.configured) {
      const route = routeFromPath(location.pathname)
      if (setupViews.has(route.view)) {
        rawDispatch({ type: 'view', view: route.view })
        return
      }
      rawDispatch({ type: 'view', view: 'welcome' })
      navigate('/setup', { replace: true })
      return
    }
    const route = routeFromPath(location.pathname)
    if (setupViews.has(route.view)) {
      rawDispatch({ type: 'view', view: 'landing' })
      navigate('/', { replace: true })
      return
    }
    applyRouteToState(route, stateRef.current, rawDispatch, navigate)
  }, [location.pathname, navigate, state.installation.configured, state.installation.loading])

  const pair = useCallback(async (form) => {
    if (pairPending.current) return
    pairPending.current = true
    rawDispatch({ type: 'setupStart' })
    navigate('/setup/pairing')
    try {
      const status = await weaveGateway.installation.pairInstallation(form)
      rawDispatch({ type: 'setupSuccess', status })
      navigate('/setup/paired-success', { replace: true })
      weaveGateway.branding.getBranding()
        .then((branding) => rawDispatch({ type: 'brandingSuccess', branding }))
        .catch(() => null)
    } catch (error) {
      if (error.status === 409) {
        try {
          const status = await weaveGateway.installation.getInstallationStatus()
          if (status.configured) {
            rawDispatch({ type: 'setupSuccess', status })
            navigate('/setup/paired-success', { replace: true })
            weaveGateway.branding.getBranding()
              .then((branding) => rawDispatch({ type: 'brandingSuccess', branding }))
              .catch(() => null)
            return
          }
        } catch { /* Keep the setup values available for a retry. */ }
      }
      rawDispatch({ type: 'setupFailure', message: error.userMessage || 'Pairing failed. Try again.' })
    } finally {
      pairPending.current = false
    }
  }, [navigate])

  const signInStaff = useCallback(async ({ email, password }) => {
    rawDispatch({ type: 'authStart' })
    try {
      const session = await weaveGateway.auth.loginStaff({ email, password })
      if (session.role === 'teacher') {
        rawDispatch({ type: 'authSuccess', session, view: 'staff' })
        rawDispatch({ type: 'staff', patch: { section: 'overview' } })
        navigate('/teacher/overview', { replace: true })
      } else if (session.role === 'admin') {
        rawDispatch({ type: 'authSuccess', session, view: 'sync-check' })
        rawDispatch({ type: 'syncChecking' })
        navigate('/sync/check', { replace: true })
        try {
          const status = await weaveGateway.sync.getSyncStatus()
          rawDispatch({ type: 'syncStatus', status })
          navigate(status.bootstrap_completed_at ? '/admin/dashboard' : '/sync/initial', { replace: true })
        } catch (error) {
          rawDispatch({ type: 'syncFailure', message: error.userMessage || 'Could not check server readiness.' })
          navigate('/sync/initial', { replace: true })
        }
      } else {
        weaveGateway.auth.signOutStaff().catch(() => weaveGateway.auth.clearStaffSession())
        rawDispatch({ type: 'authFailure', message: 'This account has no CBT staff workspace.' })
      }
    } catch (error) {
      rawDispatch({ type: 'authFailure', message: error.userMessage || 'Staff sign in failed.' })
    }
  }, [navigate])

  const signInStudent = useCallback(async ({ admissionNumber, password }) => {
    rawDispatch({ type: 'authStart' })
    try {
      const session = await weaveGateway.auth.loginStudent({ admissionNumber, password })
      rawDispatch({ type: 'authSuccess', session, view: 'student', examStage: 'lobby' })
      rawDispatch({ type: 'studentResolution', resolution: toStudentResolution(session) })
      navigate('/student', { replace: true })
    } catch (error) {
      rawDispatch({ type: 'authFailure', message: error.userMessage || 'Student sign in failed.' })
    }
  }, [navigate])

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
          rawDispatch({ type: 'studentResolution', resolution: toStudentResolution(session) })
        }
      } catch (error) {
        if (!cancelled && error.status === 401) {
          rawDispatch({ type: 'signOut' })
          navigate('/', { replace: true })
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
    navigate,
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
    rawDispatch({ type: 'signOut' })
    navigate('/', { replace: true })
  }, [navigate, state.session])

  return { state, dispatch: routeDispatch, boot, pair, signInStaff, signInStudent, signOut }
}

async function restoreStudentSession(dispatch, savedNavigation, navigate) {
  try {
    const session = await weaveGateway.auth.getStudentStatus()
    const examStage = savedNavigation?.examStage === 'active' ? 'active' : 'lobby'
    dispatch({ type: 'authSuccess', session, view: 'student', examStage })
    dispatch({ type: 'studentResolution', resolution: toStudentResolution(session) })
    navigate(examStage === 'active' ? '/student/exam' : '/student', { replace: true })
    return true
  } catch {
    return false
  }
}

async function restoreStaffSession(dispatch, savedNavigation, navigate) {
  try {
    const session = await weaveGateway.auth.refreshStaff()
    if (session.role === 'teacher') {
      const section = staffSectionForRole(session.role, savedNavigation?.staffSection)
      dispatch({ type: 'authSuccess', session, view: 'staff' })
      dispatch({ type: 'staff', patch: { section } })
      navigate(`/teacher/${section}`, { replace: true })
      return true
    }
    if (session.role === 'admin') {
      const section = staffSectionForRole(session.role, savedNavigation?.staffSection)
      dispatch({ type: 'authSuccess', session, view: 'sync-check' })
      dispatch({ type: 'staff', patch: { section } })
      dispatch({ type: 'syncChecking' })
      navigate('/sync/check', { replace: true })
      try {
        const status = await weaveGateway.sync.getSyncStatus()
        dispatch({ type: 'syncStatus', status })
        navigate(status.bootstrap_completed_at ? `/admin/${section}` : '/sync/initial', { replace: true })
      } catch (error) {
        dispatch({ type: 'syncFailure', message: error.userMessage || 'Could not check server readiness.' })
        navigate('/sync/initial', { replace: true })
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

function routeFromPath(pathname) {
  const path = normalizePath(pathname)
  if (path === '/') return { view: 'landing' }
  if (path === '/student/login') return { view: 'student-login' }
  if (path === '/staff/login') return { view: 'staff-login' }
  if (path === '/setup') return { view: 'welcome' }
  if (path.startsWith('/setup/')) {
    const view = path.slice('/setup/'.length)
    return { view: setupViews.has(view) ? view : 'welcome' }
  }
  if (path === '/sync/check') return { view: 'sync-check' }
  if (path === '/sync/initial') return { view: 'initial-sync' }
  if (path === '/student') return { view: 'student', sessionType: 'student', examStage: 'lobby', requiresAuth: true }
  if (path === '/student/exam') return { view: 'student', sessionType: 'student', examStage: 'active', requiresAuth: true }
  if (path.startsWith('/teacher')) {
    const section = path.split('/')[2] || 'overview'
    return {
      view: 'staff',
      sessionType: 'staff',
      role: 'teacher',
      staffSection: teacherSections.has(section) ? section : 'overview',
      requiresAuth: true,
    }
  }
  if (path.startsWith('/admin')) {
    const section = path.split('/')[2] || 'dashboard'
    return {
      view: 'staff',
      sessionType: 'staff',
      role: 'admin',
      staffSection: adminSections.has(section) ? section : 'dashboard',
      requiresAuth: true,
    }
  }
  return { view: 'landing' }
}

function routeToNavigation(route) {
  if (!route?.requiresAuth) return null
  return {
    sessionType: route.sessionType,
    role: route.role,
    staffSection: route.staffSection,
    examStage: route.examStage,
  }
}

function applyRouteToState(route, state, dispatch, navigate) {
  if (route?.requiresAuth) {
    if (route.sessionType === 'staff' && state.session?.type === 'staff') {
      const rolePath = state.session.role === 'admin' ? 'admin' : 'teacher'
      if (route.role && route.role !== state.session.role) {
        navigate(`/${rolePath}/${staffSectionForRole(state.session.role, state.staff.section)}`, { replace: true })
        return
      }
      dispatch({ type: 'authSuccess', session: state.session, view: 'staff' })
      dispatch({ type: 'staff', patch: { section: staffSectionForRole(state.session.role, route.staffSection) } })
      return
    }
    if (route.sessionType === 'student' && state.session?.type === 'student') {
      dispatch({ type: 'authSuccess', session: state.session, view: 'student', examStage: route.examStage || 'lobby' })
      if (state.studentResolution) dispatch({ type: 'studentResolution', resolution: state.studentResolution })
      return
    }
    const loginPath = route.sessionType === 'student' ? '/student/login' : '/staff/login'
    dispatch({ type: 'view', view: route.sessionType === 'student' ? 'student-login' : 'staff-login' })
    navigate(loginPath, { replace: true })
    return
  }
  dispatch({ type: 'view', view: route?.view || 'landing' })
}

function pathForAction(action, state) {
  if (action.type === 'view') return pathForView(action.view)
  if (action.type === 'setupStart') return '/setup/pairing'
  if (action.type === 'setupSuccess') return '/setup/paired-success'
  if (action.type === 'signOut') return '/'
  if (action.type === 'syncChecking') return '/sync/check'
  if (action.type === 'syncFailure') return '/sync/initial'
  if (action.type === 'syncStatus') return action.status.bootstrap_completed_at ? pathForStaffState(state) : '/sync/initial'
  if (action.type === 'staff' && action.patch?.section && state.session?.type === 'staff') {
    return pathForStaffState({ ...state, staff: { ...state.staff, ...action.patch } })
  }
  if (action.type === 'exam' && action.patch?.stage && state.session?.type === 'student') {
    return action.patch.stage === 'active' ? '/student/exam' : '/student'
  }
  return null
}

function pathForView(view) {
  if (view === 'landing') return '/'
  if (view === 'student-login') return '/student/login'
  if (view === 'staff-login') return '/staff/login'
  if (setupViews.has(view)) return view === 'welcome' ? '/setup' : `/setup/${view}`
  if (view === 'sync-check') return '/sync/check'
  if (view === 'initial-sync') return '/sync/initial'
  return null
}

function pathForStaffState(state) {
  if (state.session?.role === 'admin') {
    const section = state.staff.section === 'overview' ? 'dashboard' : staffSectionForRole('admin', state.staff.section)
    return `/admin/${section}`
  }
  if (state.session?.role === 'teacher') return `/teacher/${staffSectionForRole('teacher', state.staff.section)}`
  return null
}

function normalizePath(pathname) {
  const path = pathname || '/'
  if (path.length > 1 && path.endsWith('/')) return path.slice(0, -1)
  return path
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
