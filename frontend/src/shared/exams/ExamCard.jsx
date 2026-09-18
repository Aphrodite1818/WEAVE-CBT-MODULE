import { RiCalendarLine, RiEdit2Line, RiFolderOpenFill, RiGridLine, RiListCheck } from '@remixicon/react'

export function ExamFolder({ color = '#8190a5', size = 64 }) {
  return <RiFolderOpenFill className="exam-folder" size={size} style={{ color }} aria-hidden="true" />
}

export function ExamViewToggle({ value, onChange }) {
  return <div className="exam-view-toggle" aria-label="Examination view">
    <button type="button" aria-label="Grid view" aria-pressed={value === 'grid'} onClick={() => onChange('grid')}><RiGridLine size={19} /></button>
    <button type="button" aria-label="List view" aria-pressed={value === 'list'} onClick={() => onChange('list')}><RiListCheck size={19} /></button>
  </div>
}

export function ExamCard({ exam, onOpen, onEdit, children }) {
  const dated = exam.scheduledStartAt
    ? ['Scheduled', exam.scheduledStartAt]
    : exam.status === 'draft' ? ['Created', exam.createdAt] : ['Updated', exam.updatedAt]
  const date = dated[1] ? new Date(dated[1]) : null
  return <article className="exam-card">
    <button type="button" className="exam-card__open" aria-label={`Open ${exam.title}`} onClick={onOpen}>
      <ExamFolder />
      <h2 title={exam.title}>{exam.title}</h2>
      <p title={`${exam.subjectName} · ${exam.assessmentName}`}>{exam.subjectName} <span>·</span> {exam.assessmentName}</p>
    </button>
    <div className="exam-card__menu">{children}</div>
    <span className={`exam-status exam-status--${exam.status}`}>{exam.statusLabel}</span>
    <div className="exam-card__date"><RiCalendarLine size={16} />{date && !Number.isNaN(date.getTime()) ? `${dated[0]} ${date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })}` : 'Not scheduled'}</div>
    <div className="exam-card__footer"><span>{exam.questionCount} questions <span>·</span> {exam.durationMinutes} min</span>{onEdit && <button type="button" onClick={onEdit}><RiEdit2Line size={16} /> Edit</button>}</div>
  </article>
}
