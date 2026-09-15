import { Icon } from '../../shared/icons/Icon'
import { Notice, WeaveLogo } from '../../shared/ui'
import { getLocalBrandLogoSrc } from '../../api/branding'
import { useInitialSyncStatus } from './useInitialSyncStatus'
import './sync.css'

const stages = [
  'Connecting to school data',
  'Preparing academic structure',
  'Preparing student records',
  'Preparing teacher assignments',
  'Finalizing local CBT environment',
]

export function InitialSyncPage({ error, status, dispatch, branding }) {
  const { readyAnimation, retrying, retry } = useInitialSyncStatus(dispatch)
  return (
    <main className="initial-sync-page">
      <header><WeaveLogo />{getLocalBrandLogoSrc(branding) && <img className="initial-sync-school-logo" src={getLocalBrandLogoSrc(branding)} alt={`${branding.school_name} logo`} />}</header>
      <section className="initial-sync-card" aria-live="polite">
        <div className={`initial-sync-icon ${readyAnimation ? 'initial-sync-icon--ready' : ''}`}><Icon name={readyAnimation ? 'check' : 'sync'} size={34} /></div>
        <span className="initial-sync-eyebrow">WEAVE CBT SERVER</span>
        <h1>{readyAnimation ? 'Your server is ready' : 'Preparing your CBT server'}</h1>
        <p>{readyAnimation ? 'School data is ready. Opening your workspace.' : 'Your local server is receiving the school data it needs. You can leave this page open while setup continues.'}</p>
        {!readyAnimation && <div className="initial-sync-stages">{stages.map((stage) => <div key={stage}><span className="initial-sync-stage-dot" /><span>{stage}</span></div>)}</div>}
        {!readyAnimation && <div className="initial-sync-rail" aria-hidden="true"><span /></div>}
        {!readyAnimation && <small>Readiness is checked against the local server. These stages are visual guidance.</small>}
        {(error || status?.last_error) && !readyAnimation && <div className="initial-sync-error"><Notice tone="danger">{error || status.last_error}</Notice><button onClick={retry} disabled={retrying}>{retrying ? 'Retrying...' : 'Retry synchronization'}</button></div>}
      </section>
      <footer>WEAVE CBT • LOCAL TODAY. BRIGHTER TOMORROW.</footer>
    </main>
  )
}
