import { useState } from 'react'
import { PublicLayout } from '../layouts/PublicLayout'
import { Button, Field } from '../components/Ui'
import { Icon } from '../lib/icons'

export function SetupPage({ configured = false, onComplete, onContinue }) {
  const [code, setCode] = useState('')
  const [state, setState] = useState('idle')

  const submit = (event) => {
    event.preventDefault()
    if (!code.trim()) return setState('error')
    setState('loading')
    window.setTimeout(() => onComplete(), 550)
  }

  return <PublicLayout minimal>
    <section className="setup-wrap">
      <div className="setup-intro">
        <span className="eyebrow">First-time installation</span>
        <h1>Connect this CBT workspace to your school.</h1>
        <p>Enter the setup code generated from Weave to prepare this installation for Brightfield Academy.</p>
        <div className="setup-points">
          <span><Icon name="shield" /> Secure local assessment workspace</span>
          <span><Icon name="check" /> School settings stay managed in Weave</span>
        </div>
      </div>
      <form className="auth-card setup-card" onSubmit={submit}>
        <div className="card-icon"><Icon name="link" size={24} /></div>
        <span className="eyebrow">Installation setup</span>
        <h2>{configured ? 'Installation configured' : 'Enter your setup code'}</h2>
        <p>{configured ? 'This prototype is ready to use.' : 'Copy the one-time code from your Weave school workspace.'}</p>
        {!configured && <>
          <Field label="Setup code" value={code} onChange={(e) => { setCode(e.target.value.toUpperCase()); setState('idle') }} placeholder="e.g. WCBT-7K9P-2MX4" autoFocus />
          {state === 'error' && <div className="form-message form-message--error">Enter a setup code to continue.</div>}
          <Button type="submit" disabled={state === 'loading'} icon="arrow">{state === 'loading' ? 'Verifying…' : 'Verify & Continue'}</Button>
        </>}
        {configured && <Button type="button" onClick={onContinue} icon="arrow">Continue to welcome</Button>}
        <small className="form-note"><Icon name="lock" size={14} /> Prototype verification only. No data is sent.</small>
      </form>
    </section>
  </PublicLayout>
}
