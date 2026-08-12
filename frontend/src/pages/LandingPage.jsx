import { PublicLayout } from '../layouts/PublicLayout'
import { Brand } from '../components/Brand'
import { Icon } from '../lib/icons'

export function LandingPage({ navigate, resetSetup }) {
  return <PublicLayout>
    <section className="welcome-hero">
      <div className="welcome-copy">
        <span className="eyebrow">Brightfield Academy · Assessment portal</span>
        <h1>Focused exams.<br />Clear outcomes.</h1>
        <p>One calm, secure workspace for creating assessments, supervising candidates, and taking exams.</p>
        <div className="session-note"><span className="live-dot" /> CBT services available <small>2025/2026 Academic Session</small></div>
      </div>
      <div className="portal-stack">
        <button className="portal-card" onClick={() => navigate('/staff-login')}>
          <span className="portal-card__icon"><Icon name="staff" size={25} /></span>
          <span><small>For administrators & teachers</small><strong>Staff Login</strong><em>Manage exams and results</em></span>
          <Icon name="arrow" />
        </button>
        <button className="portal-card portal-card--student" onClick={() => navigate('/student-login')}>
          <span className="portal-card__icon"><Icon name="exam" size={25} /></span>
          <span><small>For enrolled students</small><strong>Take an Exam</strong><em>Admission number and exam PIN required</em></span>
          <Icon name="arrow" />
        </button>
        <button className="text-link" onClick={() => navigate('/result-details')}>View a released result <Icon name="arrow" size={15} /></button>
      </div>
    </section>
    <section className="trust-strip"><Brand compact /><span>Purpose-built for Nigerian schools</span><span>Readable by design</span><span>Mock data only</span></section>
    <button className="prototype-reset" onClick={resetSetup}>Reset prototype installation</button>
  </PublicLayout>
}
