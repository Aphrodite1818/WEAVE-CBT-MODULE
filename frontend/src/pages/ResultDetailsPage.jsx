import { PublicLayout } from '../layouts/PublicLayout'
import { Button, StatusBadge } from '../components/Ui'
import { Icon } from '../lib/icons'
import { questions } from '../mocks/data'

export function ResultDetailsPage({ navigate }) {
  const statuses = ['correct', 'correct', 'correct', 'correct', 'correct', 'correct', 'correct', 'incorrect', 'incorrect', 'unanswered']
  return <PublicLayout minimal>
    <section className="details-page">
      <button className="back-link" onClick={() => navigate('/welcome')}><Icon name="back" /> Back to portal</button>
      <header className="details-header"><div><span className="eyebrow">Released result</span><h1>SS2 Biology Mock Examination</h1><p>Amina Okeke · BFA/2024/0187 · Submitted 12 Aug, 09:18</p></div><StatusBadge tone="success">Result released</StatusBadge></header>
      <section className="result-overview">
        <article className="grade-card"><div className="score-ring"><span><strong>70</strong><small>/100</small></span></div><div><span>Normalized score</span><h2>Good performance</h2><p>7 correct answers from 10 questions.</p></div></article>
        <article className="breakdown-card"><div><span className="breakdown-dot correct" /><strong>7</strong><small>Correct</small></div><div><span className="breakdown-dot incorrect" /><strong>2</strong><small>Incorrect</small></div><div><span className="breakdown-dot unanswered" /><strong>1</strong><small>Unanswered</small></div></article>
        <article className="component-card"><Icon name="info" /><div><strong>Component result only</strong><p>The school’s final academic grade is calculated separately in Weave.</p></div></article>
      </section>
      <section className="panel question-review">
        <div className="panel__head"><div><h2>Question summary</h2><p>Performance across all 10 questions</p></div><Button variant="secondary" onClick={() => window.print()}><Icon name="print" /> Print</Button></div>
        <div className="review-list">{questions.map((question, index) => <div className="review-row" key={question.text}><span className={`review-status review-status--${statuses[index]}`}><Icon name={statuses[index] === 'correct' ? 'check' : statuses[index] === 'incorrect' ? 'close' : 'minus'} /></span><span className="review-number">{String(index + 1).padStart(2, '0')}</span><div><strong>{question.text}</strong><small>{statuses[index] === 'correct' ? `Correct · ${question.options[question.correct]}` : statuses[index] === 'incorrect' ? `Incorrect · Correct answer: ${question.options[question.correct]}` : 'Not answered'}</small></div><StatusBadge tone={statuses[index] === 'correct' ? 'success' : statuses[index] === 'incorrect' ? 'danger' : 'neutral'}>{statuses[index]}</StatusBadge></div>)}</div>
      </section>
    </section>
  </PublicLayout>
}
