import {
  RiAddLine,
  RiBookOpenLine,
  RiCalendarTodoLine,
  RiDatabase2Line,
  RiFileAddLine,
  RiFileList3Line,
  RiGraduationCapLine,
  RiStackLine,
} from '@remixicon/react'
import { Notice } from '../../shared/ui'

const statConfig = [
  { key: 'subjects', tone: 'blue', icon: RiBookOpenLine, label: 'My Subjects', caption: 'Assigned subjects', section: null },
  { key: 'banks', tone: 'green', icon: RiStackLine, label: 'Question Banks', caption: 'Available to author', section: 'question-banks' },
  { key: 'drafts', tone: 'amber', icon: RiFileList3Line, label: 'Draft Exams', caption: 'Need completion', section: 'exams' },
  { key: 'submitted', tone: 'rose', icon: RiCalendarTodoLine, label: 'Submitted Exams', caption: 'Awaiting administration', section: 'exams' },
]

export function OverviewPage({ state, dispatch, teacherData }) {
  const teacherName = state.session?.actor?.display_name || state.session?.name || 'Teacher'
  const firstName = teacherName.split(' ').filter(Boolean)[0] || 'Teacher'
  const draftExams = teacherData.exams.filter((exam) => exam.status === 'draft')
  const submittedExams = teacherData.exams.filter((exam) => exam.status === 'submitted')
  const teachingScope = groupAssignments(teacherData.assignments)
  const stats = {
    subjects: teacherData.loading ? '—' : teacherData.subjects.length,
    banks: teacherData.loading ? '—' : teacherData.banks.length,
    drafts: teacherData.loading ? '—' : draftExams.length,
    submitted: teacherData.loading ? '—' : submittedExams.length,
  }

  const goTo = (section, patch = {}) => dispatch({ type: 'staff', patch: { section, ...patch } })
  const academicContext = [teacherData.session?.name, teacherData.term?.name].filter(Boolean).join('  •  ')

  return (
    <div className="teacher-overview-page">
      <section className="teacher-overview-hero" aria-labelledby="teacher-overview-title">
        <div className="teacher-overview-hero__greeting">
          <span className="teacher-overview-sun" aria-hidden="true">☀</span>
          <div>
            <h1 id="teacher-overview-title">Good morning, {firstName}!</h1>
            <p>{academicContext || 'Academic context will appear after the local projection is available.'}</p>
          </div>
        </div>
        <blockquote>“Better teachers build<br />brighter futures.”</blockquote>
      </section>

      {teacherData.error && <Notice tone="danger">{teacherData.error}</Notice>}
      {!teacherData.error && teacherData.warning && <Notice tone="warning">Some dashboard data could not be refreshed. Available local data is still shown below.</Notice>}

      <section className="teacher-overview-stats" aria-label="Teacher workspace summary" aria-busy={teacherData.loading}>
        {statConfig.map((stat) => (
          <OverviewStat
            key={stat.key}
            {...stat}
            value={stats[stat.key]}
            onClick={stat.section ? () => goTo(stat.section) : undefined}
          />
        ))}
      </section>

      <section className="teacher-overview-columns">
        <article className="teacher-reference-panel teacher-reference-panel--work">
          <div className="teacher-reference-panel__head">
            <div>
              <h2>Continue Working</h2>
              <p>Draft examinations that still need your attention.</p>
            </div>
            <button type="button" onClick={() => goTo('exams')}>View all</button>
          </div>

          <div className="teacher-work-list">
            {draftExams.slice(0, 4).map((exam) => (
              <div className="teacher-work-row" key={exam.id}>
                <div>
                  <strong>{exam.title}</strong>
                  <span>{exam.subjectName} · {exam.questionCount} questions · {formatSelectionMode(exam.selectionMode)}</span>
                </div>
                <span className="teacher-mini-status teacher-mini-status--draft">Draft</span>
                <button type="button" onClick={() => goTo('exams', { selectedExamId: exam.id })}>Continue</button>
              </div>
            ))}

            {!teacherData.loading && draftExams.length === 0 && (
              <div className="teacher-reference-empty">
                <RiCalendarTodoLine size={25} aria-hidden="true" />
                <div><strong>No draft exams right now</strong><p>When you create a paper, unfinished drafts will appear here.</p></div>
                <button type="button" onClick={() => goTo('create-exam')}>Create exam</button>
              </div>
            )}
            {teacherData.loading && <div className="teacher-reference-loading">Loading your exam workspace…</div>}
          </div>
        </article>

        <article className="teacher-reference-panel teacher-reference-panel--scope">
          <div className="teacher-reference-panel__head">
            <div>
              <h2>Your Teaching Scope</h2>
              <p>Current Weave assignments available to this CBT server.</p>
            </div>
          </div>

          <div className="teacher-scope-list">
            {teachingScope.slice(0, 5).map((subject) => (
              <div className="teacher-scope-row" key={subject.key}>
                <div><strong>{subject.name}</strong><span>{subject.classes.join(', ')}</span></div>
                <span>{subject.classes.length} {subject.classes.length === 1 ? 'class' : 'classes'}</span>
              </div>
            ))}
            {!teacherData.loading && teachingScope.length === 0 && (
              <div className="teacher-reference-empty teacher-reference-empty--compact">
                <div><strong>No effective assignments</strong><p>Assignments will appear here after they are synced from Weave.</p></div>
              </div>
            )}
          </div>
        </article>
      </section>

      <section className="teacher-reference-panel teacher-quick-actions-card">
        <div className="teacher-reference-panel__head">
          <div><h2>Quick Actions</h2><p>Jump directly into the teacher workflows you use most.</p></div>
        </div>
        <nav className="teacher-quick-actions" aria-label="Teacher quick actions">
          <button type="button" className="primary" disabled={teacherData.banks.length === 0} onClick={() => goTo('create-question', { selectedBankId: teacherData.banks[0]?.id })}>
            <RiAddLine size={18} /> Create Question
          </button>
          <button type="button" onClick={() => goTo('create-exam')}><RiFileAddLine size={18} /> Create Exam</button>
          <button type="button" onClick={() => goTo('question-banks')}><RiDatabase2Line size={18} /> Question Banks</button>
          <button type="button" onClick={() => goTo('exams')}><RiGraduationCapLine size={18} /> View All Exams</button>
        </nav>
      </section>
    </div>
  )
}

function OverviewStat({ tone, icon: StatIcon, label, caption, value, onClick }) {
  const content = (
    <>
      <span className="teacher-overview-stat__icon"><StatIcon size={23} aria-hidden="true" /></span>
      <strong>{value}</strong>
      <span>{label}</span>
      <small>{caption}</small>
    </>
  )

  if (!onClick) return <article className={`teacher-overview-stat teacher-overview-stat--${tone}`}>{content}</article>
  return <button type="button" className={`teacher-overview-stat teacher-overview-stat--${tone}`} onClick={onClick}>{content}</button>
}

function groupAssignments(assignments) {
  const groups = new Map()
  assignments.forEach((assignment) => {
    const key = assignment.curriculumSubjectId || assignment.subjectId || assignment.subjectName
    if (!groups.has(key)) groups.set(key, { key, name: assignment.subjectName, classes: [] })
    const group = groups.get(key)
    if (assignment.className && !group.classes.includes(assignment.className)) group.classes.push(assignment.className)
  })
  return [...groups.values()]
}

function formatSelectionMode(mode) {
  return String(mode || 'random').toLowerCase() === 'manual' ? 'Manual selection' : 'Random selection'
}
