import { Pictogram } from '../../shared/icons/Pictogram'
import { WeaveLogo } from '../../shared/ui'
import './landing.css'

const benefits = [
  ['shield', 'Secure & Trusted', 'Your exams, your security'],
  ['bolt', 'Built for Schools', 'Powerful. Lightweight. Reliable.'],
  ['chart', 'Offline Ready', 'Keeps exams running'],
  ['staff', 'Better Outcomes', 'For every learner'],
]

export function LandingPage({ dispatch }) {
  return (
    <main className="landing-page">
      <header className="landing-header">
        <div className="landing-brand">
          <WeaveLogo />
          <small>Exams made simple.</small>
        </div>
        <nav aria-label="Sign in" className="landing-actions">
          <button className="landing-action landing-action--student" onClick={() => dispatch({ type: 'view', view: 'student-login' })}>
            <Pictogram name="student" size={22} />
            Login as Student
          </button>
          <button className="landing-action landing-action--staff" onClick={() => dispatch({ type: 'view', view: 'staff-login' })}>
            <Pictogram name="staff" size={22} />
            Login as Staff
          </button>
        </nav>
      </header>

      <section className="landing-hero">
        <div className="landing-hero__copy">
          <span className="product-kicker">WELCOME TO</span>
          <WeaveLogo size="large" />
          <h1>A smarter way to take exams.</h1>
          <p>Secure. Reliable. Built for Schools.</p>
        </div>

        <div className="landing-scene-shell">
          <img className="landing-scene" src="/visuals/landing-scene.webp" alt="Student preparing to take an exam with Weave CBT" />
        </div>
      </section>

      <section className="landing-benefits" aria-label="Weave CBT benefits">
        {benefits.map(([icon, title, helper]) => (
          <div key={title} className="landing-benefit">
            <span className="landing-benefit__icon"><Pictogram name={icon} size={24} /></span>
            <strong>{title}</strong>
            <small>{helper}</small>
          </div>
        ))}
      </section>

      <footer className="landing-footer">
        <span><b>Weave CBT</b><i />Local Today. Brighter Tomorrow.</span>
        <span><i />More than exams. A brighter tomorrow.</span>
      </footer>
    </main>
  )
}
