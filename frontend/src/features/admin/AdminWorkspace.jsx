import { useEffect, useMemo, useState } from 'react'
import { Icon } from '../../lib/icons'
import { DataTable, LeafLogo, Metric, Notice, PageTitle, Panel, StatusBadge } from '../../components/ui'
import { leafGateway } from '../../services/leafGateway'

const PAGE_SIZE = 100

const adminNav = [
  ['overview', 'Overview'],
  ['exams', 'Exams'],
  ['timetable', 'Timetable'],
  ['rosters', 'Rosters'],
  ['live-exams', 'Live Exams'],
  ['makeups', 'Makeups'],
  ['results', 'Results'],
  ['system', 'System'],
]

export function AdminWorkspace({ state, dispatch, signOut, gateway = leafGateway }) {
  const section = state.staff.section === 'dashboard' ? 'overview' : state.staff.section
  const actor = state.session?.actor
  const adminName = actor?.display_name || state.session?.name || 'Administrator'

  return (
    <main className="staff-shell">
      <aside className="staff-sidebar admin-sidebar">
        <LeafLogo />
        <div className="admin-identity">
          <span>{initials(adminName)}</span>
          <div>
            <strong>{adminName}</strong>
            <small>Administrator</small>
          </div>
        </div>
        <div className="school-card">
          <span><Icon name="school" size={20} /></span>
          <div>
            <strong>{state.installation?.status?.tenant_name || 'Brightfield Academy'}</strong>
            <small>{state.installation?.status?.server_name || 'Leaf CBT Node'}</small>
          </div>
        </div>
        <nav aria-label="Admin navigation">
          {adminNav.map(([item, label]) => (
            <button key={item} className={section === item ? 'active' : ''} onClick={() => dispatch({ type: 'staff', patch: { section: item } })}>
              {label}
            </button>
          ))}
        </nav>
        <button className="sidebar-signout" onClick={signOut}>Sign out</button>
      </aside>
      <section className="staff-main">
        <header className="staff-topbar">
          <div>
            <span>Leaf</span>
            <strong>{adminNav.find(([item]) => item === section)?.[1] || 'Overview'}</strong>
          </div>
        </header>
        <div className="staff-content admin-content">
          {section === 'overview' && <AdminOverview adminName={adminName} />}
          {section === 'exams' && <ExamOperations gateway={gateway} />}
          {section === 'timetable' && <AdminTimetable gateway={gateway} />}
          {section === 'rosters' && <RosterPage gateway={gateway} />}
          {section === 'live-exams' && <LiveExamsPage />}
          {section === 'makeups' && <MakeupsPage gateway={gateway} />}
          {section === 'results' && <ResultsPage gateway={gateway} />}
          {section === 'system' && <SystemPage gateway={gateway} />}
        </div>
      </section>
    </main>
  )
}

function AdminOverview({ adminName }) {
  return (
    <>
      <PageTitle title={`Good morning, ${firstName(adminName)}`} subtitle="Exam operations that need administrator attention." />
      <div className="metric-grid">
        <Metric label="Exams Today" value="-" helper="Needs dashboard summary API" />
        <Metric label="Active Exams" value="-" helper="Needs exam list or aggregate API" />
        <Metric label="Candidates Writing" value="-" helper="Needs live attempt discovery API" />
        <Metric label="Pending Makeups" value="-" helper="Use Makeups with an exam ID" />
      </div>
      <Panel title="Needs Attention">
        <Notice tone="warning">The backend does not currently expose a dashboard aggregate route. Leaf will not scan every exam or candidate to invent these counts.</Notice>
      </Panel>
    </>
  )
}

