import { useState } from 'react'
import { FormField, Notice, SegmentedControl, WeaveLogo } from '../../shared/ui'
import './auth.css'

export function AuthPage({ mode, connectivity, error, loading, setMode, onSubmit }) {
  const [identifier, setIdentifier] = useState('')
  const [secret, setSecret] = useState('')
  const offlineStudent = connectivity === 'weave-offline' && mode === 'student'

  return (
    <main className="premium-auth-shell">
      <div className="premium-auth-container">
        <div className="premium-auth-left">
          <div className="premium-auth-brand">
            <WeaveLogo />
            {mode === 'student' && <span className="premium-auth-pill">Student Access</span>}
            {mode === 'staff' && <span className="premium-auth-pill">Staff Access</span>}
          </div>
          <div className="premium-auth-hero">
            <h1>Focused Minds<br/>Brighter Futures</h1>
            <p>A secure and seamless exam experience.</p>
            <div className="premium-auth-illustration">
              <img src="/student-hero.jpg" alt="Student using Weave CBT" />
            </div>
          </div>
        </div>
        <div className="premium-auth-right">
          <div className="premium-signin-card">
            <h2>Sign in to start your exam</h2>
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
              className="premium-form-grid"
              onSubmit={(event) => {
                event.preventDefault()
                onSubmit({ identifier, secret })
              }}
            >
              <div className="premium-form-group">
                <label>{mode === 'student' ? 'Admission Number' : 'Email'}</label>
                <FormField
                  icon="mail"
                  placeholder={mode === 'student' ? 'e.g. ADM2024001' : 'Enter your email'}
                  value={identifier}
                  type={mode === 'student' ? 'text' : 'email'}
                  onChange={setIdentifier}
                />
              </div>
              <div className="premium-form-group">
                <label>{mode === 'student' ? 'Access Code / Password' : 'Password'}</label>
                <FormField
                  icon="lock"
                  placeholder={mode === 'student' ? '••••••••' : 'Enter your password'}
                  value={secret}
                  type="password"
                  onChange={setSecret}
                />
              </div>
              {offlineStudent && <Notice tone="success">Offline student authentication is available locally.</Notice>}
              {mode === 'staff' && connectivity === 'weave-offline' && (
                <Notice tone="warning">Staff sign-in is paused until Weave connectivity returns.</Notice>
              )}
              {error && <Notice tone="danger">{error}</Notice>}
              <button className="premium-btn-primary full-width" type="submit" disabled={loading}>
                {loading ? 'Checking...' : 'Sign In'}
              </button>
            </form>
            <div className="premium-forgot-link">
              <button type="button">Forgot access code?</button>
            </div>
          </div>
          <div className="premium-auth-footer">
            <span>WEAVE CBT</span>
            <span>Secure &middot; Reliable &middot; Built for Schools</span>
          </div>
        </div>
      </div>
    </main>
  )
}
