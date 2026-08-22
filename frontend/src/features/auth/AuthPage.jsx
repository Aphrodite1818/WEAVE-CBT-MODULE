import { useState } from 'react'
import { FormField, LeafLogo, Notice, SegmentedControl, TenantIdentity } from '../../components/ui'

function AuthShell({ tenant, children }) {
  return (
    <main className="auth-shell">
      <div className="auth-shell__brand">
        <LeafLogo />
        <TenantIdentity tenant={tenant} />
      </div>
      <div className="auth-shell__content auth-shell__content--centered">
        {children}
      </div>
    </main>
  )
}

export function AuthPage({ mode, tenant, connectivity, error, loading, setMode, onSubmit }) {
  const [identifier, setIdentifier] = useState('')
  const [secret, setSecret] = useState('')
  const offlineStudent = connectivity === 'weave-offline' && mode === 'student'

  return (
    <AuthShell tenant={tenant}>
      <section className="signin-card">
        <div className="signin-card__header">
          <h1>Welcome back</h1>
          <p>Sign in to continue</p>
        </div>
        <SegmentedControl
          label="Sign in type"
          value={mode}
          options={[
            ['student', 'Student'],
            ['staff', 'Staff'],
          ]}
          onChange={setMode}
        />
        <form
          className="form-grid"
          onSubmit={(event) => {
            event.preventDefault()
            onSubmit({ identifier, secret })
          }}
        >
          <FormField
            label={mode === 'student' ? 'Admission Number' : 'Email'}
            icon="mail"
            placeholder={mode === 'student' ? 'Enter your admission number' : 'Enter your email'}
            value={identifier}
            type={mode === 'student' ? 'text' : 'email'}
            onChange={setIdentifier}
          />
          <FormField
            label={mode === 'student' ? 'CBT PIN' : 'Password'}
            icon="lock"
            placeholder={mode === 'student' ? 'Enter your CBT PIN' : 'Enter your password'}
            value={secret}
            type="password"
            onChange={setSecret}
          />
          {offlineStudent && <Notice tone="success">Offline student authentication is available locally.</Notice>}
          {mode === 'staff' && connectivity === 'weave-offline' && (
            <Notice tone="warning">Staff sign-in is paused until Weave connectivity returns.</Notice>
          )}
          {error && <Notice tone="danger">{error}</Notice>}
          <button className="button button--primary" type="submit" disabled={loading}>
            {loading ? 'Checking...' : 'Sign in'}
          </button>
        </form>
        <div className="signin-card__help">
          <span>Need help?</span>
          <button type="button">Contact your administrator</button>
        </div>
      </section>
    </AuthShell>
  )
}
