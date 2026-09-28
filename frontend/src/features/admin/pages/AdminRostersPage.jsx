import { useEffect, useMemo, useState } from 'react'
import { RiArrowLeftLine, RiArrowRightLine, RiSearchLine } from '@remixicon/react'
import { buildAcademicLevels, listSubjectsForLevel } from '../../../shared/academics/authoringScope'
import { Icon } from '../../../shared/icons/Icon'
import { Notice, SelectControl } from '../../../shared/ui'
import { RosterCandidateActionButton, RosterRecoveryNotice } from '../components/RosterCandidateActions'
import {
  partitionRosterExams,
  rosterHistoryDescription,
  rosterHistoryKind,
  rosterHistoryLabel,
} from '../rosterLineage'
import '../admin-rosters.css'
import '../admin-roster-history.css'

const OVERVIEW_PAGE_SIZE = 12
const HISTORY_GROUP_PAGE_SIZE = 6
const ROSTER_PAGE_SIZE = 50
const TRANSITIONAL_ROSTER_STATES = new Set(['pending', 'building', 'stale'])

export function AdminRostersPage({ adminData, onNavigate }) {
  const [query, setQuery] = useState('')
  const [levelId, setLevelId] = useState('all')
  const [subjectId, setSubjectId] = useState('all')
  const [requestedPage, setPage] = useState(1)
  const [requestedHistoryPage, setHistoryPage] = useState(1)

  const levels = useMemo(() => buildAcademicLevels(adminData.subjects), [adminData.subjects])
  const levelSubjects = useMemo(
    () => levelId === 'all' ? [] : listSubjectsForLevel(adminData.subjects, levelId),
    [adminData.subjects, levelId],
  )
  const rosterPresentation = useMemo(
    () => partitionRosterExams(adminData.exams),
    [adminData.exams],
  )
  const currentRosters = rosterPresentation.current
  const historyGroups = rosterPresentation.historyGroups

  const refreshExams = adminData.refreshExams
  useEffect(() => {
    if (!currentRosters.some((exam) => TRANSITIONAL_ROSTER_STATES.has(exam.rosterStatus))) return undefined
    const timer = window.setInterval(() => {
      void refreshExams({ silent: true })
    }, 4000)
    return () => window.clearInterval(timer)
  }, [currentRosters, refreshExams])

  const filteredCurrent = useMemo(
    () => currentRosters.filter((exam) => rosterMatchesFilters(exam, { query, levelId, subjectId })),
    [currentRosters, levelId, query, subjectId],
  )

  const filteredHistoryGroups = useMemo(
    () => historyGroups
      .map((group) => ({
        ...group,
        entries: group.entries.filter((exam) => rosterMatchesFilters(exam, { query, levelId, subjectId })),
      }))
      .filter((group) => group.entries.length > 0),
    [historyGroups, levelId, query, subjectId],
  )

  const pageCount = Math.max(1, Math.ceil(filteredCurrent.length / OVERVIEW_PAGE_SIZE))
  const page = Math.min(requestedPage, pageCount)
  const visible = filteredCurrent.slice((page - 1) * OVERVIEW_PAGE_SIZE, page * OVERVIEW_PAGE_SIZE)

  const historyPageCount = Math.max(1, Math.ceil(filteredHistoryGroups.length / HISTORY_GROUP_PAGE_SIZE))
  const historyPage = Math.min(requestedHistoryPage, historyPageCount)
  const visibleHistoryGroups = filteredHistoryGroups.slice(
    (historyPage - 1) * HISTORY_GROUP_PAGE_SIZE,
    historyPage * HISTORY_GROUP_PAGE_SIZE,
  )

  const levelOptions = [
    { value: 'all', label: 'All levels' },
    ...levels.map((level) => ({ value: level.id, label: level.name })),
  ]
  const subjectOptions = [
    { value: 'all', label: 'All subjects' },
    ...levelSubjects.map((subject) => ({ value: subject.id, label: subject.name, description: subject.code || undefined })),
  ]

  const resetPages = () => {
    setPage(1)
    setHistoryPage(1)
  }

  const changeLevel = (nextLevelId) => {
    setLevelId(nextLevelId)
    setSubjectId('all')
    resetPages()
  }

  return (
    <div className="teacher-reference-page admin-rosters-page">
      <div className="teacher-page-heading admin-rosters-heading">
        <div>
          <div className="teacher-page-title-line">
            <span className="teacher-page-title-icon"><Icon name="roster" size={27} /></span>
            <h1>Roster</h1>
          </div>
          <p>Review the roster that currently matters for each examination. Superseded, closed, and cancelled rosters remain available below as history.</p>
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
            onChange={(event) => { setQuery(event.target.value); resetPages() }}
            placeholder="Search by exam, level, subject, or assessment..."
          />
        </label>
        <SelectControl label="Roster level filter" value={levelId} options={levelOptions} onChange={changeLevel} />
        <SelectControl
          label="Roster subject filter"
          value={subjectId}
          options={subjectOptions}
          onChange={(value) => { setSubjectId(value); resetPages() }}
          disabled={levelId === 'all'}
        />
      </div>

      <section className="admin-roster-section" aria-labelledby="current-rosters-title">
        <div className="admin-roster-section__heading">
          <div>
            <h2 id="current-rosters-title">Current rosters</h2>
            <p>Latest revisions that are preparing for, running, or finalizing a sitting.</p>
          </div>
          <span>{filteredCurrent.length} {filteredCurrent.length === 1 ? 'roster' : 'rosters'}</span>
        </div>

        <div className="admin-roster-grid" aria-label="Current examination rosters" aria-busy={adminData.loading}>
          {visible.map((exam) => (
            <RosterCard
              key={exam.id}
              exam={exam}
              historical={false}
              allExams={adminData.exams}
              onOpen={() => onNavigate('roster-detail', { selectedExamId: exam.id })}
            />
          ))}

          {!adminData.loading && visible.length === 0 && (
            <div className="admin-roster-empty">
              <span><Icon name="roster" size={27} /></span>
              <div>
                <strong>{currentRosters.length ? 'No current rosters match these filters' : 'No current prepared rosters'}</strong>
                <p>{currentRosters.length ? 'Adjust the level, subject, or search filters.' : 'A latest examination revision appears here after its roster is prepared.'}</p>
              </div>
            </div>
          )}
          {adminData.loading && <div className="admin-roster-empty"><div><strong>Loading examination rosters…</strong></div></div>}

          <RosterPagination
            page={page}
            pageCount={pageCount}
            total={filteredCurrent.length}
            pageSize={OVERVIEW_PAGE_SIZE}
            label="rosters"
            onPrevious={() => setPage(page - 1)}
            onNext={() => setPage(page + 1)}
          />
        </div>
      </section>

      <section className="admin-roster-history" aria-labelledby="roster-history-title">
        <div className="admin-roster-section__heading admin-roster-history__heading">
          <div>
            <h2 id="roster-history-title">Roster history</h2>
            <p>Previous revisions and completed or cancelled sittings. Candidate lists remain available for audit.</p>
          </div>
          <span>{filteredHistoryGroups.length} {filteredHistoryGroups.length === 1 ? 'exam group' : 'exam groups'}</span>
        </div>

        {!adminData.loading && visibleHistoryGroups.length === 0 && (
          <div className="admin-roster-empty admin-roster-history__empty">
            <span><Icon name="roster" size={27} /></span>
            <div>
              <strong>{historyGroups.length ? 'No roster history matches these filters' : 'No roster history yet'}</strong>
              <p>{historyGroups.length ? 'Adjust the level, subject, or search filters.' : 'Superseded revisions and terminal exam rosters will be retained here.'}</p>
            </div>
          </div>
        )}

        {visibleHistoryGroups.map((group) => (
          <RosterHistoryGroup
            key={group.id}
            group={group}
            allExams={adminData.exams}
            onNavigate={onNavigate}
          />
        ))}

        {filteredHistoryGroups.length > 0 && (
          <RosterPagination
            page={historyPage}
            pageCount={historyPageCount}
            total={filteredHistoryGroups.length}
            pageSize={HISTORY_GROUP_PAGE_SIZE}
            label="exam groups"
            onPrevious={() => setHistoryPage(historyPage - 1)}
            onNext={() => setHistoryPage(historyPage + 1)}
          />
        )}
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

  const historyKind = exam ? rosterHistoryKind(exam, adminData.exams) : null
  const historical = Boolean(historyKind)
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
    if (historical || !exam || !TRANSITIONAL_ROSTER_STATES.has(exam.rosterStatus)) return undefined
    const timer = window.setInterval(async () => {
      await refreshExams({ silent: true })
      setRefreshToken((value) => value + 1)
    }, 4000)
    return () => window.clearInterval(timer)
  }, [exam?.id, exam?.rosterStatus, historical, refreshExams])

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

  const retryFailedRoster = async () => {
    await gateway.candidates.retryFailedRoster(exam.id)
    await refreshRosterStatus()
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
          <p>{[exam.academicLevelName, exam.subjectName, exam.assessmentName, `Revision ${exam.revisionNumber || 1}`].filter(Boolean).join(' · ')}</p>
        </div>
        <RosterLifecycleState
          status={historical ? historyKind : exam.status}
          label={historical ? rosterHistoryLabel(historyKind) : exam.statusLabel}
        />
      </div>

      {historical ? (
        <Notice tone="warning">{rosterHistoryDescription(exam, adminData.exams)} Candidate records remain fully available below, but this roster is read-only.</Notice>
      ) : (
        <RosterRecoveryNotice
          exam={exam}
          onRefresh={refreshRosterStatus}
          onRetry={retryFailedRoster}
          onOpenOperations={() => onNavigate('operation-detail', { selectedExamId: exam.id })}
        />
      )}
      {error && <Notice tone="danger">{error}</Notice>}

      <div className="admin-roster-summary" aria-label="Roster summary">
        <SummaryItem label={historical ? 'Candidates' : 'Current candidates'} value={String(exam.rosterCandidateCount || 0)} hint={historical ? 'Preserved roster snapshot' : 'Academically eligible snapshot'} />
        <SummaryItem label="Exam revision" value={`Revision ${exam.revisionNumber || 1}`} hint={historical ? 'Historical exam revision' : 'Current exam revision'} />
        <SummaryItem label="Roster version" value={`v${exam.rosterVersion || 0}`} hint={`${titleCase(exam.rosterStatus)}${exam.rosterPreparedAt ? ` · ${formatCompactDate(exam.rosterPreparedAt)}` : ''}`} />
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
              <th>{historical ? 'Access' : 'Actions'}</th>
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
                  {historical ? (
                    <span className="admin-roster-read-only">Read only</span>
                  ) : (
                    <RosterCandidateActionButton
                      candidate={candidate}
                      exam={exam}
                      gateway={gateway}
                      onChanged={() => setRefreshToken((value) => value + 1)}
                    />
                  )}
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

function RosterHistoryGroup({ group, allExams, onNavigate }) {
  const scope = [group.academicLevelName, group.subjectName, group.assessmentName].filter(Boolean).join(' · ')
  return (
    <article className="admin-roster-history-group">
      <div className="admin-roster-history-group__heading">
        <div>
          <span>Exam lineage</span>
          <h3>{group.title}</h3>
          <p>{scope || 'Historical examination rosters'}</p>
        </div>
        <strong>{group.entries.length} historical {group.entries.length === 1 ? 'roster' : 'rosters'}</strong>
      </div>
      <div className="admin-roster-grid admin-roster-history-group__grid">
        {group.entries.map((exam) => (
          <RosterCard
            key={exam.id}
            exam={exam}
            historical
            allExams={allExams}
            onOpen={() => onNavigate('roster-detail', { selectedExamId: exam.id })}
          />
        ))}
      </div>
    </article>
  )
}

function RosterCard({ exam, historical, allExams, onOpen }) {
  const historyKind = historical ? rosterHistoryKind(exam, allExams) : null
  const statusCopy = historical
    ? rosterHistoryDescription(exam, allExams)
    : rosterStatusCopy(exam.rosterStatus)
  const statusLabel = historical ? rosterHistoryLabel(historyKind) : exam.statusLabel
  const statusValue = historical ? historyKind : exam.status

  return (
    <article className={`admin-roster-card${historical ? ' admin-roster-card--historical' : ''}`}>
      <button className="admin-roster-card__open" type="button" onClick={onOpen} aria-label={`${historical ? 'Open historical roster' : 'Open roster'} for ${exam.title} revision ${exam.revisionNumber || 1}`}>
        <div className="admin-roster-card__top">
          <span className="admin-roster-ledger"><Icon name="roster" size={28} /></span>
          <RosterLifecycleState status={statusValue} label={statusLabel} />
        </div>
        <div className="admin-roster-card__scope">{[exam.academicLevelName, exam.subjectName].filter(Boolean).join(' · ') || 'Examination roster'}</div>
        <h2>{exam.title}</h2>
        <p>{exam.assessmentName} · Revision {exam.revisionNumber || 1}</p>
        <div className="admin-roster-card__status-copy">{statusCopy}</div>
        <div className="admin-roster-card__meta">
          <div><span>{historical ? 'Candidates' : 'Current candidates'}</span><strong>{exam.rosterCandidateCount || 0}</strong></div>
          <div><span>Roster version</span><strong>v{exam.rosterVersion || 0}</strong></div>
        </div>
        <div className="admin-roster-card__footer">
          <span>{exam.scheduledStartAt ? formatCompactDate(exam.scheduledStartAt) : 'Schedule not set'}</span>
          <strong>{historical ? 'View historical roster' : 'View roster'} <RiArrowRightLine size={16} aria-hidden="true" /></strong>
        </div>
      </button>
    </article>
  )
}

function RosterLifecycleState({ status, label }) {
  const normalized = String(status || 'historical').toLowerCase()
  return <span className={`admin-roster-lifecycle-state admin-roster-lifecycle-state--${normalized}`}>{label || titleCase(normalized)}</span>
}

function CandidateState({ status }) {
  const normalized = String(status || '').toLowerCase()
  return <span className={`admin-candidate-state admin-candidate-state--${normalized}`}>{titleCase(normalized)}</span>
}

function SummaryItem({ label, value, hint }) {
  return <div className="admin-roster-summary__item"><span>{label}</span><strong>{value}</strong><small>{hint}</small></div>
}

function RosterPagination({ page, pageCount, total, pageSize, label, onPrevious, onNext }) {
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, total)
  return (
    <div className="admin-roster-pagination">
      <span>{total === 0 ? `0 ${label}` : `Showing ${start}–${end} of ${total} ${label}`}</span>
      <div>
        <button type="button" aria-label={`Previous ${label} page`} disabled={page === 1} onClick={onPrevious}>‹</button>
        <span>{page} / {pageCount}</span>
        <button type="button" aria-label={`Next ${label} page`} disabled={page === pageCount} onClick={onNext}>›</button>
      </div>
    </div>
  )
}

function rosterMatchesFilters(exam, { query, levelId, subjectId }) {
  if (levelId !== 'all' && exam.academicLevelId !== levelId) return false
  if (subjectId !== 'all' && exam.curriculumSubjectId !== subjectId) return false
  const needle = query.trim().toLowerCase()
  if (!needle) return true
  return `${exam.title} ${exam.academicLevelName} ${exam.subjectName} ${exam.assessmentName} revision ${exam.revisionNumber || 1}`.toLowerCase().includes(needle)
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
