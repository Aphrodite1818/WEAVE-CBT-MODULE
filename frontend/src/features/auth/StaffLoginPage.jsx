import { useState } from 'react'
import { LoginField, LoginShell } from './LoginShell'

export function StaffLoginPage({ error, loading, branding, onSubmit, onBack }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  return (
    <LoginShell
      kind="staff"
      branding={branding}
      title="Staff Login"
      subtitle="Access your CBT staff account"
      error={error}
      loading={loading}
      onBack={onBack}
      onSubmit={() => onSubmit({ email: email.trim(), password })}
    >
      <LoginField
        label="Email Address"
        type="email"
        autoComplete="username"
        value={email}
        onChange={setEmail}
        placeholder="you@school.edu.ng"
      />
      <LoginField
        label="Password"
        type="password"
        autoComplete="current-password"
        value={password}
        onChange={setPassword}
        placeholder="Enter your password"
      />
    </LoginShell>
  )
}
