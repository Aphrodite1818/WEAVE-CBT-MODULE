import { Icon } from '../../shared/icons/Icon'
import { Metric, Notice, PageTitle, Panel, StatusBadge } from '../../shared/ui'
import { BankIcon } from './components'
import { statusTone } from './utils'

export function OverviewPage({ state, dispatch, teacherData }) {
  const banks = teacherData.banks
  const questions = teacherData.questions
  const teacherName = state.session?.actor?.display_name || state.session?.name || 'Teacher'

  return (
    <>
      <PageTitle title={`Good morning, ${firstName(teacherName)}`} subtitle="Live content from the local CBT backend." />
      {teacherData.error && <Notice tone="danger">{teacherData.error}</Notice>}
      <div className="teacher-metric-grid">
        <Metric label="Question Banks" value={teacherData.loading ? '-' : banks.length} helper="Authorable banks" />
        <Metric label="Questions" value={teacherData.loading ? '-' : questions.length} helper="Loaded from bank items" />
        <Metric label="Exam Drafts" value="-" helper="Needs teacher exam list API" />
        <Metric label="Upcoming Exams" value="-" helper="Needs exam schedule/list API" />
      </div>
      <div className="teacher-two-column">
        <Panel title="Recent Question Banks" action={<button className="text-button" onClick={() => dispatch({ type: 'staff', patch: { section: 'question-banks' } })}>View all banks</button>}>
          {teacherData.loading && <p>Loading question banks...</p>}
          {!teacherData.loading && banks.length === 0 && <Notice>No authorable question banks were returned by the backend.</Notice>}
          <div className="bank-list">
            {banks.slice(0, 3).map((bank) => (
              <button key={bank.id} className="bank-row" onClick={() => dispatch({ type: 'staff', patch: { section: 'bank-detail', selectedBankId: bank.id } })}>
                <BankIcon name="book" />
                <span><strong>{bank.name}</strong><small>{bank.count} questions</small></span>
                <StatusBadge tone={statusTone(bank.status)}>{bank.status}</StatusBadge>
              </button>
            ))}
          </div>
        </Panel>
        <Panel title="Upcoming / Recent Exams">
          <Notice tone="warning">The backend does not currently expose a teacher exam list. Leaf will not show fake authored exams here.</Notice>
          <div className="quick-actions"><div><strong>Exam authoring contract needed</strong><p>Add a real exam collection route before this panel can show drafts and submitted exams.</p></div><Icon name="exams" size={28} /></div>
        </Panel>
      </div>
      <Panel title="Continue working">
        <div className="quick-actions">
          <div><strong>Create new content</strong><p>Questions can be added to authorable banks returned by the backend.</p></div>
          <div className="toolbar">
            <button className="button button--primary" disabled={banks.length === 0} onClick={() => dispatch({ type: 'staff', patch: { section: 'create-question', selectedBankId: banks[0]?.id } })}>
              <Icon name="plus" size={17} /> New Question
            </button>
          </div>
        </div>
      </Panel>
    </>
  )
}

function firstName(name) {
  return name.split(' ')[0]
}