function ExamOperations({ gateway }) {
  const [examId, setExamId] = useState('')
  const [exam, setExam] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  const [reasonAction, setReasonAction] = useState(null)

  const loadExam = async () => {
    if (!examId) return
    setError('')
    setBusy('load')
    try {
      setExam(await gateway.exams.getExam(examId))
    } catch (error) {
      setError(message(error))
    } finally {
      setBusy('')
    }
  }

  const run = async (name, operation) => {
    setError('')
    setBusy(name)
    try {
      setExam(await operation())
    } catch (error) {
      setError(message(error))
    } finally {
      setBusy('')
    }
  }

  return (
    <>
      <PageTitle title="Exams" subtitle="Lifecycle actions are driven by the backend state machine." />
      <Panel title="Open Exam">
        <ExamIdControl examId={examId} setExamId={setExamId} onLoad={loadExam} loading={busy === 'load'} />
        {error && <Notice tone="danger">{error}</Notice>}
      </Panel>
      {exam && (
        <Panel title={exam.title}>
          <div className="exam-summary-grid">
            <Metric label="Status" value={exam.status} helper={`Revision ${exam.revision_number}`} />
            <Metric label="Roster" value={exam.roster_status} helper={`${exam.roster_candidate_count} candidates`} />
            <Metric label="Questions" value={exam.question_count} helper={exam.question_selection_mode} />
            <Metric label="Duration" value={`${exam.duration_minutes}m`} helper="Backend contract" />
          </div>
          <div className="toolbar">
            <button className="button button--secondary" disabled={busy === 'submit'} onClick={() => run('submit', () => gateway.exams.submitExam(exam.id))}>Submit</button>
            <button className="button button--secondary" disabled={busy === 'return'} onClick={() => run('return', () => gateway.exams.returnExamToDraft(exam.id))}>Return to draft</button>
            <button className="button button--secondary" disabled={busy === 'seal'} onClick={() => run('seal', () => gateway.exams.sealExam(exam.id))}>Seal</button>
            <button className="button button--secondary" disabled={busy === 'revision'} onClick={() => run('revision', () => gateway.exams.createRevision(exam.id))}>Create revision</button>
            <button className="button button--primary" disabled={busy === 'activate'} onClick={() => run('activate', () => gateway.exams.activateExam(exam.id))}>Activate</button>
            <button className="button button--secondary" disabled={busy === 'close'} onClick={() => run('close', () => gateway.exams.closeExam(exam.id))}>Close</button>
            <button className="button button--secondary" onClick={() => setReasonAction('suspend')}>Suspend</button>
            <button className="button button--secondary" onClick={() => setReasonAction('resume')}>Resume</button>
            <button className="button button--secondary" onClick={() => setReasonAction('cancel')}>Cancel</button>
          </div>
        </Panel>
      )}
      {reasonAction && (
        <ReasonDialog
          title={`${label(reasonAction)} exam`}
          confirmLabel={label(reasonAction)}
          onCancel={() => setReasonAction(null)}
          onConfirm={(reason) => {
            const actions = {
              suspend: () => gateway.exams.suspendExam(exam.id, reason),
              resume: () => gateway.exams.resumeExam(exam.id, reason),
              cancel: () => gateway.exams.cancelExam(exam.id, reason),
            }
            setReasonAction(null)
            run(reasonAction, actions[reasonAction])
          }}
        />
      )}
    </>
  )
}

function AdminTimetable({ gateway }) {
  const [examIds, setExamIds] = useState('')
  const [impactExamId, setImpactExamId] = useState('')
  const [batch, setBatch] = useState(null)
  const [impacts, setImpacts] = useState([])
  const [error, setError] = useState('')

  const startBatch = async () => {
    setError('')
    try {
      setBatch(await gateway.timetable.startBatch(examIds.split(/\s|,/).map((item) => item.trim()).filter(Boolean)))
    } catch (error) {
      setError(message(error))
    }
  }

  const loadImpact = async () => {
    setError('')
    try {
      setImpacts(await gateway.timetable.getTimetableImpact(impactExamId))
    } catch (error) {
      setError(message(error))
    }
  }

  return (
    <>
      <PageTitle title="Timetable" subtitle="Batch activation preserves per-exam results." />
      <Panel title="Start Batch">
        <textarea className="plain-textarea" value={examIds} onChange={(event) => setExamIds(event.target.value)} placeholder="Paste exam UUIDs separated by comma or space" />
        <button className="button button--primary" onClick={startBatch}>Activate selected</button>
        {batch && <DataTable columns={['Exam', 'Result', 'Notes']} rows={batch.results.map((row) => [row.exam_id, row.started ? 'Activated' : 'Failed', row.error || `${row.impacts.length} delayed exams`])} />}
      </Panel>
      <Panel title="Timetable Impact">
        <ExamIdControl examId={impactExamId} setExamId={setImpactExamId} onLoad={loadImpact} />
        {impacts.length > 0 && <DataTable columns={['Exam', 'Original', 'Proposed Start', 'Proposed End']} rows={impacts.map((row) => [row.title, formatDate(row.original_start_at), formatDate(row.proposed_start_at), formatDate(row.proposed_end_at)])} />}
        {error && <Notice tone="danger">{error}</Notice>}
      </Panel>
    </>
  )
}

