import { useEffect, useMemo, useState } from 'react'
import { RiArrowLeftLine, RiArrowRightLine, RiSearchLine } from '@remixicon/react'
import { buildAcademicLevels, listSubjectsForLevel } from '../../../shared/academics/authoringScope'
import { Icon } from '../../../shared/icons/Icon'
import { Notice, SelectControl } from '../../../shared/ui'
import { RosterCandidateActionButton, RosterRecoveryNotice } from '../components/RosterCandidateActions'
import '../admin-rosters.css'

const OVERVIEW_PAGE_SIZE = 12
const ROSTER_PAGE_SIZE = 50
const TRANSITIONAL_ROSTER_STATES = new Set(['pending', 'building', 'stale'])
const ROSTER_EXAM_STATES = new Set(['sealed', 'active', 'suspended', 'closing', 'cancelling', 'closed', 'cancelled'])

export function AdminRostersPage({ adminData, onNavigate }) {
  const [query, setQuery] = useState('')
  const [levelId, setLevelId] = useState('all')
  const [subjectId, setSubjectId] = useState('all')
  const [requestedPage, setPage] = useState(1)

  const levels = useMemo(() => buildAcademicLevels(adminData.subjects), [adminData.subjects])
  const levelSubjects = useMemo(
    () => levelId === 'all' ? [] : listSubjectsForLevel(adminData.subjects, levelId),
    [adminData.subjects, levelId],
  )

  const rosterExams = useMemo(
    () => adminData.exams.filter((exam) => ROSTER_EXAM_STATES.has(exam.status) && exam.rosterStatus !== 'not_prepared'),
    [adminData.exams],
  )

  const refreshExams = adminData.refreshExams
  useEffect(() => {
    if (!rosterExams.some((exam) => TRANSITIONAL_ROSTER_STATES.has(exam.rosterStatus))) return undefined
    const timer = window.setInterval(() => {
      void refreshExams({ silent: true })
    }, 4000)
    return () => window.clearInterval(timer)
  }, [refreshExams, rosterExams])

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return rosterExams.filter((exam) => {
      if (levelId !== 'all' && exam.academicLevelId !== levelId) return false
      if (subjectId !== 'all' && exam.curriculumSubjectId !== subjectId) return false
      if (!needle) return true
      return `${exam.title} ${exam.academicLevelName} ${exam.subjectName} ${exam.assessmentName}`.toLowerCase().includes(needle)
    })
  }, [levelId, query, rosterExams, subjectId])

  const pageCount = Math.max(1, Math.ceil(filtered.length / OVERVIEW_PAGE_SIZE))
  const page = Math.min(requestedPage, pageCount)
  const visible = filtered.slice((page - 1) * OVERVIEW_PAGE_SIZE, page * OVERVIEW_PAGE_SIZE)

  const levelOptions = [
    { value: 'all', label: 'All levels' },
    ...levels.map((level) => ({ value: level.id, label: level.name })),
  ]
  const subjectOptions = [
    { value: 'all', label: 'All subjects' },
    ...levelSubjects.map((subject) => ({ value: subject.id, label: subject.name, description: subject.code || undefined })),
  ]

  const changeLevel = (nextLevelId) => {
    setLevelId(nextLevelId)
    setSubjectId('all')
    setPage(1)
  }

  return (
    <div className="teacher-reference-page admin-rosters-page">
      <div className="teacher-page-heading admin-rosters-heading">
        <div>
          <div className="teacher-page-title-line">
            <span className="teacher-page-title-icon"><Icon name="roster" size={27} /></span>
            <h1>Roster</h1>
          </div>
          <p>Review examination candidate rosters prepared from the latest synchronized enrollment data.</p>
        </div>
      </div>

      {adminData.error && <Notice tone="danger">{adminData.error}</Notice>}
      {adminData.warning && <Notice tone="warning">{adminData.warning}</Notice>}

      <div className="admin-roster-filters">
        <label className="teacher-search-control teacher-search-control--grow">
          <RiSearchLine size={18} aria-hidden="true" />
          <input
            aria-label="Search rosters"
            type="search"
            value={query}
            onChange={(event) => { setQuery(event.target.value); setPage(1) }}
            placeholder="Search by exam, level, subject, or assessment..."
          />
        </label>
        <SelectControl label="Roster level filter" value={levelId} options={levelOptions} onChange={changeLevel} />
        <SelectControl
          label="Roster subject filter"
          value={subjectId}
          options={subjectOptions}
          onChange={(value) => { setSubjectId(value); setPage(1) }}
          disabled={levelId === 'all'}
        />
      </div>

      <section className="admin-roster-grid" aria-label="Examination rosters" aria-busy={adminData.loading}>
        {visible.map((exam) => (
          <RosterCard key={exam.id} exam={exam} onOpen={() => onNavigate('roster-detail', { selectedExamId: exam.id })} />
        ))}

        {!adminData.loading && visible.length === 0 && (
          <div className="admin-roster-empty">
            <span><Icon name="roster" size={27} /></span>
            <div>
              <strong>{rosterExams.length ? 'No rosters match these filters' : 'No prepared rosters yet'}</strong>
              <p>{rosterExams.length ? 'Adjust the level, subject, or search filters.' : 'Rosters appear here automatically after an examination is sealed.'}</p>
            </div>
          </div>
        )}
        {adminData.loading && <div className="admin-roster-empty"><div><strong>Loading examination rosters…</strong></div></div>}

        <div className="admin-roster-pagination">
          <span>{filtered.length === 0 ? '0 rosters' : `Showing ${(page - 1) * OVERVIEW_PAGE_SIZE + 1}–${Math.min(page * OVERVIEW_PAGE_SIZE, filtered.length)} of ${filtered.length} rosters`}</span>
          <div>
            <button type="button" aria-label="Previous roster page" disabled={page === 1} onClick={() => setPage(page - 1)}>‹</button>
            <span>{page} / {pageCount}</span>
            <button type="button" aria-label="Next roster page" disabled={page === pageCount} onClick={() => setPage(page + 1)}>›</button>
          </div>
        </div>
      </section>
    </div>
  )
}

