import { useState } from 'react'
import { ExamLayout } from '../layouts/ExamLayout'
import { Button } from '../components/Ui'
import { Icon } from '../lib/icons'
import { questions } from '../mocks/data'

export function ExamPage({ navigate }) {
  const [current, setCurrent] = useState(0)
  const [answers, setAnswers] = useState({ 0: 1, 1: 2, 2: 3, 3: 1, 4: 2, 5: 1, 6: 3 })
  const [review, setReview] = useState([7])
  const [showSubmit, setShowSubmit] = useState(false)
  const question = questions[current]
  const toggleReview = () => setReview((items) => items.includes(current) ? items.filter((item) => item !== current) : [...items, current])
  return <ExamLayout title="SS2 Biology Mock Examination" time="14:32">
    <div className="exam-body">
      <section className="question-stage">
        <div className="exam-progress"><span>Question {current + 1} of {questions.length}</span><div><i style={{ width: `${((current + 1) / questions.length) * 100}%` }} /></div><strong>{Math.round(((current + 1) / questions.length) * 100)}%</strong></div>
        <article className="question-card">
          <div className="question-meta"><span>Biology · Single answer</span><button className={review.includes(current) ? 'review-button active' : 'review-button'} onClick={toggleReview}><Icon name="flag" /> {review.includes(current) ? 'Marked for review' : 'Mark for review'}</button></div>
          <h1><span>{String(current + 1).padStart(2, '0')}</span>{question.text}</h1>
          <div className="answer-list">{question.options.map((option, index) => <label className={answers[current] === index ? 'answer-option selected' : 'answer-option'} key={option}><input type="radio" name={`question-${current}`} checked={answers[current] === index} onChange={() => setAnswers({ ...answers, [current]: index })} /><span className="option-letter">{String.fromCharCode(65 + index)}</span><strong>{option}</strong><span className="radio-mark"><Icon name="check" size={15} /></span></label>)}</div>
        </article>
        <div className="exam-actions"><Button variant="secondary" disabled={current === 0} onClick={() => setCurrent(current - 1)}><Icon name="back" /> Previous</Button><span>Answers save automatically on this device</span>{current === questions.length - 1 ? <Button onClick={() => setShowSubmit(true)}>Review & Submit</Button> : <Button icon="arrow" onClick={() => setCurrent(current + 1)}>Next question</Button>}</div>
      </section>
      <aside className="question-navigator">
        <div className="candidate-mini"><span>AO</span><div><strong>Amina Okeke</strong><small>BFA/2024/0187</small></div></div>
        <div className="navigator-head"><h2>Question navigator</h2><span>{Object.keys(answers).length}/{questions.length} answered</span></div>
        <div className="question-grid">{questions.map((_, index) => <button key={index} className={`${current === index ? 'current' : ''} ${answers[index] !== undefined ? 'answered' : ''} ${review.includes(index) ? 'review' : ''}`} onClick={() => setCurrent(index)}>{index + 1}</button>)}</div>
        <div className="legend"><span><i className="answered" /> Answered</span><span><i className="review" /> Review</span><span><i /> Not answered</span></div>
        <button className="submit-link" onClick={() => setShowSubmit(true)}><Icon name="submit" /> Submit examination</button>
      </aside>
    </div>
    {showSubmit && <div className="modal-backdrop"><section className="submit-modal" role="dialog" aria-modal="true" aria-labelledby="submit-title"><span className="modal-icon"><Icon name="submit" size={28} /></span><h2 id="submit-title">Submit your examination?</h2><p>You answered <strong>{Object.keys(answers).length} of {questions.length}</strong> questions. You still have {questions.length - Object.keys(answers).length} unanswered and {review.length} marked for review.</p><div className="submit-summary"><span><strong>{Object.keys(answers).length}</strong> Answered</span><span><strong>{questions.length - Object.keys(answers).length}</strong> Unanswered</span><span><strong>{review.length}</strong> Review</span></div><div className="modal-actions"><Button variant="secondary" onClick={() => setShowSubmit(false)}>Keep working</Button><Button onClick={() => navigate('/submission')}>Submit exam</Button></div></section></div>}
  </ExamLayout>
}