function RosterPage({ gateway }) {
  const [examId, setExamId] = useState('')
  const [loadedExamId, setLoadedExamId] = useState('')
  const [status, setStatus] = useState('')
  const [classId, setClassId] = useState('')
  const [offset, setOffset] = useState(0)
  const [roster, setRoster] = useState(null)
  const [selectedCandidateId, setSelectedCandidateId] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!loadedExamId) return undefined
    const controller = new AbortController()
    gateway.candidates
      .listExamRoster(loadedExamId, { status, class_id: classId, offset, limit: PAGE_SIZE }, { signal: controller.signal })
      .then(setRoster)
      .catch((error) => {
        if (error.name !== 'AbortError') setError(message(error))
      })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [gateway, loadedExamId, status, classId, offset])

  const visibleCandidates = useMemo(() => {
    const rows = roster?.candidates || []
    const value = search.trim().toLowerCase()
    if (!value) return rows
    return rows.filter((candidate) =>
      `${candidate.display_name} ${candidate.admission_number}`.toLowerCase().includes(value),
    )
  }, [roster, search])

  const updateCandidate = (candidate) => {
    setRoster((current) => ({
      ...current,
      candidates: current.candidates.map((item) => (item.id === candidate.id ? candidate : item)),
    }))
  }

  return (
    <>
      <PageTitle title="Rosters" subtitle="Open one examination register and work inside it." />
      <Panel title="Select Exam">
        <ExamIdControl
          examId={examId}
          setExamId={setExamId}
          onLoad={() => {
            setLoading(true)
            setError('')
            setOffset(0)
            setLoadedExamId(examId)
          }}
          loading={loading}
        />
        <Notice tone="warning">Exam search/listing is not currently exposed by the backend, so this page opens a known exam UUID directly.</Notice>
      </Panel>
      {loadedExamId && (
        <section className="register-shell">
          <header className="register-header">
            <div>
              <h2>{roster?.exam_title || 'Digital Candidate Register'}</h2>
              <p>{roster ? `${roster.roster_candidate_count} candidates - ${roster.roster_status}` : 'Loading roster'}</p>
            </div>
            <div className="register-controls">
              <label>
                <span>Search loaded page</span>
                <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Name or admission no." />
              </label>
              <label>
                <span>Status</span>
                <select value={status} onChange={(event) => { setLoading(true); setError(''); setStatus(event.target.value); setOffset(0) }}>
                  <option value="">All</option>
                  <option value="eligible">Eligible</option>
                  <option value="blocked">Blocked</option>
                  <option value="withdrawn">Withdrawn</option>
                </select>
              </label>
              <label>
                <span>Class ID</span>
                <input value={classId} onChange={(event) => { setLoading(true); setError(''); setClassId(event.target.value); setOffset(0) }} placeholder="Optional UUID" />
              </label>
            </div>
          </header>
          {toast && <Notice tone="success">{toast}</Notice>}
          {error && <Notice tone="danger">{error}</Notice>}
          <div className="register-table-wrap">
            <table className="register-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Student</th>
                  <th>Admission No.</th>
                  <th>Class</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {loading && Array.from({ length: 8 }, (_, index) => <SkeletonRosterRow key={index} />)}
                {!loading && visibleCandidates.map((candidate, index) => (
                  <tr key={candidate.id} className={selectedCandidateId === candidate.id ? 'selected' : ''} onClick={() => setSelectedCandidateId(candidate.id)}>
                    <td>{String(offset + index + 1).padStart(3, '0')}</td>
                    <td><strong>{candidate.display_name}</strong></td>
                    <td><code>{candidate.admission_number}</code></td>
                    <td>{shortId(candidate.class_id)}</td>
                    <td><StatusBadge tone={statusTone(candidate.status)}>{candidate.status}</StatusBadge></td>
                    <td><Icon name="menu" size={18} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <footer className="register-pagination">
            <span>{roster ? `${offset + 1}-${Math.min(offset + PAGE_SIZE, roster.total)} of ${roster.total}` : 'No roster loaded'}</span>
            <div>
              <button className="button button--secondary" disabled={offset === 0 || loading} onClick={() => { setLoading(true); setError(''); setOffset(Math.max(0, offset - PAGE_SIZE)) }}>Previous</button>
              <button className="button button--secondary" disabled={!roster || offset + PAGE_SIZE >= roster.total || loading} onClick={() => { setLoading(true); setError(''); setOffset(offset + PAGE_SIZE) }}>Next</button>
            </div>
          </footer>
          <Notice>Search is limited to the currently loaded page because the roster endpoint does not expose name/admission-number search.</Notice>
        </section>
      )}
      {selectedCandidateId && (
        <CandidateDrawer
          candidateId={selectedCandidateId}
          gateway={gateway}
          onClose={() => setSelectedCandidateId('')}
          onCandidateChanged={updateCandidate}
          onToast={setToast}
        />
      )}
    </>
  )
}

function CandidateDrawer({ candidateId, gateway, onClose, onCandidateChanged, onToast }) {
  const [candidate, setCandidate] = useState(null)
  const [lateStarts, setLateStarts] = useState([])
  const [makeups, setMakeups] = useState([])
  const [error, setError] = useState('')
  const [dialog, setDialog] = useState(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      gateway.candidates.getCandidate(candidateId),
      gateway.candidates.listLateStartAuthorizations(candidateId),
      gateway.makeups.listMakeupAuthorizations(candidateId),
    ])
      .then(([candidate, lateStarts, makeups]) => {
        if (cancelled) return
        setCandidate(candidate)
        setLateStarts(lateStarts)
        setMakeups(makeups)
      })
      .catch((error) => {
        if (!cancelled) setError(message(error))
      })
    return () => {
      cancelled = true
    }
  }, [candidateId, gateway])

  const run = async (operation, successMessage) => {
    setError('')
    try {
      const result = await operation()
      if (result?.display_name) {
        setCandidate(result)
        onCandidateChanged(result)
      }
      const [lateStartRows, makeupRows] = await Promise.all([
        gateway.candidates.listLateStartAuthorizations(candidateId),
        gateway.makeups.listMakeupAuthorizations(candidateId),
      ])
      setLateStarts(lateStartRows)
      setMakeups(makeupRows)
      onToast(successMessage)
    } catch (error) {
      setError(message(error))
    }
  }

  return (
    <aside className="candidate-drawer" aria-label="Candidate details">
      <header>
        <button className="icon-button" onClick={onClose} aria-label="Close candidate details"><Icon name="close" size={20} /></button>
        <div>
          <h2>{candidate?.display_name || 'Loading candidate'}</h2>
          <p>{candidate?.admission_number || candidateId}</p>
        </div>
      </header>
      {error && <Notice tone="danger">{error}</Notice>}
      {candidate && (
        <>
          <dl className="status-rows">
            <div><dt>Candidate Status</dt><dd><StatusBadge tone={statusTone(candidate.status)}>{candidate.status}</StatusBadge></dd></div>
            <div><dt>Class</dt><dd>{shortId(candidate.class_id)}</dd></div>
            <div><dt>Exam</dt><dd>{shortId(candidate.exam_id)}</dd></div>
          </dl>
          <div className="drawer-actions">
            {candidate.status === 'blocked' ? (
              <button className="button button--secondary" onClick={() => run(() => gateway.candidates.unblockCandidate(candidate.id), 'Candidate unblocked.')}>Unblock Candidate</button>
            ) : (
              <button className="button button--secondary" onClick={() => setDialog({ type: 'block', title: `Block ${candidate.display_name}?`, confirm: 'Block Candidate' })}>Block Candidate</button>
            )}
            <button className="button button--secondary" onClick={() => setDialog({ type: 'late-start', title: 'Grant Late Start', confirm: 'Grant Late Start', showExpiry: true })}>Grant Late Start</button>
            <button className="button button--secondary" onClick={() => setDialog({ type: 'makeup', title: 'Approve Makeup', confirm: 'Approve Makeup' })}>Approve Makeup</button>
          </div>
          <HistoryList title="Late Start History" rows={lateStarts} revoke={(row) => setDialog({ type: 'revoke-late-start', title: 'Revoke Late Start', confirm: 'Revoke', id: row.id })} />
          <HistoryList title="Makeup History" rows={makeups} revoke={(row) => setDialog({ type: 'revoke-makeup', title: 'Revoke Makeup', confirm: 'Revoke', id: row.id })} />
        </>
      )}
      {dialog && (
        <ReasonDialog
          title={dialog.title}
          confirmLabel={dialog.confirm}
          showExpiry={dialog.showExpiry}
          onCancel={() => setDialog(null)}
          onConfirm={(reason, expiresAt) => {
            const actions = {
              block: () => gateway.candidates.blockCandidate(candidate.id, reason),
              'late-start': () => gateway.candidates.grantLateStart(candidate.id, { reason, expires_at: expiresAt || null }),
              makeup: () => gateway.makeups.approveMakeup(candidate.id, reason),
              'revoke-late-start': () => gateway.candidates.revokeLateStart(dialog.id, reason),
              'revoke-makeup': () => gateway.makeups.revokeMakeup(dialog.id, reason),
            }
            const labels = {
              block: 'Candidate blocked.',
              'late-start': 'Late start granted.',
              makeup: 'Makeup approved.',
              'revoke-late-start': 'Late start revoked.',
              'revoke-makeup': 'Makeup approval revoked.',
            }
            setDialog(null)
            run(actions[dialog.type], labels[dialog.type])
          }}
        />
      )}
    </aside>
  )
}