export function AdminRosterDetailPage({ state, adminData, gateway, onNavigate }) {
  const exam = adminData.exams.find((item) => item.id === state.staff.selectedExamId)
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('eligible')
  const [classId, setClassId] = useState('all')
  const [requestedPage, setPage] = useState(1)
  const [payload, setPayload] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [refreshToken, setRefreshToken] = useState(0)

  const pageCount = Math.max(1, Math.ceil((payload?.total || 0) / ROSTER_PAGE_SIZE))
  const page = Math.min(requestedPage, pageCount)

  useEffect(() => {
    if (!exam) return undefined
    let cancelled = false
    const timer = window.setTimeout(async () => {
      setLoading(true)
      setError('')
      try {
        const params = {
          offset: (page - 1) * ROSTER_PAGE_SIZE,
          limit: ROSTER_PAGE_SIZE,
        }
        if (status !== 'all') params.status = status
        if (classId !== 'all') params.class_id = classId
        if (query.trim()) params.search = query.trim()
        const response = await gateway.candidates.listExamRoster(exam.id, params)
        if (!cancelled) setPayload(response)
      } catch (requestError) {
        if (!cancelled) setError(requestError.userMessage || 'Weave could not load this examination roster.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }, query.trim() ? 220 : 0)

    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [classId, exam?.id, gateway, page, query, refreshToken, status])

  const refreshExams = adminData.refreshExams
  useEffect(() => {
    if (!exam || !TRANSITIONAL_ROSTER_STATES.has(exam.rosterStatus)) return undefined
    const timer = window.setInterval(async () => {
      await refreshExams({ silent: true })
      setRefreshToken((value) => value + 1)
    }, 4000)
    return () => window.clearInterval(timer)
  }, [exam?.id, exam?.rosterStatus, refreshExams])

  if (!exam) {
    return (
      <div className="teacher-reference-page admin-roster-detail">
        <button className="admin-roster-back" type="button" onClick={() => onNavigate('roster')}><RiArrowLeftLine size={17} /> Back to roster</button>
        <Notice tone="warning">The selected examination is no longer available.</Notice>
      </div>
    )
  }

  const classOptions = [
    { value: 'all', label: 'All classes' },
    ...(payload?.classes || []).map((classroom) => ({ value: classroom.id, label: classroom.display_name })),
  ]
  const statusOptions = [
    { value: 'eligible', label: 'Eligible' },
    { value: 'all', label: 'All statuses' },
    { value: 'blocked', label: 'Blocked' },
    { value: 'withdrawn', label: 'Withdrawn' },
  ]

  const refreshRosterStatus = async () => {
    await refreshExams({ silent: true })
    setRefreshToken((value) => value + 1)
  }

  return (
    <div className="teacher-reference-page admin-roster-detail">
      <button className="admin-roster-back" type="button" onClick={() => onNavigate('roster')}><RiArrowLeftLine size={17} /> Back to roster</button>

      <div className="teacher-page-heading admin-roster-detail__heading">
        <div>
          <div className="teacher-page-title-line">
            <span className="teacher-page-title-icon"><Icon name="roster" size={27} /></span>
            <h1>{exam.title}</h1>
          </div>
          <p>{[exam.academicLevelName, exam.subjectName, exam.assessmentName].filter(Boolean).join(' · ')}</p>
        </div>
        <RosterState status={exam.rosterStatus} />
      </div>

      <RosterRecoveryNotice
        exam={exam}
        onRefresh={refreshRosterStatus}
        onOpenOperations={() => onNavigate('operation-detail', { selectedExamId: exam.id })}
      />
      {error && <Notice tone="danger">{error}</Notice>}

      <div className="admin-roster-summary" aria-label="Roster summary">
        <SummaryItem label="Current candidates" value={String(exam.rosterCandidateCount || 0)} hint="Academically eligible snapshot" />
        <SummaryItem label="Roster version" value={`v${exam.rosterVersion || 0}`} hint={exam.rosterPreparedAt ? `Updated ${formatCompactDate(exam.rosterPreparedAt)}` : 'Not prepared yet'} />
        <SummaryItem label="Exam state" value={exam.statusLabel} hint={exam.scheduledStartAt ? `Scheduled ${formatCompactDate(exam.scheduledStartAt)}` : 'No scheduled start'} />
      </div>

      <div className="admin-roster-detail__filters">
        <label className="teacher-search-control teacher-search-control--grow">
          <RiSearchLine size={18} aria-hidden="true" />
          <input
            aria-label="Search candidates"
            type="search"
            value={query}
            onChange={(event) => { setQuery(event.target.value); setPage(1) }}
            placeholder="Search candidate name or admission number..."
          />
        </label>
        <SelectControl label="Candidate class filter" value={classId} options={classOptions} onChange={(value) => { setClassId(value); setPage(1) }} />
        <SelectControl label="Candidate status filter" value={status} options={statusOptions} onChange={(value) => { setStatus(value); setPage(1) }} />
      </div>

      <div className="admin-roster-table-shell" aria-busy={loading}>
        <table className="admin-roster-table">
          <thead>
            <tr>
              <th>Candidate</th>
              <th>Admission number</th>
              <th>Class</th>
              <th>Eligibility</th>
              <th>Reason</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {!loading && (payload?.candidates || []).map((candidate) => (
              <tr key={candidate.id}>
                <td><div className="admin-roster-candidate"><span>{initials(candidate.display_name)}</span><strong>{candidate.display_name}</strong></div></td>
                <td><span className="admin-roster-admission">{candidate.admission_number}</span></td>
                <td>{candidate.class_name || '—'}</td>
                <td><CandidateState status={candidate.status} /></td>
                <td className="admin-roster-reason">{candidate.status_reason || '—'}</td>
                <td>
                  <RosterCandidateActionButton
                    candidate={candidate}
                    exam={exam}
                    gateway={gateway}
                    onChanged={() => setRefreshToken((value) => value + 1)}
                  />
                </td>
              </tr>
            ))}
            {loading && <tr><td colSpan={6}><div className="admin-roster-table-state">Loading candidates…</div></td></tr>}
            {!loading && !error && (payload?.candidates || []).length === 0 && (
              <tr><td colSpan={6}><div className="admin-roster-table-state"><strong>No candidates match these filters</strong><span>Try a different class, status, or search term.</span></div></td></tr>
            )}
          </tbody>
        </table>

        <div className="admin-roster-table-footer">
          <span>{payload?.total ? `Showing ${(page - 1) * ROSTER_PAGE_SIZE + 1}–${Math.min(page * ROSTER_PAGE_SIZE, payload.total)} of ${payload.total} candidates` : '0 candidates'}</span>
          <div>
            <button type="button" aria-label="Previous candidate page" disabled={page === 1 || loading} onClick={() => setPage(page - 1)}>‹</button>
            <span>{page} / {pageCount}</span>
            <button type="button" aria-label="Next candidate page" disabled={page === pageCount || loading} onClick={() => setPage(page + 1)}>›</button>
          </div>
        </div>
      </div>
    </div>
  )
}

function RosterCard({ exam, onOpen }) {
  const statusCopy = rosterStatusCopy(exam.rosterStatus)
  return (
    <article className="admin-roster-card">
      <button className="admin-roster-card__open" type="button" onClick={onOpen} aria-label={`Open roster for ${exam.title}`}>
        <div className="admin-roster-card__top">
          <span className="admin-roster-ledger"><Icon name="roster" size={28} /></span>
          <RosterState status={exam.rosterStatus} />
        </div>
        <div className="admin-roster-card__scope">{[exam.academicLevelName, exam.subjectName].filter(Boolean).join(' · ') || 'Examination roster'}</div>
        <h2>{exam.title}</h2>
        <p>{exam.assessmentName}{exam.revisionNumber > 1 ? ` · Revision ${exam.revisionNumber}` : ''}</p>
        <div className="admin-roster-card__status-copy">{statusCopy}</div>
        <div className="admin-roster-card__meta">
          <div><span>Current candidates</span><strong>{exam.rosterCandidateCount || 0}</strong></div>
          <div><span>Roster version</span><strong>v{exam.rosterVersion || 0}</strong></div>
        </div>
        <div className="admin-roster-card__footer">
          <span>{exam.scheduledStartAt ? formatCompactDate(exam.scheduledStartAt) : 'Schedule not set'}</span>
          <strong>View roster <RiArrowRightLine size={16} aria-hidden="true" /></strong>
        </div>
      </button>
    </article>
  )
}

function RosterState({ status }) {
  const normalized = String(status || 'not_prepared').toLowerCase()
  return <span className={`admin-roster-state admin-roster-state--${normalized}`}>{titleCase(normalized)}</span>
}

function CandidateState({ status }) {
  const normalized = String(status || '').toLowerCase()
  return <span className={`admin-candidate-state admin-candidate-state--${normalized}`}>{titleCase(normalized)}</span>
}

function SummaryItem({ label, value, hint }) {
  return <div className="admin-roster-summary__item"><span>{label}</span><strong>{value}</strong><small>{hint}</small></div>
}

function rosterStatusCopy(status) {
  if (status === 'pending') return 'Waiting for candidate preparation.'
  if (status === 'building') return 'Building the candidate snapshot.'
  if (status === 'stale') return 'Enrollment changed; refreshing automatically.'
  if (status === 'failed') return 'Roster needs administrator attention.'
  if (status === 'ready') return 'Candidate snapshot is ready for this sitting.'
  return 'Roster has not been prepared.'
}

function titleCase(value) {
  return String(value || '').replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function formatCompactDate(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat(undefined, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function initials(name) {
  const parts = String(name || '').trim().split(/\s+/).filter(Boolean)
  return parts.slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || '?'
}
