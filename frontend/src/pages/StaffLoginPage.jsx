import { useState } from 'react'
import { PublicLayout } from '../layouts/PublicLayout'
import { Button, Field } from '../components/Ui'
import { Icon } from '../lib/icons'

export function StaffLoginPage({ navigate, onLogin }) {
  const [role, setRole] = useState('admin')
  const [loading, setLoading] = useState(false)
  const submit = (event) => {
    event.preventDefault()
    setLoading(true)
    window.setTimeout(() => onLogin(role), 450)
  }
  return <PublicLayout minimal>
    <section className="auth-page">
      <button className="back-link" onClick={() => navigate('/welcome')}><Icon name="back" /> Back to portal</button>
      <form className="auth-card" onSubmit={submit}>
        <div className="card-icon"><Icon name="staff" size={24} /></div>
        <span className="eyebrow">Staff workspace</span>
        <h1>Welcome back</h1>
        <p>Sign in to manage your school’s assessments.</p>
        <div className="segmented" aria-label="Choose staff role">
          <button type="button" className={role === 'admin' ? 'active' : ''} onClick={() => setRole('admin')}>Administrator</button>
          <button type="button" className={role === 'teacher' ? 'active' : ''} onClick={() => setRole('teacher')}>Teacher</button>
        </div>
        <Field label="Email or username" type="text" defaultValue={role === 'admin' ? 'amara.okafor' : 'chidi.adebayo'} required />
        <Field label="Password" type="password" defaultValue="password" required />
        <div className="form-row"><label className="checkbox"><input type="checkbox" /> Keep me signed in</label><button type="button" className="text-button">Forgot password?</button></div>
        <Button type="submit" disabled={loading} icon="arrow">{loading ? 'Signing in…' : `Sign in as ${role}`}</Button>
        <small className="form-note"><Icon name="lock" size={14} /> Mock sign-in accepts the prefilled details.</small>
      </form>
    </section>
  </PublicLayout>
}
