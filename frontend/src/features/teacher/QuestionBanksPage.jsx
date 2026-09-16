import { useMemo, useState } from 'react'
import { RiArrowRightLine, RiInformationLine, RiRefreshLine, RiSearchLine, RiStackLine } from '@remixicon/react'
import { Icon } from '../../shared/icons/Icon'
import { Notice, PageTitle, Panel, StatusBadge } from '../../shared/ui'
import { QuestionRows } from './components'
import { statusTone } from './utils'

export function QuestionBanksPage({ dispatch, teacherData }) {
  const [query, setQuery] = useState('')
  const banks = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return teacherData.banks
    return teacherData.banks.filter((bank) => `${bank.name} ${bank.description || ''}`.toLowerCase().includes(needle))
  }, [query, teacherData.banks])

  return (
    <div className="teacher-reference-page">
      <div className="teacher-page-heading teacher-page-heading--with-search">
        <div>
          <h1>Question Banks</h1>
          <p>These are the question banks you are currently authorized to contribute to.</p>
        </div>
        <label className="teacher-search-control">
          <RiSearchLine size={17} aria-hidden="true" />
          <input aria-label="Search question banks" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search banks..." />
        </label>
      </div>

      {teacherData.error && <Notice tone="danger">{teacherData.error}</Notice>}

      {teacherData.loading && <div className="teacher-page-loading">Loading your question banks…</div>}
      {!teacherData.loading && teacherData.banks.length === 0 && (
        <div className="teacher-reference-empty teacher-reference-empty--large">
          <RiStackLine size={30} aria-hidden="true" />
          <div><strong>No authorable question banks</strong><p>Your administrator creates question banks. Banks assigned to your teaching scope will appear here automatically.</p></div>
        </div>
      )}

      <section className="teacher-bank-grid" aria-label="Authorable question banks">
        {banks.map((bank) => (
          <article key={bank.id} className="teacher-bank-card">
            <span className="teacher-bank-card__icon"><RiStackLine size={22} aria-hidden="true" /></span>
            <div className="teacher-bank-card__body">
              <h2>{bank.name}</h2>
              <p>{bank.description || 'Question bank available for your current teaching assignment.'}</p>
              <div className="teacher-bank-card__meta">
                <span>{bank.count} {bank.count === 1 ? 'question' : 'questions'}</span>
                <StatusBadge tone={statusTone(bank.status)}>{bank.status}</StatusBadge>
              </div>
            </div>
            <button
              type="button"
              className="teacher-bank-card__action"
              onClick={() => dispatch({ type: 'staff', patch: { section: 'bank-detail', selectedBankId: bank.id } })}
            >
              View Questions <RiArrowRightLine size={16} aria-hidden="true" />
            </button>
          </article>
        ))}
      </section>

      {!teacherData.loading && teacherData.banks.length > 0 && banks.length === 0 && (
        <div className="teacher-reference-empty teacher-reference-empty--compact"><div><strong>No matching banks</strong><p>Try another bank name or clear the search.</p></div></div>
      )}

      <aside className="teacher-info-banner">
        <span><RiInformationLine size={20} aria-hidden="true" /></span>
        <div>
          <strong>Can’t find a bank?</strong>
          <p>You only see banks that match your current Weave teaching authorization. If something is missing, ask your school administrator to check your assignment.</p>
        </div>
        <button type="button" onClick={teacherData.refresh}><RiRefreshLine size={16} /> Refresh</button>
      </aside>
    </div>
  )
}

export function BankDetailPage({ state, dispatch, teacherData }) {
  const bank = teacherData.banks.find((item) => item.id === state.staff.selectedBankId) || teacherData.banks[0]
  const questions = bank ? teacherData.questions.filter((question) => question.bankId === bank.id) : []

  if (!bank) {
    return <><PageTitle title="Question Bank" subtitle="No bank selected." /><Notice>No authorable question banks were returned by the backend.</Notice></>
  }

  return (
    <div className="teacher-reference-page">
      <div className="teacher-page-head">
        <div><button className="text-button" onClick={() => dispatch({ type: 'staff', patch: { section: 'question-banks' } })}>Back to banks</button><PageTitle title={bank.name} subtitle={`${bank.count} questions`} /></div>
        <div className="toolbar">
          <button className="button button--secondary" onClick={teacherData.refresh}><Icon name="sync" size={17} /> Refresh</button>
          <button className="button button--primary" onClick={() => dispatch({ type: 'staff', patch: { section: 'create-question', selectedBankId: bank.id } })}><Icon name="plus" size={17} /> Add Question</button>
        </div>
      </div>
      <Panel title="Questions"><QuestionRows questions={questions} banks={teacherData.banks} /></Panel>
    </div>
  )
}
