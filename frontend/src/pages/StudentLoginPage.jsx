import { useState } from 'react'
import { PublicLayout } from '../layouts/PublicLayout'
import { Button, Field } from '../components/Ui'
import { Icon } from '../lib/icons'

export function StudentLoginPage({ navigate }) {
  const [loading, setLoading] = useState(false)
  const submit = (event) => {
    event.preventDefault()
    setLoading(true)
    window.setTimeout(() => navigate('/exam'), 500)
  }
  return <PublicLayout minimal>
    <section className="student-auth-page">
      <button className="back-link" onClick={() => navigate('/welcome')}><Icon name="back" /> Back to portal</button>
      <div className="student-auth-context">
        <span className="eyebrow">Candidate access</span>
        <h1>Ready when you are.</h1>
        <p>Have your admission number and one-time exam PIN ready. Your timer starts only after the instructions page.</p>
        <div className="exam-preview"><span><Icon name="book" /></span><div><small>Available assessment</small><strong>SS2 Biology Mock Examination</strong><em>10 questions · 20 minutes</em></div></div>
      </div>
      <form className="auth-card student-login-card" onSubmit={submit}>
        <div className="candidate-number">01</div>
        <h2>Enter exam details</h2>
        <p>Use the details provided by your invigilator.</p>
        <Field label="Admission number" defaultValue="BFA/2024/0187" required />
        <Field label="One-time exam PIN" defaultValue="829461" inputMode="numeric" maxLength="6" required />
        <Button type="submit" disabled={loading} icon="arrow">{loading ? 'Checking details…' : 'Continue to exam'}</Button>
        <div className="help-note"><Icon name="info" /><span><strong>Having trouble?</strong> Ask the invigilator before trying again.</span></div>
      </form>
    </section>
  </PublicLayout>
}
