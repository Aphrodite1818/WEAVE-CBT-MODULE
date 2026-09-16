import { StudentLoginPage } from '../features/auth/StudentLoginPage'
import { LandingPage } from '../features/landing/LandingPage'
import { StudentWorkspace } from '../features/student/StudentWorkspace'
import { buildBrandingThemeStyle, createDefaultBranding } from './theme/branding'
import { weaveGateway } from './gateway'
import { ProductLoadingScreen } from './ProductLoadingScreen'
import { useAppController } from './useAppController'

export default function StudentApp() {
  const { state, dispatch, boot, signInStudent, signOut } = useAppController({ application: 'student' })
  const branding = state.installation.configured ? state.branding : createDefaultBranding()

  return (
    <div className="weave-app" style={buildBrandingThemeStyle(branding)}>
      {state.view === 'boot' && (
        <ProductLoadingScreen
          title="Starting Weave"
          copy="Checking the local CBT server and installation state."
          error={state.bootError}
          onRetry={() => boot()}
        />
      )}
      {state.view === 'student-unavailable' && (
        <ProductLoadingScreen
          title="CBT server not ready"
          copy="This CBT server has not been configured yet. Ask a school administrator to complete setup from the staff application."
        />
      )}
      {state.view === 'landing' && <LandingPage dispatch={dispatch} audience="student" branding={branding} />}
      {state.view === 'student-login' && (
        <StudentLoginPage
          error={state.authError}
          loading={state.authLoading}
          branding={branding}
          onSubmit={signInStudent}
          onBack={() => dispatch({ type: 'view', view: 'landing' })}
        />
      )}
      {state.view === 'student' && (
        <StudentWorkspace
          exam={state.exam}
          resolution={state.studentResolution}
          gateway={weaveGateway}
          dispatch={dispatch}
          returnToSignIn={signOut}
        />
      )}
    </div>
  )
}
