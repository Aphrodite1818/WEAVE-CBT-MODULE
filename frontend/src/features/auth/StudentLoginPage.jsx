import { useState } from 'react'
import { LoginField, LoginShell } from './LoginShell'

export function StudentLoginPage({ error, loading, branding, onSubmit, onBack }) {
  const [admissionNumber, setAdmissionNumber] = useState('')
  const [password, setPassword] = useState('')

  return (
    <LoginShell
      kind="student"
      branding={branding}
      title="Student Login"
      subtitle="Access your CBT exam account"
      error={error}
      loading={loading}
      onBack={onBack}
      onSubmit={() => onSubmit({ admissionNumber: admissionNumber.trim(), password })}
    >
      <LoginField
        label="Admission Number"
        autoComplete="username"
        value={admissionNumber}
        onChange={setAdmissionNumber}
        placeholder="Enter your admission number"
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
