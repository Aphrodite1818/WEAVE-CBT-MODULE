import {
  RiAddLine,
  RiArrowRightLine,
  RiBarChartBoxLine,
  RiCalendarTodoLine,
  RiDatabase2Line,
  RiFileAddLine,
  RiFileList3Line,
  RiGraduationCapLine,
  RiMore2Fill,
  RiQuestionAnswerLine,
  RiUserStarLine,
} from '@remixicon/react'
import { Notice, StatusBadge } from '../../shared/ui'

const dashboardStats = [
  { key: 'banks', tone: 'blue', icon: RiFileList3Line, label: 'Question Banks', section: 'question-banks' },
  { key: 'questions', tone: 'green', icon: RiQuestionAnswerLine, label: 'Total Questions', section: 'questions' },
  { key: 'exams', tone: 'purple', icon: RiCalendarTodoLine, label: 'Exams Created', section: 'exams' },
  { key: 'students', tone: 'orange', icon: RiUserStarLine, label: 'Students Assessed' },
]

export function OverviewPage({ dispatch, teacherData }) {
  const banks = teacherData.banks
  const questions = teacherData.questions
  const recentExams = teacherData.exams || []
  const stats = {
    banks: teacherData.loading ? '—' : banks.length,
    questions: teacherData.loading ? '—' : questions.length,
    exams: '—',
    students: '—',
  }

  const goTo = (section, patch = {}) => dispatch({ type: 'staff', patch: { section, ...patch } })

  return (
    <div className="teacher-dashboard">
      <section className="teacher-dashboard-hero" aria-labelledby="teacher-dashboard-title">
        <div>
          <span>Good morning,</span>
          <h1 id="teacher-dashboard-title">Teacher Dashboard</h1>
          <p>Manage your question banks, create exams and keep your assessments organised in one place.</p>
        </div>
        <div className="teacher-hero-mark" aria-hidden="true">
          <RiGraduationCapLine size={72} />
          <small>Better assessments<br />Brighter futures</small>
        </div>
      </section>

      {teacherData.error && <Notice tone="danger">{teacherData.error}</Notice>}

      <section className="teacher-stat-grid" aria-label="Teacher workspace summary" aria-busy={teacherData.loading}>
        {dashboardStats.map((stat) => (
          <DashboardStat
            key={stat.key}
            {...stat}
            value={stats[stat.key]}
            unavailable={stat.key === 'exams' || stat.key === 'students'}
            onClick={stat.section ? () => goTo(stat.section) : undefined}
          />
        ))}
      </section>

      <section className="teacher-dashboard-grid">
        <article className="teacher-dashboard-panel teacher-dashboard-panel--wide">
          <div className="teacher-panel-heading">
            <div>
              <h2>Recent Exams</h2>
              <p>Your latest authored assessments will appear here.</p>
            </div>
            <button type="button" onClick={() => goTo('exams')}>View all</button>
          </div>

          <div className="teacher-exam-list">
            <table>
              <thead>
                <tr>
                  <th scope="col">Title</th>
                  <th scope="col">Subject</th>
                  <th scope="col">Questions</th>
                  <th scope="col">Created on</th>
                  <th scope="col">Status</th>
                  <th scope="col"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {recentExams.map((exam) => (
                  <ExamRow key={exam.id} exam={exam} onOpen={() => goTo('exams')} />
                ))}
                {!teacherData.loading && recentExams.length === 0 && (
                  <tr className="teacher-exam-empty-row">
                    <td colSpan="6">
                      <span><RiCalendarTodoLine aria-hidden="true" /></span>
                      <div>
                        <strong>No recent exams to show yet</strong>
                        <p>The backend does not currently provide a teacher exam list. Real exams will appear here when that contract is available.</p>
                      </div>
                    </td>
                  </tr>
                )}
                {teacherData.loading && (
                  <tr className="teacher-exam-empty-row">
                    <td colSpan="6"><div><strong>Loading teacher content…</strong></div></td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </article>

        <article className="teacher-dashboard-panel teacher-dashboard-actions">
          <div className="teacher-panel-heading">
            <div>
              <h2>Quick Actions</h2>
              <p>Get started with common tasks.</p>
            </div>
          </div>
          <nav className="teacher-action-list" aria-label="Teacher quick actions">
            <button type="button" onClick={() => goTo('create-exam')}><RiAddLine size={18} /> <span>Create New Exam</span></button>
            <button type="button" onClick={() => goTo('question-banks')}><RiDatabase2Line size={18} /> <span>Manage Question Banks</span></button>
            <button type="button" disabled={banks.length === 0} onClick={() => goTo('create-question', { selectedBankId: banks[0]?.id })}><RiFileAddLine size={18} /> <span>Add New Question</span></button>
            <button type="button" disabled title="Teacher reporting is not available yet"><RiBarChartBoxLine size={18} /> <span>View Reports</span></button>
          </nav>
        </article>
      </section>

      <section className="teacher-dashboard-banner">
        <span><RiGraduationCapLine size={27} aria-hidden="true" /></span>
        <div>
          <strong>Create better assessments for brighter futures.</strong>
          <p>Quality questions. Fair exams. Stronger students.</p>
        </div>
        <small aria-hidden="true">Exams made simple</small>
      </section>
    </div>
  )
}

function DashboardStat({ tone, icon: StatIcon, label, value, unavailable, onClick }) {
  return (
    <article className={`teacher-stat-card teacher-stat-card--${tone}`}>
      <span className="teacher-stat-card__icon"><StatIcon className="teacher-kpi-icon" size={28} aria-hidden="true" /></span>
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
        {unavailable ? (
          <small>Not available yet</small>
        ) : (
          <button type="button" onClick={onClick}>View all <RiArrowRightLine size={13} aria-hidden="true" /></button>
        )}
      </div>
    </article>
  )
}

function ExamRow({ exam, onOpen }) {
  return (
    <tr>
      <td><strong>{exam.title}</strong></td>
      <td>{exam.subject || '—'}</td>
      <td>{exam.questionCount ?? exam.questions ?? '—'}</td>
      <td>{formatExamDate(exam.createdAt || exam.createdOn)}</td>
      <td><StatusBadge tone={exam.status === 'Published' ? 'success' : 'info'}>{exam.status}</StatusBadge></td>
      <td><button type="button" aria-label={`Open ${exam.title}`} onClick={onOpen}><RiMore2Fill size={17} aria-hidden="true" /></button></td>
    </tr>
  )
}

function formatExamDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('en', { day: 'numeric', month: 'short', year: 'numeric' }).format(date)
}
