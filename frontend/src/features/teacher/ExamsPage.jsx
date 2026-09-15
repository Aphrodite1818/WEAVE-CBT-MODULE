import { Icon } from '../../shared/icons/Icon'
import { Notice, PageTitle, Panel } from '../../shared/ui'

export function ExamsPage() {
  return (
    <>
      <div className="teacher-page-head"><PageTitle title="Exams" subtitle="Teacher exam lists are waiting on a backend read contract." /></div>
      <Panel title="Backend contract needed">
        <Notice tone="warning">Leaf is no longer showing fake teacher exam drafts. The backend currently exposes individual exam reads and lifecycle mutations, but no teacher-facing collection route for authored exams.</Notice>
        <div className="quick-actions"><div><strong>Required route</strong><p>Add a real teacher exam list/search endpoint before this page can show drafts, returned exams, submitted exams, or upcoming schedules.</p></div><Icon name="exams" size={30} /></div>
      </Panel>
    </>
  )
}

export function CreateExamPage() {
  return (
    <>
      <div className="teacher-page-head"><PageTitle title="Create Exam" subtitle="Exam creation needs academic IDs not currently exposed to this frontend flow." /></div>
      <Panel title="Backend contract needed"><Notice tone="warning">The create-exam API requires session, term, curriculum subject, assessment scheme/component, and question bank IDs. The current teacher frontend does not have a real route to retrieve and select that academic context, so this form is intentionally unavailable instead of sending fake IDs.</Notice></Panel>
    </>
  )
}