function MakeupsPage({ gateway }) {
  const [examId, setExamId] = useState('')
  const [loadedExamId, setLoadedExamId] = useState('')
  const [offset, setOffset] = useState(0)
  const [missed, setMissed] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!loadedExamId) return
    gateway.makeups
      .listMissedCandidates(loadedExamId, { offset, limit: PAGE_SIZE })
      .then(setMissed)
      .catch((error) => setError(message(error)))
  }, [gateway, loadedExamId, offset])

  return (
    <>
      <PageTitle title="Makeups" subtitle="Missed candidates remain a register, not cards." />
      <Panel title="Open Missed Candidate Register">
        <ExamIdControl examId={examId} setExamId={setExamId} onLoad={() => { setOffset(0); setLoadedExamId(examId) }} />
        {error && <Notice tone="danger">{error}</Notice>}
      </Panel>
      {missed && (
        <section className="register-shell">
          <header className="register-header">
            <div>
              <h2>Missed Candidates - {missed.exam_title}</h2>
              <p>{missed.total} candidates</p>
            </div>
          </header>
          <DataTable
            columns={['Student', 'Admission No.', 'Class', 'Makeup']}
            rows={missed.candidates.map((row) => [
              row.candidate.display_name,
              row.candidate.admission_number,
              shortId(row.candidate.class_id),
              row.makeup_authorization ? 'Approved' : 'Not approved',
            ])}
          />
          <footer className="register-pagination">
            <span>{offset + 1}-{Math.min(offset + PAGE_SIZE, missed.total)} of {missed.total}</span>
            <div>
              <button className="button button--secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Previous</button>
              <button className="button button--secondary" disabled={offset + PAGE_SIZE >= missed.total} onClick={() => setOffset(offset + PAGE_SIZE)}>Next</button>
            </div>
          </footer>
        </section>
      )}
    </>
  )
}

