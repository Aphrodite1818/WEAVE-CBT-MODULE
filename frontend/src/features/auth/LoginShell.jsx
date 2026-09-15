import { useState } from 'react'
import { Pictogram } from '../../shared/icons/Pictogram'
import { Notice, WeaveLogo } from '../../shared/ui'
import './auth.css'

const benefitSets = {
  staff: [
    ['shield', 'Secure', 'Your data, our priority.'],
    ['bolt', 'Reliable', 'Always ready.'],
    ['staff', 'Built for Schools', 'Empowering education.'],
    ['chart', 'Better Outcomes', 'Together we achieve more.'],
  ],
  student: [
    ['student', 'Focus', 'Take your exams with confidence.'],
    ['bolt', 'Reliable', 'Always ready.'],
    ['student', 'Built for You', 'Supporting your journey.'],
    ['chart', 'Brighter Futures', 'Today’s effort. Tomorrow’s possibilities.'],
  ],
}

export function LoginField({ label, type = 'text', icon, value, onChange, placeholder, autoComplete, required = true }) {
  const [visible, setVisible] = useState(false)
  const resolvedType = type === 'password' && visible ? 'text' : type

  return (
    <label className="login-field">
      <span>{label}</span>
      <span className="login-field__control">
        <Pictogram name={icon} size={20} />
        <input
          type={resolvedType}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          autoComplete={autoComplete}
          required={required}
        />
        {type === 'password' && (
          <button type="button" className="login-field__reveal" onClick={() => setVisible((current) => !current)} aria-label={visible ? 'Hide password' : 'Show password'}>
            <span aria-hidden="true">{visible ? '◉' : '○'}</span>
          </button>
        )}
      </span>
    </label>
  )
}

export function LoginShell({ kind, title, subtitle, children, error, loading, onSubmit, onBack }) {
  const isStudent = kind === 'student'
  const benefits = benefitSets[kind] || benefitSets.student
  const artSrc = isStudent ? '/visuals/student-login.webp' : '/visuals/staff-login.webp'

  return (
    <main className={`weave-login-page weave-login-page--${kind}`}>
      <header className="weave-login-header">
        <div className="weave-login-brand">
          <WeaveLogo />
          <small>Exams made simple.</small>
        </div>
      </header>

      <div className="weave-login-content">
        <button className="weave-login-back" type="button" onClick={onBack}><Pictogram name="back" size={18} /> Back to Home</button>

        <div className="weave-login-layout">
          <section className="weave-login-card">
            <div className="weave-login-card__icon"><Pictogram name={isStudent ? 'student' : 'staff'} size={30} /></div>
            <h1>{title}</h1>
            <p>{subtitle}</p>
            <form onSubmit={(event) => { event.preventDefault(); onSubmit() }}>
              {children}
              {error && <Notice tone="danger">{error}</Notice>}
              <button className="weave-login-submit" type="submit" disabled={loading}>
                {loading ? 'Checking...' : 'Sign In'}
                {!loading && <Pictogram name="arrow" size={20} />}
              </button>
            </form>
            <div className="weave-login-trust"><Pictogram name="shield" size={18} /> {isStudent ? 'Your exams. Your future. Our support.' : 'Secure access for school staff'}</div>
          </section>

          <section className="weave-login-art" aria-label={isStudent ? 'Student exam illustration' : 'School staff illustration'}>
            <img src={artSrc} alt="" aria-hidden="true" />
          </section>
        </div>

        <section className="weave-login-benefits" aria-label="Weave CBT benefits">
          {benefits.map(([icon, heading, helper]) => (
            <div key={heading}>
              <span><Pictogram name={icon} size={22} /></span>
              <strong>{heading}</strong>
              <small>{helper}</small>
            </div>
          ))}
        </section>
      </div>

      <footer className="weave-login-footer">
        <span><b>Weave CBT</b> • Local Today. Brighter Tomorrow.</span>
        <span><i />More than exams. A brighter tomorrow.</span>
      </footer>
    </main>
  )
}
