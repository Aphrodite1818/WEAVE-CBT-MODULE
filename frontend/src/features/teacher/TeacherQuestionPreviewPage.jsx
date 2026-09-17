import { useEffect, useMemo, useState } from 'react'
import { RiArrowLeftLine } from '@remixicon/react'
import { Notice } from '../../shared/ui'
import { QuestionPreview } from './QuestionBuilder'
import './question-builder.css'

export function TeacherQuestionPreviewPage({ state, dispatch, teacherData, gateway }) {
  const questionId = state.staff.selectedQuestionId
  const [question, setQuestion] = useState(null)
  const [loading, setLoading] = useState(Boolean(questionId))
  const [error, setError] = useState('')

  useEffect(() => {
    if (!questionId) {
      setLoading(false)
      setError('Choose a question to preview it.')
      return undefined
    }
    let cancelled = false
    setLoading(true)
    setError('')
    gateway.questions.getQuestion(questionId)
      .then((loadedQuestion) => {
        if (!cancelled) setQuestion(loadedQuestion)
      })
      .catch((requestError) => {
        if (!cancelled) setError(requestError.userMessage || 'Weave could not load this question preview.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [gateway, questionId])

  const options = useMemo(() => (question?.options || []).map((option, index) => ({
    clientId: option.id || `preview-option-${index}`,
    id: option.id || null,
    text: option.text || '',
    isCorrect: Boolean(option.is_correct),
    imageAssetId: option.image_asset_id || null,
    imageFile: null,
    removeExistingImage: false,
  })), [question])

  const selectedBank = teacherData.banks.find((bank) => bank.id === question?.bank_id)
  const returnToBank = state.staff.questionPreviewOrigin === 'bank-detail'
  const returnSection = returnToBank ? 'bank-detail' : 'questions'
  const returnLabel = returnToBank ? `Back to ${selectedBank?.name || 'question bank'}` : 'Back to questions'
  const leavePreview = () => dispatch({
    type: 'staff',
    patch: {
      section: returnSection,
      selectedBankId: question?.bank_id || state.staff.selectedBankId,
      selectedQuestionId: null,
      editingQuestion: null,
      questionPreviewOrigin: null,
    },
  })

  return (
    <div className="question-builder-page question-preview-page">
      <header className="question-preview-page__header">
        <div><h1>Question preview</h1><p>Review exactly how this saved question appears to students.</p></div>
        <button className="question-preview-back" type="button" onClick={leavePreview}><RiArrowLeftLine size={19} /> {returnLabel}</button>
      </header>
      {error && <Notice tone="danger">{error}</Notice>}
      {loading && <div className="question-builder-loading">Loading question preview…</div>}
      {!loading && question && (
        <QuestionPreview
          gateway={gateway}
          questionId={question.id}
          selectedBank={selectedBank}
          questionType={question.question_type}
          prompt={question.prompt || ''}
          instruction={question.instruction || ''}
          questionImageFile={null}
          questionImageAssetId={question.image_asset_id || null}
          removeQuestionImage={false}
          options={options}
          previewLabel="Saved question"
          previewTone="success"
        />
      )}
    </div>
  )
}
