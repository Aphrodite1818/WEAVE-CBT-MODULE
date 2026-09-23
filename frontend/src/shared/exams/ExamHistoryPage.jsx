import { RiEdit2Line } from '@remixicon/react'
import { ExamFolder } from './ExamCard'
import { examRevisionHistory } from './examLineage'
import { canManageExam } from './examPermissions'
import { useAuthoringResultReviews } from './useAuthoringResultReviews'
import { Icon } from '../icons/Icon'
import './exam-workspace.css'

export function ExamHistoryPage({ state, dispatch, teacherData, gateway }) {
  const selected = teacherData.exams.find((exam) => exam.id === state.staff.selectedExamId)
  const reviews = useAuthoringResultReviews(gateway, teacherData.exams, state.session?.actor?.role === 'admin')
  const history = selected ? examRevisionHistory(teacherData.exams, selected) : []
  const current = history[0]
  const navigate = (section, id = null) => dispatch({ type: 'staff', patch: { section, selectedExamId: id, examAuthoringNotice: '' } })

  return <div className="teacher-reference-page exam-history-page">
    <header className="teacher-page-heading">
      <div><div className="teacher-page-title-line"><span className="teacher-page-title-icon"><Icon name="exam" size={26} /></span><h1>Examination history</h1></div><p>One examination, from its first draft to its latest revision.</p></div>
      <button type="button" className="teacher-secondary-action" onClick={() => navigate('exams')}><Icon name="back" size={17} /> Back to Examinations</button>
    </header>
    {teacherData.loading && !current ? <p role="status">Loading examination history...</p> : !current ? <p role="status">This examination is no longer available.</p> : <>
      <section className="exam-history-overview" aria-label="Current examination">
        <ExamFolder color={current.folderColor || undefined} size={60} />
        <div className="exam-history-overview__title"><span className="exam-history-eyebrow">Examination record</span><h2>{current.title}</h2><p>{current.academicLevelName} / {current.subjectName} / {current.assessmentName}</p></div>
        <div className="exam-history-overview__current"><span className={`exam-status exam-status--${current.status}`}>{current.statusLabel}</span><span>Revision {current.revisionNumber || 1} / Current</span></div>
      </section>
      {reviews.error && <p className="exam-authoring-recovery" role="status">{reviews.error}</p>}
      <section className="exam-history-records" aria-labelledby="revision-history-title">
        <div className="exam-history-section-heading"><div><h2 id="revision-history-title">Revision history</h2><p>Latest first. Earlier revisions remain preserved.</p></div><span>{history.length} {history.length === 1 ? 'revision' : 'revisions'}</span></div>
        <ol className="exam-history-timeline">{history.map((exam, index) => {
          const disposition = reviews.reviews.find((review) => review.exam_id === exam.id)?.result_disposition
          const editable = index === 0 && canManageExam(exam, state.session?.actor, teacherData.assignments)
          return <li key={exam.id} className={index === 0 ? 'is-current' : ''}>
            <span className="exam-history-marker" aria-hidden="true">{exam.revisionNumber || 1}</span>
            <article className="exam-history-record">
              <header><div><div className="exam-history-record__title"><h3>Revision {exam.revisionNumber || 1}</h3>{index === 0 && <span className="exam-history-current-tag">Current</span>}</div><p>{exam.title}</p></div><div className="exam-history-record__badges"><span className={`exam-status exam-status--${exam.status}`}>{exam.statusLabel}</span>{disposition && <span className="exam-history-disposition">{label(disposition)}</span>}</div></header>
              <dl className="exam-history-facts"><div><dt>Questions</dt><dd>{exam.questionCount}</dd></div><div><dt>Duration</dt><dd>{exam.durationMinutes} minutes</dd></div><div><dt>Created</dt><dd>{date(exam.createdAt)}</dd></div><div><dt>Scheduled</dt><dd>{date(exam.scheduledStartAt)}</dd></div></dl>
              <footer><details><summary>Revision details</summary><dl className="exam-history-details"><div><dt>Assessment</dt><dd>{exam.assessmentName}</dd></div><div><dt>Question selection</dt><dd>{label(exam.selectionMode)}</dd></div><div><dt>Instructions</dt><dd>{exam.instructions || 'No instructions added.'}</dd></div>{exam.closedAt && <div><dt>Closed</dt><dd>{date(exam.closedAt)}</dd></div>}</dl></details>{editable && <button type="button" className="teacher-secondary-action" onClick={() => navigate('create-exam', exam.id)}><RiEdit2Line size={16} /> Edit draft</button>}</footer>
            </article>
          </li>
        })}</ol>
      </section>
    </>}
  </div>
}

function label(value) { return String(value || 'Not specified').replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()) }
function date(value) {
  if (!value) return 'Not scheduled'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? 'Unavailable' : parsed.toLocaleString(undefined, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}
