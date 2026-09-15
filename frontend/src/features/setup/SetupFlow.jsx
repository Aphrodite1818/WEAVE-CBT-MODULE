import { useState } from 'react'
import { Icon } from '../../shared/icons/Icon'
import { Notice, WeaveLogo } from '../../shared/ui'
import './setup.css'

export function SetupFlow({ view, error, installation, dispatch, onPair }) {
  const [pairingCode, setPairingCode] = useState('')
  const [serverName, setServerName] = useState('')
  const [localError, setLocalError] = useState('')

  const nextCode = () => {
    if (pairingCode.trim().length < 8 || pairingCode.trim().length > 20) {
      setLocalError('Enter the complete pairing code (8–20 characters).')
      return
    }
    setLocalError('')
    dispatch({ type: 'view', view: 'server-name' })
  }

  const submitName = () => {
    if (serverName.trim().length < 2 || serverName.trim().length > 150) {
      setLocalError('Use a server name between 2 and 150 characters.')
      return
    }
    setLocalError('')
    onPair({ pairingCode: pairingCode.trim().toUpperCase(), serverName: serverName.trim() })
  }

  return (
    <main className="setup-shell">
      <header className="setup-header"><WeaveLogo /><span>EXAMS MADE SIMPLE</span></header>
      {view === 'welcome' && (
        <section className="setup-welcome setup-enter">
          <div className="setup-welcome__copy">
            <span className="setup-eyebrow">EXAMS MADE SIMPLE</span>
            <h1>Welcome to<br />Weave <em>CBT</em></h1>
            <p>This CBT server needs to be connected to your school’s Weave account before it can be used.</p>
            <button className="setup-primary" onClick={() => dispatch({ type: 'view', view: 'pairing-code' })}>Get Started <Icon name="arrow" /></button>
            <small>Already paired on this device? The app will open the landing page automatically when the local server reports it is configured.</small>
          </div>
          <div className="setup-welcome__visual" aria-hidden="true">
            <div className="setup-visual-card"><Icon name="shield" size={34} /><strong>Secure</strong></div>
            <div className="setup-visual-card"><Icon name="sync" size={34} /><strong>Offline Ready</strong></div>
            <div className="setup-visual-card"><Icon name="school" size={34} /><strong>Reliable</strong></div>
          </div>
        </section>
      )}
      {view === 'pairing-code' && (
        <section className="setup-card setup-enter">
          <div className="setup-icon"><Icon name="link" size={30} /></div>
          <h1>Enter Pairing Code</h1>
          <p>Use the pairing code from your Weave school account to connect this server.</p>
          <form onSubmit={(event) => { event.preventDefault(); nextCode() }}>
            <label className="setup-code-label" htmlFor="pairing-code">Pairing Code</label>
            <input id="pairing-code" className="setup-code-input" autoFocus autoComplete="one-time-code" maxLength="20" value={pairingCode} onChange={(event) => { setPairingCode(event.target.value.toUpperCase()); setLocalError('') }} placeholder="Enter or paste code" />
            <div className="setup-code-tiles" aria-hidden="true">{Array.from({ length: 8 }, (_, index) => <span key={index}>{pairingCode[index] || ''}</span>)}</div>
            {localError && <Notice tone="danger">{localError}</Notice>}
            <button className="setup-primary" type="submit">Continue <Icon name="arrow" /></button>
          </form>
          <button className="setup-back" onClick={() => dispatch({ type: 'view', view: 'welcome' })}><Icon name="back" /> Back</button>
        </section>
      )}
      {view === 'server-name' && (
        <section className="setup-card setup-enter">
          <div className="setup-icon"><Icon name="school" size={30} /></div>
          <h1>Set a server name</h1>
          <p>Give this CBT server a name to easily identify it in your Weave account.</p>
          <form onSubmit={(event) => { event.preventDefault(); submitName() }}>
            <label htmlFor="server-name">Server Name</label>
            <input id="server-name" autoFocus maxLength="150" value={serverName} onChange={(event) => { setServerName(event.target.value); setLocalError('') }} placeholder="e.g. Main Lab, Block A, School Hall" />
            {localError && <Notice tone="danger">{localError}</Notice>}
            <button className="setup-primary" type="submit">Complete Setup <Icon name="arrow" /></button>
          </form>
          <button className="setup-back" onClick={() => dispatch({ type: 'view', view: 'pairing-code' })}><Icon name="back" /> Back</button>
        </section>
      )}
      {view === 'pairing' && (
        <section className="setup-card setup-enter" aria-live="polite">
          <div className={`setup-icon ${error ? 'setup-icon--error' : 'setup-icon--busy'}`}><Icon name={error ? 'info' : 'sync'} size={32} /></div>
          <h1>{error ? 'Pairing needs attention' : 'Pairing with Weave...'}</h1>
          <p>{error ? 'The server is still unpaired. Review the message and retry with the same details.' : 'Verifying your code and connecting this server to your school account.'}</p>
          {error ? <Notice tone="danger">{error}</Notice> : <div className="setup-activity"><span>Processing the pairing request</span><span className="setup-dots">● ● ●</span></div>}
          {error && <button className="setup-primary" onClick={submitName}>Retry Pairing <Icon name="arrow" /></button>}
          {error && <button className="setup-back" onClick={() => dispatch({ type: 'view', view: 'server-name' })}><Icon name="back" /> Edit server name</button>}
        </section>
      )}
      {view === 'paired-success' && (
        <section className="setup-card setup-enter">
          <div className="setup-icon setup-icon--success"><Icon name="check" size={34} /></div>
          <h1>Successfully Paired!</h1>
          <p>This CBT server is now connected to {installation.status?.tenant_name || 'your Weave school account'}.</p>
          <div className="setup-activity">Your server is set up and ready for sign in. School data may still be preparing in the background.</div>
          <button className="setup-primary" onClick={() => dispatch({ type: 'view', view: 'landing' })}>Continue to Home <Icon name="arrow" /></button>
        </section>
      )}
      <footer className="setup-footer"><span>WEAVE CBT&nbsp; • &nbsp;EXAMS MADE SIMPLE</span><span>LOCAL TODAY. BRIGHTER TOMORROW.</span></footer>
    </main>
  )
}
