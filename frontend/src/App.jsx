import { useEffect, useMemo, useReducer, useState } from 'react'
import { FormField, WeaveLogo, Notice, TenantIdentity } from './components/ui'
import { AdminWorkspace } from './features/admin/AdminWorkspace'
import { AuthPage } from './features/auth/AuthPage'
import { StudentWorkspace } from './features/student/StudentWorkspace'
import { TeacherWorkspace } from './features/teacher/TeacherWorkspace'
import { appReducer, createInitialState, getTenant } from './state/appState'
import { leafGateway } from './services/leafGateway'

export default function App() {
  const [state, dispatch] = useReducer(appReducer, undefined, createInitialState)
  const tenant = getTenant(state)

  useEffect(() => {
    const controller = new AbortController()
    dispatch({ type: 'bootStart' })
    leafGateway.installation
      .getInstallationStatus({ signal: controller.signal })
      .then((status) => dispatch({ type: 'bootSuccess', status }))
      .catch((error) => {
        if (error.name !== 'AbortError') {
          dispatch({ type: 'bootFailure', message: error.userMessage || 'Weave could not reach the local backend.' })
        }
      })
    return () => controller.abort()
  }, [])

  const themeStyle = useMemo(
    () => ({
      '--tenant-accent': tenant.primaryAccent,
      '--tenant-accent-soft': tenant.softAccent,
      '--tenant-accent-ink': tenant.inkAccent,
    }),
    [tenant],
  )

  const signIn = async (form) => {
    if (state.authMode === 'student' && (!form.identifier || !form.secret)) {
      dispatch({ type: 'authFailure', message: 'Admission number and CBT PIN are required.' })
      return
    }
    if (state.authMode === 'staff' && (!form.identifier || !form.secret)) {
      dispatch({ type: 'authFailure', message: 'Email and password are required.' })
      return
    }

    dispatch({ type: 'authStart' })
    try {
      if (state.authMode === 'student') {
        const session = await leafGateway.auth.loginStudent({ admissionNumber: form.identifier, pin: form.secret })
        const resolution = {
          state: session.availability,
          exam: { id: session.exam_id, title: session.exam_title, scheduledStartAt: session.scheduled_start_at },
          candidate: { id: session.candidate_id, name: session.display_name, studentId: session.student_id },
          isMakeup: session.is_makeup,
        }
        dispatch({ type: 'authSuccess', session, view: 'student', examStage: 'lobby' })
        dispatch({ type: 'studentResolution', resolution })
        return
      }

      const session = await leafGateway.auth.loginStaff({ email: form.identifier, password: form.secret })
      dispatch({
        type: 'authSuccess',
        session,
        view: 'staff',
      })
      dispatch({ type: 'staff', patch: { section: session.role === 'admin' ? 'overview' : 'overview' } })
    } catch (error) {
      dispatch({ type: 'authFailure', message: error.userMessage || 'Sign in failed.' })
    }
  }

  const pairInstallation = async (form) => {
    if (!form.pairingCode || !form.serverName) {
      dispatch({ type: 'authFailure', message: 'Pairing code and server name are required.' })
      return
    }

    dispatch({ type: 'setupStart' })
    try {
      const status = await leafGateway.installation.pairInstallation(form)
      dispatch({ type: 'setupSuccess', status })
    } catch (error) {
      dispatch({ type: 'authFailure', message: error.userMessage || 'Pairing failed.' })
    }
  }

  const currentRole = state.session?.role || state.session?.type
  const signOut = async () => {
    if (state.session?.type === 'student') {
      await leafGateway.auth.logoutStudent().catch(() => null)
    }
    if (state.session?.type === 'staff') leafGateway.auth.signOutStaff()
    dispatch({ type: 'signOut' })
  }

  return (
    <div className="leaf-app" style={themeStyle}>
      {state.view === 'boot' && (
        <BootScreen
          error={state.bootError}
          retry={() => {
            dispatch({ type: 'bootStart' })
            leafGateway.installation
              .getInstallationStatus()
              .then((status) => dispatch({ type: 'bootSuccess', status }))
              .catch((error) => dispatch({ type: 'bootFailure', message: error.userMessage || 'Weave could not reach the local backend.' }))
          }}
        />
      )}
      {state.view === 'setup' && (
        <SetupScreen
          tenant={tenant}
          error={state.authError}
          loading={state.authLoading}
          onSubmit={pairInstallation}
          onContinue={() => dispatch({ type: 'view', view: 'auth' })}
        />
      )}
      {state.view === 'auth' && (
        <AuthPage
          mode={state.authMode}
          tenant={tenant}
          connectivity={state.connectivity}
          error={state.authError}
          loading={state.authLoading}
          setMode={(authMode) => dispatch({ type: 'authMode', authMode })}
          onSubmit={signIn}
        />
      )}
      {state.view === 'student' && (
        <StudentWorkspace
          exam={state.exam}
          resolution={state.studentResolution}
          gateway={leafGateway}
          dispatch={dispatch}
          returnToSignIn={signOut}
        />
      )}
      {state.view === 'staff' && currentRole === 'teacher' && (
        <TeacherWorkspace
          state={state}
          dispatch={dispatch}
          signOut={signOut}
          gateway={leafGateway}
        />
      )}
      {state.view === 'staff' && currentRole === 'admin' && (
        <AdminWorkspace
          state={state}
          dispatch={dispatch}
          signOut={signOut}
          gateway={leafGateway}
        />
      )}
    </div>
  )
}

function BootScreen({ error, retry }) {
  return (
    <main className="auth-shell">
      <section className="submission-card">
        <WeaveLogo />
        <h1>Starting Weave</h1>
        <p>Checking the local CBT backend and installation state.</p>
        {error && <Notice tone="danger">{error}</Notice>}
        {error && <button className="button button--primary" onClick={retry}>Try again</button>}
      </section>
    </main>
  )
}

function SetupScreen({ tenant, error, loading, onSubmit, onContinue }) {
  const [pairingCode, setPairingCode] = useState('')
  const [serverName, setServerName] = useState('')

  return (
    <main className="auth-shell">
      <div className="auth-shell__brand">
        <WeaveLogo />
        <TenantIdentity tenant={tenant} />
      </div>
      <div className="auth-shell__content auth-shell__content--centered">
        <section className="signin-card setup-card">
          <div className="signin-card__header">
            <h1>Pair Weave</h1>
            <p>Connect this CBT node to its Weave school account.</p>
          </div>
          <form
            className="form-grid"
            onSubmit={(event) => {
              event.preventDefault()
              onSubmit({ pairingCode, serverName })
            }}
          >
            <FormField label="Pairing Code" icon="link" value={pairingCode} placeholder="Enter Weave pairing code" onChange={setPairingCode} />
            <FormField label="Server Name" icon="school" value={serverName} placeholder="e.g. Brightfield CBT Lab" onChange={setServerName} />
            <Notice>If this CBT backend is already paired, continue to sign in.</Notice>
            {error && <Notice tone="danger">{error}</Notice>}
            <button className="button button--primary" type="submit" disabled={loading}>
              {loading ? 'Pairing...' : 'Pair Weave'}
            </button>
            <button className="button button--secondary" type="button" onClick={onContinue}>
              Continue to sign in
            </button>
          </form>
        </section>
      </div>
    </main>
  )
}
