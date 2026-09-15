import { useState } from 'react'
import { LoginShell } from './LoginShell'

export function StaffLoginPage({ error, loading, onSubmit, onBack, branding }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  return <LoginShell title="Staff Login" subtitle="Welcome back. Access your school’s CBT workspace." imageAlt="Weave CBT student illustration" error={error} loading={loading} onBack={onBack} branding={branding} onSubmit={() => onSubmit({ email: email.trim(), password })}>
    <label htmlFor="staff-email">Email</label><input id="staff-email" type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Enter your email" />
    <label htmlFor="staff-password">Password</label><input id="staff-password" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Enter your password" />
  </LoginShell>
}