function ResultsPage({ gateway }) {
  const [examId, setExamId] = useState('')
  const [results, setResults] = useState(null)
  const [error, setError] = useState('')

  const load = async () => {
    setError('')
    try {
      setResults(await gateway.results.listExamResults(examId, { offset: 0, limit: PAGE_SIZE }))
    } catch (error) {
      setError(message(error))
    }
  }

  return (
    <>
      <PageTitle title="Results" subtitle="Read-only server-calculated scores." />
      <Panel title="Open Exam Results">
        <ExamIdControl examId={examId} setExamId={setExamId} onLoad={load} />
        {error && <Notice tone="danger">{error}</Notice>}
      </Panel>
      {results && <DataTable columns={['Candidate', 'Raw', 'Percentage', 'Component', 'Sync']} rows={results.results.map((row) => [shortId(row.candidate_id), `${row.raw_score}/${row.raw_max_score}`, `${row.percentage}%`, `${row.component_score}/${row.component_maximum_score}`, row.sync_status])} />}
    </>
  )
}

function SystemPage({ gateway }) {
  const [status, setStatus] = useState(null)
  const [error, setError] = useState('')

  const load = async () => {
    setError('')
    try {
      setStatus(await gateway.sync.getSyncStatus())
    } catch (error) {
      setError(message(error))
    }
  }

  return (
    <>
      <PageTitle title="System" subtitle="Connectivity and sync controls live here." />
      <Panel title="Synchronization">
        <button className="button button--secondary" onClick={load}>Refresh status</button>
        <button className="button button--primary" onClick={() => gateway.sync.reconcileSync().then(setStatus).catch((error) => setError(message(error)))}>Reconcile now</button>
        {status && <pre className="json-panel">{JSON.stringify(status, null, 2)}</pre>}
        {error && <Notice tone="danger">{error}</Notice>}
      </Panel>
    </>
  )
}

