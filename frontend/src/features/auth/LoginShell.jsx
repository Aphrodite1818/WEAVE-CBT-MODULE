import { Icon } from '../../shared/icons/Icon'
import { Notice, WeaveLogo } from '../../shared/ui'
import { getLocalBrandLogoSrc } from '../../api/branding'
import './auth.css'

export function LoginShell({ title, subtitle, imageAlt, children, error, loading, onSubmit, onBack, branding }) {
  return (
    <main className="weave-login-page">
      <header className="weave-login-header"><div><WeaveLogo />{getLocalBrandLogoSrc(branding) && <img className="weave-login-school-logo" src={getLocalBrandLogoSrc(branding)} alt={`${branding.school_name} logo`} />}</div><button onClick={onBack}><Icon name="back" /> Back to Home</button></header>
      <div className="weave-login-layout">
        <section className="weave-login-intro">
          <span>{branding?.is_enabled ? branding.school_name : 'WEAVE CBT'}</span>
          <h1>{title}</h1>
          <p>{subtitle}</p>
          <img src="/student-hero.jpg" alt={imageAlt} />
        </section>
        <section className="weave-login-card">
          <div className="weave-login-card__icon"><Icon name={title.includes('Student') ? 'school' : 'staff'} size={29} /></div>
          <h2>Sign in</h2>
          <p>Enter your details to continue.</p>
          <form onSubmit={(event) => { event.preventDefault(); onSubmit() }}>
            {children}
            {error && <Notice tone="danger">{error}</Notice>}
            <button className="setup-primary" type="submit" disabled={loading}>{loading ? 'Checking...' : 'Sign In'} <Icon name="arrow" /></button>
          </form>
        </section>
      </div>
      <footer className="weave-login-footer">Weave CBT • Secure. Reliable. Built for Schools.</footer>
    </main>
  )
}
