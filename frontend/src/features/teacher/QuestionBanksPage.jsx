import { Icon } from '../../lib/icons'
import { FilterBar, Notice, PageTitle, Panel, SearchField, StatusBadge } from '../../components/ui'
import { BankIcon, QuestionRows } from './components'
import { statusTone } from './utils'

export function QuestionBanksPage({ dispatch, teacherData }) {
  return (
    <>
      <div className="teacher-page-head">
        <PageTitle title="Question Banks" subtitle="Authorable banks returned by the backend." />
      </div>
      {teacherData.error && <Notice tone="danger">{teacherData.error}</Notice>}
      <FilterBar>
        <SearchField label="Search banks" placeholder="Search loaded banks..." />
        <button className="button button--secondary" onClick={teacherData.refresh}>Refresh</button>
      </FilterBar>
      {teacherData.loading && <Panel title="Question Banks"><p>Loading question banks...</p></Panel>}
      {!teacherData.loading && teacherData.banks.length === 0 && (
        <Panel title="Question Banks">
          <Notice>No authorable question banks were returned. Teachers can only create questions inside banks already exposed by the backend.</Notice>
        </Panel>
      )}
      <div className="bank-grid">
        {teacherData.banks.map((bank) => (
          <article key={bank.id} className="bank-card">
            <BankIcon name="book" />
            <h2>{bank.name}</h2>
            <p>{bank.description || 'No description'}</p>
            <small>{bank.count} questions</small>
            <div className="card-actions">
              <StatusBadge tone={statusTone(bank.status)}>{bank.status}</StatusBadge>
              <button className="button button--secondary" onClick={() => dispatch({ type: 'staff', patch: { section: 'bank-detail', selectedBankId: bank.id } })}>Open</button>
            </div>
          </article>
        ))}
      </div>
    </>
  )
}

export function BankDetailPage({ state, dispatch, teacherData }) {
  const bank = teacherData.banks.find((item) => item.id === state.staff.selectedBankId) || teacherData.banks[0]
  const questions = bank ? teacherData.questions.filter((question) => question.bankId === bank.id) : []

  if (!bank) {
    return (
      <>
        <PageTitle title="Question Bank" subtitle="No bank selected." />
        <Notice>No authorable question banks were returned by the backend.</Notice>
      </>
    )
  }

  return (
    <>
      <div className="teacher-page-head">
        <div>
          <button className="text-button" onClick={() => dispatch({ type: 'staff', patch: { section: 'question-banks' } })}>Back to banks</button>
          <PageTitle title={bank.name} subtitle={`${bank.count} questions`} />
        </div>
        <div className="toolbar">
          <button className="button button--secondary" onClick={teacherData.refresh}>
            <Icon name="sync" size={17} /> Refresh
          </button>
          <button className="button button--primary" onClick={() => dispatch({ type: 'staff', patch: { section: 'create-question', selectedBankId: bank.id } })}>
            <Icon name="plus" size={17} /> Add Question
          </button>
        </div>
      </div>
      <FilterBar>
        <SearchField label="Search questions in bank" placeholder="Search loaded questions..." />
      </FilterBar>
      <Panel title="Questions">
        <QuestionRows questions={questions} banks={teacherData.banks} />
      </Panel>
    </>
  )
}
