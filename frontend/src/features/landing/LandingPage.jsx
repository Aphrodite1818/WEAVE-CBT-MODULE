import { Icon } from '../../shared/icons/Icon'
import { WeaveLogo } from '../../shared/ui'
import { getLocalBrandLogoSrc } from '../../api/branding'
import './landing.css'

export function LandingPage({ dispatch, branding }) {
  const schoolLogo = getLocalBrandLogoSrc(branding)
  return (
    <main className="landing-page">
      <header className="landing-header">
        <div><WeaveLogo /><small>Exams made simple.</small>{schoolLogo && <img className="landing-school-logo" src={schoolLogo} alt={`${branding.school_name} logo`} />}</div>
        <nav aria-label="Sign in"><button onClick={() => dispatch({ type: 'view', view: 'student-login' })}><Icon name="school" /> Login as Student</button><button className="landing-header__primary" onClick={() => dispatch({ type: 'view', view: 'staff-login' })}><Icon name="staff" /> Login as Staff</button></nav>
      </header>
      <section className="landing-hero">
        <div className="landing-hero__copy">
          <span>W E L C O M E &nbsp; T O</span>
          <WeaveLogo size="large" />
          <h1>A smarter way to take exams.</h1>
          <p>Secure. Reliable. Built for Schools.</p>
          {branding?.is_enabled && branding?.school_name && <small className="landing-school">For {branding.school_name}</small>}
        </div>
        <img className="landing-hero__image" src="/student-hero.jpg" alt="Student preparing to take an exam with Weave CBT" />
      </section>
      <section className="landing-benefits" aria-label="Weave CBT benefits">
        <div><span><Icon name="shield" size={27} /></span><strong>Secure &amp; Trusted</strong><small>Your exams, your security</small></div>
        <div><span><Icon name="bolt" size={27} /></span><strong>Built for Schools</strong><small>Powerful. Lightweight. Reliable.</small></div>
        <div><span><Icon name="results" size={27} /></span><strong>Offline Ready</strong><small>Keeps exams running</small></div>
        <div><span><Icon name="users" size={27} /></span><strong>Better Outcomes</strong><small>For every learner</small></div>
      </section>
      <footer className="landing-footer"><span><b>Weave CBT</b> • Local Today. Brighter Tomorrow.</span><span>More than exams. A brighter tomorrow.</span></footer>
    </main>
  )
}
