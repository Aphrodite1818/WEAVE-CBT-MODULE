import { useEffect, useMemo, useState } from 'react'
import { RiRefreshLine } from '@remixicon/react'
import { Notice } from '../../../shared/ui'
import '../admin-roster-actions.css'

const READ_ONLY_EXAM_STATES = new Set(['closing', 'cancelling', 'closed', 'cancelled'])

export function RosterCandidateActionButton({ candidate, exam, gateway, onChanged }) {
  const [open, setOpen] = useState(false)
  const [authorizations, setAuthorizations] = useState([])
  const [loadingAuthorizations, setLoadingAuthorizations] = useState(false)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [blockReason, setBlockReason] = useState('')
  const [lateStartReason, setLateStartReason] = useState('')
  const [lateStartExpiry, setLateStartExpiry] = useState('')
  const [revocationReason, setRevocationReason] = useState('')

  const readOnlyExam = READ_ONLY_EXAM_STATES.has(exam.status)
  const canChangeEligibility = !readOnlyExam && candidate.status !== 'withdrawn'
  const canGrantLateStart = exam.status === 'active' && candidate.status === 'eligible'
  const hasManagementAction = canChangeEligibility || canGrantLateStart

  const activeAuthorization = useMemo(() => {
    const now = Date.now()
    return [...authorizations]
      .sort((a, b) => new Date(b.granted_at).getTime() - new Date(a.granted_at).getTime())
      .find((authorization) => {
        if (authorization.revoked_at || authorization.consumed_at) return false
        if (!authorization.expires_at) return true
        return new Date(authorization.expires_at).getTime() > now
      }) || null
  }, [authorizations])

  const sortedAuthorizations = useMemo(
    () => [...authorizations].sort((a, b) => new Date(b.granted_at).getTime() - new Date(a.granted_at).getTime()),
    [authorizations],
  )

  const loadAuthorizations = async () => {
    setLoadingAuthorizations(true)
    setError('')
    try {
      const response = await gateway.candidates.listLateStartAuthorizations(candidate.id)
      setAuthorizations(Array.isArray(response) ? response : [])
    } catch (requestError) {
      setError(requestError.userMessage || 'Weave could not load late-start authorization details.')
    } finally {
      setLoadingAuthorizations(false)
    }
  }

  useEffect(() => {
    if (!open) return undefined
    void loadAuthorizations()
    const closeOnEscape = (event) => {
      if (event.key === 'Escape' && !busy) setOpen(false)
    }
    document.addEventListener('keydown', closeOnEscape)
    return () => document.removeEventListener('keydown', closeOnEscape)
  }, [open, candidate.id])

  const runCandidateMutation = async (action, request) => {
    setBusy(action)
    setError('')
    try {
      await request()
      setBlockReason('')
      await onChanged?.()
      setOpen(false)
    } catch (requestError) {
      setError(requestError.userMessage || 'Weave could not update this candidate.')
    } finally {
      setBusy('')
    }
  }

  const blockCandidate = () => {
    const reason = blockReason.trim()
    if (!reason) {
      setError('Enter a reason before blocking this candidate.')
      return
    }
    void runCandidateMutation('block', () => gateway.candidates.blockCandidate(candidate.id, reason))
  }

  const unblockCandidate = () => {
    void runCandidateMutation('unblock', () => gateway.candidates.unblockCandidate(candidate.id))
  }

  const grantLateStart = async () => {
    const reason = lateStartReason.trim()
    if (!reason) {
      setError('Enter a reason before granting late-start access.')
      return
    }

    let expiresAt = null
    if (lateStartExpiry) {
      const parsed = new Date(lateStartExpiry)
      if (Number.isNaN(parsed.getTime())) {
        setError('Enter a valid late-start expiry time.')
        return
      }
      expiresAt = parsed.toISOString()
    }

    setBusy('grant-late-start')
    setError('')
    try {
      await gateway.candidates.grantLateStart(candidate.id, {
        reason,
        expires_at: expiresAt,
      })
      setLateStartReason('')
      setLateStartExpiry('')
      await loadAuthorizations()
    } catch (requestError) {
      setError(requestError.userMessage || 'Weave could not grant late-start access.')
    } finally {
      setBusy('')
    }
  }

  const revokeLateStart = async () => {
    if (!activeAuthorization) return
    const reason = revocationReason.trim()
    if (!reason) {
      setError('Enter a reason before revoking late-start access.')
      return
    }

    setBusy('revoke-late-start')
    setError('')
    try {
      await gateway.candidates.revokeLateStart(activeAuthorization.id, reason)
      setRevocationReason('')
      await loadAuthorizations()
    } catch (requestError) {
      setError(requestError.userMessage || 'Weave could not revoke late-start access.')
    } finally {
      setBusy('')
    }
  }

  return (
    <>
      <button
        className="admin-roster-manage"
        type="button"
        onClick={() => { setError(''); setOpen(true) }}
      >
        {hasManagementAction ? 'Manage' : 'View'}
      </button>

      {open && (
        <div className="admin-roster-action-modal" role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget && !busy) setOpen(false)
        }}>
          <section className="admin-roster-action-sheet" role="dialog" aria-modal="true" aria-labelledby={`candidate-actions-${candidate.id}`}>
            <header className="admin-roster-action-sheet__header">
              <div>
                <span>Candidate access</span>
                <h2 id={`candidate-actions-${candidate.id}`}>{candidate.display_name}</h2>
                <p>{candidate.admission_number}{candidate.class_name ? ` · ${candidate.class_name}` : ''}</p>
              </div>
              <button type="button" aria-label="Close candidate actions" disabled={Boolean(busy)} onClick={() => setOpen(false)}>×</button>
            </header>

            {error && <Notice tone="danger">{error}</Notice>}

            <div className="admin-roster-action-section">
              <div className="admin-roster-action-section__heading">
                <div>
                  <strong>Exam eligibility</strong>
                  <span>Control whether this candidate may participate in this sitting.</span>
                </div>
                <CandidateAccessState status={candidate.status} />
              </div>

              {candidate.status === 'eligible' && canChangeEligibility && (
                <div className="admin-roster-action-form">
                  <label>
                    <span>Reason for blocking</span>
                    <textarea value={blockReason} onChange={(event) => setBlockReason(event.target.value)} placeholder="State why this candidate should not start the examination." maxLength={500} />
                  </label>
                  <div className="admin-roster-action-form__footer">
                    <small>This affects this examination only. It does not change the student’s Weave enrollment.</small>
                    <button className="admin-roster-action-danger" type="button" disabled={Boolean(busy)} onClick={blockCandidate}>
                      {busy === 'block' ? 'Blocking…' : 'Block candidate'}
                    </button>
                  </div>
                </div>
              )}

              {candidate.status === 'blocked' && canChangeEligibility && (
                <div className="admin-roster-action-callout">
                  <div><span>Block reason</span><strong>{candidate.status_reason || 'No reason recorded'}</strong></div>
                  <button className="admin-roster-action-primary" type="button" disabled={Boolean(busy)} onClick={unblockCandidate}>
                    {busy === 'unblock' ? 'Unblocking…' : 'Unblock candidate'}
                  </button>
                </div>
              )}

              {candidate.status === 'withdrawn' && (
                <p className="admin-roster-action-note">This candidate is no longer academically eligible. Restore the enrollment in Weave and let roster reconciliation handle the change.</p>
              )}

              {readOnlyExam && candidate.status !== 'withdrawn' && (
                <p className="admin-roster-action-note">This examination is read-only, so candidate eligibility can no longer be changed.</p>
              )}
            </div>

            <div className="admin-roster-action-section">
              <div className="admin-roster-action-section__heading">
                <div>
                  <strong>Late-start authorization</strong>
                  <span>Allow an eligible candidate to start after the normal entry window.</span>
                </div>
              </div>

              {loadingAuthorizations && <div className="admin-roster-action-loading">Loading authorization status…</div>}

              {!loadingAuthorizations && activeAuthorization && (
                <div className="admin-roster-late-start-active">
                  <div className="admin-roster-late-start-active__header">
                    <span>Active authorization</span>
                    <strong>{activeAuthorization.expires_at ? `Expires ${formatActionDate(activeAuthorization.expires_at)}` : 'No expiry set'}</strong>
                  </div>
                  <p>{activeAuthorization.reason}</p>
                  {!readOnlyExam && (
                    <div className="admin-roster-action-form admin-roster-action-form--compact">
                      <label>
                        <span>Reason for revocation</span>
                        <textarea value={revocationReason} onChange={(event) => setRevocationReason(event.target.value)} placeholder="Why should this authorization be revoked?" />
                      </label>
                      <div className="admin-roster-action-form__footer">
                        <span />
                        <button className="admin-roster-action-danger admin-roster-action-danger--secondary" type="button" disabled={Boolean(busy)} onClick={revokeLateStart}>
                          {busy === 'revoke-late-start' ? 'Revoking…' : 'Revoke authorization'}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {!loadingAuthorizations && !activeAuthorization && canGrantLateStart && (
                <div className="admin-roster-action-form">
                  <label>
                    <span>Authorization reason</span>
                    <textarea value={lateStartReason} onChange={(event) => setLateStartReason(event.target.value)} placeholder="State why this candidate is being allowed to start late." />
                  </label>
                  <label>
                    <span>Expires at <small>(optional)</small></span>
                    <input type="datetime-local" value={lateStartExpiry} onChange={(event) => setLateStartExpiry(event.target.value)} />
                  </label>
                  <div className="admin-roster-action-form__footer">
                    <small>Late-start access is available only while this examination is active.</small>
                    <button className="admin-roster-action-primary" type="button" disabled={Boolean(busy)} onClick={grantLateStart}>
                      {busy === 'grant-late-start' ? 'Granting…' : 'Grant late start'}
                    </button>
                  </div>
                </div>
              )}

              {!loadingAuthorizations && !activeAuthorization && !canGrantLateStart && (
                <p className="admin-roster-action-note">
                  {candidate.status !== 'eligible'
                    ? 'Late-start access is available only to eligible candidates.'
                    : exam.status !== 'active'
                      ? 'Late-start access becomes available when the examination is active.'
                      : 'Late-start access is not available for this candidate.'}
                </p>
              )}

              {!loadingAuthorizations && sortedAuthorizations.length > 0 && (
                <div className="admin-roster-authorization-history">
                  <span>Recent authorization history</span>
                  {sortedAuthorizations.slice(0, 3).map((authorization) => (
                    <div key={authorization.id}>
                      <div>
                        <strong>{lateStartStatus(authorization)}</strong>
                        <span>{formatActionDate(authorization.granted_at)}</span>
                      </div>
                      <p>{authorization.reason}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>
        </div>
      )}
    </>
  )
}

export function RosterRecoveryNotice({ exam, onRefresh, onOpenOperations }) {
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState('')

  if (!['stale', 'failed'].includes(exam.rosterStatus)) return null

  const refresh = async () => {
    setChecking(true)
    setError('')
    try {
      await onRefresh?.()
    } catch (requestError) {
      setError(requestError.userMessage || 'Weave could not refresh the roster status.')
    } finally {
      setChecking(false)
    }
  }

  const failed = exam.rosterStatus === 'failed'

  return (
    <div className={`admin-roster-recovery admin-roster-recovery--${failed ? 'failed' : 'stale'}`} role={failed ? 'alert' : 'status'}>
      <div className="admin-roster-recovery__copy">
        <strong>{failed ? 'Roster reconciliation needs attention' : 'Roster refresh in progress'}</strong>
        <p>
          {failed
            ? (exam.rosterError || 'The last roster preparation or reconciliation attempt failed. Failed rosters are left for administrator review rather than retried indefinitely.')
            : 'Enrollment changed in Weave. The maintenance worker will reconcile this sealed roster automatically before activation.'}
        </p>
        {error && <small>{error}</small>}
      </div>
      <div className="admin-roster-recovery__actions">
        <button type="button" disabled={checking} onClick={refresh}><RiRefreshLine size={16} /> {checking ? 'Checking…' : 'Refresh status'}</button>
        {failed && <button type="button" className="admin-roster-recovery__secondary" onClick={onOpenOperations}>Open Exam Operations</button>}
      </div>
    </div>
  )
}

function CandidateAccessState({ status }) {
  const normalized = String(status || '').toLowerCase()
  return <span className={`admin-candidate-state admin-candidate-state--${normalized}`}>{titleCase(normalized)}</span>
}

function lateStartStatus(authorization) {
  if (authorization.consumed_at) return 'Consumed'
  if (authorization.revoked_at) return 'Revoked'
  if (authorization.expires_at && new Date(authorization.expires_at).getTime() <= Date.now()) return 'Expired'
  return 'Active'
}

function formatActionDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat(undefined, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function titleCase(value) {
  return String(value || '').replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}
