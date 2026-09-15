import { Icon } from '../../shared/icons/Icon'
import { StatusBadge } from '../../shared/ui'

export function BankIcon({ name }) {
  const iconName = name === 'flask' ? 'flask' : name === 'math' ? 'math' : name === 'weave' ? 'weaveIcon' : 'book'
  return <span className={`bank-icon bank-icon--${name}`}><Icon name={iconName} size={34} /></span>
}

export function QuestionRows({ questions, banks }) {
  if (!questions.length) return <p>No questions yet. Add the first question for this bank.</p>

  return (
    <div className="question-list">
      {questions.map((question) => {
        const bank = banks.find((item) => item.id === question.bankId)
        return (
          <div className="question-row" key={question.id}>
            <Icon name="questions" size={18} />
            <span><strong>{question.prompt}</strong><small>{bank?.name} - {question.type} - {question.updated}</small></span>
            {question.image && <StatusBadge>Image</StatusBadge>}
            <StatusBadge tone={question.status === 'Ready' ? 'success' : 'warning'}>{question.status}</StatusBadge>
          </div>
        )
      })}
    </div>
  )
}