function LiveExamsPage() {
  return (
    <>
      <PageTitle title="Live Exams" subtitle="Operator state changes require a real attempt discovery list." />
      <Panel title="Backend contract needed">
        <Notice tone="warning">The backend exposes interrupt, resume, and terminate mutations for known attempt IDs, but no route currently lists live attempts by exam. Production UI should stay unavailable until that read contract exists.</Notice>
      </Panel>
    </>
  )
}

function ExamIdControl({ examId, setExamId, onLoad, loading }) {
  return (
    <div className="exam-id-control">
      <input aria-label="Exam ID" value={examId} onChange={(event) => setExamId(event.target.value)} placeholder="Exam UUID" />
      <button className="button button--primary" disabled={!examId || loading} onClick={onLoad}>Open</button>
    </div>
  )
}

function ReasonDialog({ title, confirmLabel, showExpiry = false, onCancel, onConfirm }) {
  const [reason, setReason] = useState('')
  const [expiresAt, setExpiresAt] = useState('')

  return (
    <div className="dialog-backdrop">
      <section className="confirm-dialog" role="dialog" aria-label={title}>
        <h2>{title}</h2>
        <label className="field-stack">
          Reason
          <textarea value={reason} onChange={(event) => setReason(event.target.value)} />
        </label>
        {showExpiry && (
          <label className="field-stack">
            Expires at
            <input type="datetime-local" value={expiresAt} onChange={(event) => setExpiresAt(event.target.value)} />
          </label>
        )}
        <div className="toolbar">
          <button className="button button--secondary" onClick={onCancel}>Cancel</button>
          <button className="button button--primary" disabled={!reason.trim()} onClick={() => onConfirm(reason.trim(), expiresAt ? new Date(expiresAt).toISOString() : null)}>{confirmLabel}</button>
        </div>
      </section>
    </div>
  )
}

function HistoryList({ title, rows, revoke }) {
  return (
    <section className="history-list">
      <h3>{title}</h3>
      {rows.length === 0 && <p>No authorization history.</p>}
      {rows.map((row) => (
        <article key={row.id}>
          <strong>{row.revoked_at ? 'Revoked' : 'Granted'} {formatDate(row.granted_at || row.approved_at)}</strong>
          <span>{row.expires_at ? `Expires ${formatDate(row.expires_at)}` : 'No expiry'}</span>
          <p>{row.revocation_reason || row.reason}</p>
          {!row.revoked_at && <button className="text-button" onClick={() => revoke(row)}>Revoke</button>}
        </article>
      ))}
    </section>
  )
}

function SkeletonRosterRow() {
  return (
    <tr className="skeleton-row">
      <td></td>
      <td><span></span></td>
      <td><span></span></td>
      <td><span></span></td>
      <td><span></span></td>
      <td></td>
    </tr>
  )
}

function initials(name) {
  return name.split(' ').map((part) => part[0]).join('').slice(0, 2).toUpperCase()
}

function firstName(name) {
  return name.split(' ').filter(Boolean)[0] || 'Administrator'
}

function shortId(value) {
  return value ? String(value).slice(0, 8) : '-'
}

function statusTone(status) {
  if (status === 'eligible') return 'success'
  if (status === 'blocked') return 'danger'
  return 'warning'
}

function label(value) {
  return value.split('-').map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(' ')
}

function message(error) {
  return error.userMessage || error.message || 'Leaf could not complete that request.'
}

function formatDate(value) {
  if (!value) return '-'
  return new Intl.DateTimeFormat('en-NG', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}
