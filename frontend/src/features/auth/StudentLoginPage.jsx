import { useState } from 'react'
import { LoginShell } from './LoginShell'

export function StudentLoginPage({ error, loading, onSubmit, onBack, branding }) {
  const [admissionNumber, setAdmissionNumber] = useState('')
  const [password, setPassword] = useState('')
  return <LoginShell title="Student Login" subtitle="Your exams are ready when you are." imageAlt="Student using Weave CBT" error={error} loading={loading} onBack={onBack} branding={branding} onSubmit={() => onSubmit({ admissionNumber: admissionNumber.trim(), password })}>
    <label htmlFor="student-admission">Admission Number</label><input id="student-admission" autoComplete="username" required value={admissionNumber} onChange={(event) => setAdmissionNumber(event.target.value)} placeholder="Enter your admission number" />
    <label htmlFor="student-password">Password</label><input id="student-password" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Enter your password" />
  </LoginShell>
}
