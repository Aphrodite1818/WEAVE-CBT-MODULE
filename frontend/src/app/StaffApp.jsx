import { AdminWorkspace } from '../features/admin/AdminWorkspace'
import { StaffLoginPage } from '../features/auth/StaffLoginPage'
import { LandingPage } from '../features/landing/LandingPage'
import { SetupFlow } from '../features/setup/SetupFlow'
import { isSetupView } from '../features/setup/setupViews'
import { InitialSyncPage } from '../features/sync/InitialSyncPage'
import { TeacherWorkspace } from '../features/teacher/TeacherWorkspace'
import { buildBrandingThemeStyle, createDefaultBranding } from './theme/branding'
import { weaveGateway } from './gateway'
import { ProductLoadingScreen } from './ProductLoadingScreen'
import { useAppController } from './useAppController'

export default function StaffApp() {
  const { state, dispatch, boot, pair, signInStaff, signOut } = useAppController({ application: 'staff' })
  const branding = state.installation.configured ? state.branding : createDefaultBranding()
  const currentRole = state.session?.role || state.session?.type

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
      {isSetupView(state.view) && (
        <SetupFlow
          view={state.view}
          error={state.authError}
          installation={state.installation}
          dispatch={dispatch}
          onPair={pair}
        />
      )}
      {state.view === 'landing' && <LandingPage dispatch={dispatch} audience="staff" branding={branding} />}
      {state.view === 'staff-login' && (
        <StaffLoginPage
          error={state.authError}
          loading={state.authLoading}
          branding={branding}
          onSubmit={signInStaff}
          onBack={() => dispatch({ type: 'view', view: 'landing' })}
        />
      )}
      {state.view === 'sync-check' && (
        <ProductLoadingScreen
          title="Checking server readiness"
          copy="Reading the local synchronization status."
        />
      )}
      {state.view === 'initial-sync' && (
        <InitialSyncPage
          error={state.syncError}
          status={state.syncStatus}
          branding={branding}
          dispatch={dispatch}
        />
      )}
      {state.view === 'staff' && currentRole === 'teacher' && (
        <TeacherWorkspace
          state={state}
          dispatch={dispatch}
          signOut={signOut}
          gateway={weaveGateway}
        />
      )}
      {state.view === 'staff' && currentRole === 'admin' && (
        <AdminWorkspace
          state={state}
          dispatch={dispatch}
          signOut={signOut}
          gateway={weaveGateway}
        />
      )}
    </div>
  )
}
