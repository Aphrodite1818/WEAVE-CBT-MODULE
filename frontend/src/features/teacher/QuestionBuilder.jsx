import { useEffect, useMemo, useRef, useState } from 'react'
import { RiAddLine, RiArrowLeftLine, RiDeleteBin6Line, RiImageAddLine, RiSave3Line } from '@remixicon/react'
import { Notice, SelectControl, StatusBadge } from '../../shared/ui'
import '../student/student.css'
import './question-builder.css'

const MAX_IMAGE_SIZE = 5 * 1024 * 1024
const IMAGE_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp'])

function makeOption(seed = {}) {
  return {
    clientId: seed.clientId || `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    id: seed.id || null,
    text: seed.text || '',
    isCorrect: Boolean(seed.is_correct ?? seed.isCorrect),
    imageAssetId: seed.image_asset_id || seed.imageAssetId || null,
    imageFile: null,
    removeExistingImage: false,
  }
}

function initialOptions() {
  return [makeOption(), makeOption(), makeOption(), makeOption()]
}

export function QuestionBuilder({ mode = 'create', state, dispatch, teacherData, gateway }) {
  const editing = mode === 'edit'
  const questionId = state.staff.selectedQuestionId
  const initializedQuestionRef = useRef(null)
  const [bankId, setBankId] = useState(state.staff.selectedBankId || teacherData.banks[0]?.id || '')
  const [questionType, setQuestionType] = useState('single_choice')
  const [prompt, setPrompt] = useState('')
  const [instruction, setInstruction] = useState('')
  const [questionImageAssetId, setQuestionImageAssetId] = useState(null)
  const [questionImageFile, setQuestionImageFile] = useState(null)
  const [removeQuestionImage, setRemoveQuestionImage] = useState(false)
  const [options, setOptions] = useState(initialOptions)
  const [loading, setLoading] = useState(editing)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!bankId && teacherData.banks[0]) setBankId(teacherData.banks[0].id)
  }, [bankId, teacherData.banks])

  useEffect(() => {
    if (!editing || !questionId || initializedQuestionRef.current === questionId) return undefined
    let cancelled = false
    setLoading(true)
    setError('')
    gateway.questions.getQuestion(questionId)
      .then((question) => {
        if (cancelled) return
        initializedQuestionRef.current = questionId
        setBankId(question.bank_id)
        setQuestionType(question.question_type)
        setPrompt(question.prompt || '')
        setInstruction(question.instruction || '')
        setQuestionImageAssetId(question.image_asset_id || null)
        setQuestionImageFile(null)
        setRemoveQuestionImage(false)
        setOptions((question.options || []).map((option) => makeOption(option)))
      })
      .catch((requestError) => {
        if (!cancelled) setError(requestError.userMessage || 'Weave could not load this question for editing.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [editing, gateway, questionId])

  const selectedBank = teacherData.banks.find((bank) => bank.id === bankId)
  const bankOptions = teacherData.banks.map((bank) => ({
    value: bank.id,
    label: bank.name,
    description: `${bank.count || 0} questions`,
  }))
  const correctCount = options.filter((option) => option.isCorrect).length
  const validation = useMemo(() => validateDraft({ prompt, questionType, options }), [options, prompt, questionType])

  const updateOption = (clientId, patch) => {
    setOptions((current) => current.map((option) => option.clientId === clientId ? { ...option, ...patch } : option))
  }

  const markCorrect = (clientId) => {
    setOptions((current) => current.map((option) => {
      if (questionType === 'single_choice') return { ...option, isCorrect: option.clientId === clientId }
      if (option.clientId === clientId) return { ...option, isCorrect: !option.isCorrect }
      return option
    }))
  }

  const addOption = () => setOptions((current) => [...current, makeOption()])
  const removeOption = (clientId) => {
    if (options.length <= 2) return
    setOptions((current) => current.filter((option) => option.clientId !== clientId))
  }

  const onQuestionImage = (file) => {
    const issue = validateImage(file)
    if (issue) return setError(issue)
    setError('')
    setQuestionImageFile(file)
    setRemoveQuestionImage(false)
  }

  const onOptionImage = (clientId, file) => {
    const issue = validateImage(file)
    if (issue) return setError(issue)
    setError('')
    updateOption(clientId, { imageFile: file, removeExistingImage: false })
  }

  const leaveEditor = () => {
    dispatch({
      type: 'staff',
      patch: {
        section: 'questions',
        selectedBankId: bankId || state.staff.selectedBankId,
        selectedQuestionId: null,
        editingQuestion: null,
      },
    })
  }

  const resetForAnother = () => {
    setPrompt('')
    setInstruction('')
    setQuestionImageAssetId(null)
    setQuestionImageFile(null)
    setRemoveQuestionImage(false)
    setOptions(initialOptions())
    setError('')
  }

  const save = async ({ createAnother = false } = {}) => {
    setError('')
    if (validation) return setError(validation)
    if (!bankId) return setError('Choose a question bank before saving.')

    setSaving(true)
    try {
      let nextQuestionImageId = questionImageAssetId
      if (questionImageFile) {
        const uploaded = await gateway.media.uploadQuestionImage(questionImageFile)
        nextQuestionImageId = uploaded.id
      } else if (removeQuestionImage) {
        nextQuestionImageId = null
      }

      const optionPayloads = []
      for (const option of options) {
        let imageAssetId = option.imageAssetId
        if (option.imageFile) {
          const uploaded = await gateway.media.uploadQuestionImage(option.imageFile)
          imageAssetId = uploaded.id
        } else if (option.removeExistingImage) {
          imageAssetId = null
        }
        optionPayloads.push({
          text: option.text.trim() || null,
          image_asset_id: imageAssetId || null,
          is_correct: option.isCorrect,
        })
      }

      const payload = {
        prompt: prompt.trim(),
        instruction: instruction.trim() || null,
        options: optionPayloads,
      }

      if (editing) {
        if (questionImageFile || removeQuestionImage) payload.image_asset_id = nextQuestionImageId
        await gateway.questions.updateQuestion(questionId, payload)
      } else {
        payload.image_asset_id = nextQuestionImageId || null
        if (questionType === 'multiple_choice') await gateway.questions.createMultipleChoiceQuestion(bankId, payload)
        else await gateway.questions.createSingleChoiceQuestion(bankId, payload)
      }

      await teacherData.refresh()
      if (!editing && createAnother) {
        resetForAnother()
        return
      }
      leaveEditor()
    } catch (requestError) {
      setError(requestError.userMessage || `Weave could not ${editing ? 'update' : 'create'} this question.`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="question-builder-page">
      <header className="question-builder-header">
        <div>
          <button className="question-builder-back" type="button" onClick={leaveEditor}><RiArrowLeftLine size={17} /> Questions</button>
          <h1>{editing ? 'Edit Question' : 'Create Question'}</h1>
          <p>{editing ? 'Update the source question while preserving exam-safe media references.' : 'Author the question and preview exactly how the unsaved content will be presented to a student.'}</p>
        </div>
        <div className="question-builder-header__actions">
          <button className="teacher-secondary-action" type="button" disabled={saving} onClick={leaveEditor}>Cancel</button>
          <button className="teacher-primary-action" type="button" disabled={saving || loading} onClick={() => save({ createAnother: false })}>
            <RiSave3Line size={18} /> {saving ? 'Saving…' : 'Save & close'}
          </button>
          {!editing && (
            <button className="teacher-secondary-action question-builder-create-another" type="button" disabled={saving || loading} onClick={() => save({ createAnother: true })}>
              <RiAddLine size={18} /> Create another
            </button>
          )}
        </div>
      </header>

      {error && <Notice tone="danger">{error}</Notice>}
      {loading ? <div className="question-builder-loading">Loading question…</div> : (
        <div className="question-builder-grid">
          <div className="question-builder-editor">
            <section className="question-builder-card">
              <div className="question-builder-card__heading"><div><span>01</span><h2>Question setup</h2></div><p>Choose the bank and response model.</p></div>
              <div className="question-builder-fields">
                <div className="question-builder-field">
                  <span>Question bank</span>
                  <SelectControl label="Question bank" value={bankId} options={bankOptions} onChange={setBankId} disabled={editing} placeholder="Choose a bank" />
                </div>
                <div className="question-builder-field">
                  <span>Answer type</span>
                  <div className="question-type-switch" role="group" aria-label="Answer type">
                    <button type="button" disabled={editing} className={questionType === 'single_choice' ? 'active' : ''} onClick={() => setQuestionType('single_choice')}>Single choice</button>
                    <button type="button" disabled={editing} className={questionType === 'multiple_choice' ? 'active' : ''} onClick={() => setQuestionType('multiple_choice')}>Multiple choice</button>
                  </div>
                  {editing && <small>Question type is fixed after creation.</small>}
                </div>
              </div>
            </section>

            <section className="question-builder-card">
              <div className="question-builder-card__heading"><div><span>02</span><h2>Question content</h2></div><p>Images are optional and normalized by the local CBT server.</p></div>
              <label className="question-builder-field question-builder-field--wide"><span>Question prompt</span><textarea rows="5" value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Write the question exactly as students should see it." /></label>
              <label className="question-builder-field question-builder-field--wide"><span>Instruction <small>(optional)</small></span><input value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="e.g. Select the most appropriate answer." /></label>
              <MediaPicker
                label="Question image"
                file={questionImageFile}
                existing={Boolean(questionImageAssetId && !removeQuestionImage)}
                existingPreview={questionImageAssetId && !removeQuestionImage ? <QuestionMedia gateway={gateway} questionId={questionId} alt="Current question" /> : null}
                onFile={onQuestionImage}
                onRemove={() => { setQuestionImageFile(null); setRemoveQuestionImage(Boolean(questionImageAssetId)) }}
              />
            </section>

            <section className="question-builder-card">
              <div className="question-builder-card__heading"><div><span>03</span><h2>Answer options</h2></div><p>{questionType === 'single_choice' ? 'Mark exactly one correct answer.' : 'Mark at least two correct answers and leave at least one incorrect.'}</p></div>
              <div className="question-option-stack">
                {options.map((option, index) => (
                  <article className={`question-option-editor ${option.isCorrect ? 'is-correct' : ''}`} key={option.clientId}>
                    <button className="question-option-correct" type="button" onClick={() => markCorrect(option.clientId)} aria-pressed={option.isCorrect}>
                      <span>{option.isCorrect ? '✓' : optionLetter(index)}</span><strong>{option.isCorrect ? 'Correct answer' : `Option ${optionLetter(index)}`}</strong>
                    </button>
                    <div className="question-option-editor__body">
                      <input value={option.text} onChange={(event) => updateOption(option.clientId, { text: event.target.value })} placeholder="Answer text (optional when an image is attached)" />
                      <div className="question-option-media-row">
                        <label className="question-option-image-button"><RiImageAddLine size={17} /> {option.imageFile || (option.imageAssetId && !option.removeExistingImage) ? 'Replace image' : 'Add image'}<input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => event.target.files?.[0] && onOptionImage(option.clientId, event.target.files[0])} /></label>
                        {(option.imageFile || (option.imageAssetId && !option.removeExistingImage)) && <button type="button" className="text-button" onClick={() => updateOption(option.clientId, { imageFile: null, removeExistingImage: Boolean(option.imageAssetId) })}>Remove image</button>}
                        <button type="button" className="question-option-delete" disabled={options.length <= 2} onClick={() => removeOption(option.clientId)} aria-label={`Remove option ${optionLetter(index)}`}><RiDeleteBin6Line size={17} /></button>
                      </div>
                      {(option.imageFile || (option.imageAssetId && !option.removeExistingImage)) && (
                        <div className="question-option-thumbnail">
                          {option.imageFile ? <LocalImage file={option.imageFile} alt={`Option ${optionLetter(index)}`} /> : <QuestionMedia gateway={gateway} questionId={questionId} optionId={option.id} alt={`Option ${optionLetter(index)}`} />}
                        </div>
                      )}
                    </div>
                  </article>
                ))}
              </div>
              <button className="question-builder-add-option" type="button" onClick={addOption}><RiAddLine size={18} /> Add answer option</button>
              <div className="question-builder-rule"><strong>{correctCount}</strong><span>option{correctCount === 1 ? '' : 's'} marked correct</span></div>
            </section>
          </div>

          <aside className="question-preview-card" aria-label="Student question preview">
            <div className="question-preview-card__heading"><div><span>Student preview</span><StatusBadge tone="info">Unsaved preview</StatusBadge></div><small>{selectedBank?.name || 'Question bank'}</small></div>
            <div className="premium-exam-content question-builder-student-preview">
              <div className="premium-question-header"><h2>Question 1 of 1</h2><label className="premium-mark-review"><input type="checkbox" disabled /> Mark for review</label></div>
              {instruction.trim() && <p className="question-preview-instruction">{instruction}</p>}
              <div className="premium-question-prompt">{prompt.trim() || 'Your question will appear here as you type.'}</div>
              {(questionImageFile || (questionImageAssetId && !removeQuestionImage)) && (
                <div className="premium-question-media">{questionImageFile ? <LocalImage file={questionImageFile} alt="Question preview" /> : <QuestionMedia gateway={gateway} questionId={questionId} alt="Question preview" />}</div>
              )}
              <div className="premium-options-list">
                {options.map((option, index) => (
                  <div className="premium-option" key={option.clientId}>
                    <div className="premium-option-letter">{optionLetter(index)}</div>
                    <div className="premium-option-content">
                      {option.text.trim() && <div className="premium-option-text">{option.text}</div>}
                      {(option.imageFile || (option.imageAssetId && !option.removeExistingImage)) && (
                        <div className="premium-option-media">{option.imageFile ? <LocalImage file={option.imageFile} alt={`Option ${optionLetter(index)}`} /> : <QuestionMedia gateway={gateway} questionId={questionId} optionId={option.id} alt={`Option ${optionLetter(index)}`} />}</div>
                      )}
                      {!option.text.trim() && !option.imageFile && !(option.imageAssetId && !option.removeExistingImage) && <div className="premium-option-text question-preview-placeholder">Add answer text or an image</div>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <footer><span>{questionType === 'single_choice' ? 'Single choice' : 'Multiple choice'}</span><span>{options.length} options</span></footer>
          </aside>
        </div>
      )}
    </div>
  )
}

function validateDraft({ prompt, questionType, options }) {
  if (!prompt.trim()) return 'Write the question prompt before saving.'
  if (options.length < 2) return 'A question must have at least two answer options.'
  if (options.some((option) => !option.text.trim() && !option.imageFile && !(option.imageAssetId && !option.removeExistingImage))) return 'Every answer option needs text, an image, or both.'
  const correctCount = options.filter((option) => option.isCorrect).length
  if (questionType === 'single_choice' && correctCount !== 1) return 'Single-choice questions require exactly one correct answer.'
  if (questionType === 'multiple_choice' && correctCount < 2) return 'Multiple-choice questions require at least two correct answers.'
  if (questionType === 'multiple_choice' && correctCount === options.length) return 'Multiple-choice questions need at least one incorrect answer.'
  const textOptions = options.map((option) => option.text.trim().toLowerCase()).filter(Boolean)
  if (new Set(textOptions).size !== textOptions.length) return 'Answer text must be unique within the question.'
  return ''
}

function validateImage(file) {
  if (!file) return ''
  if (!IMAGE_TYPES.has(file.type)) return 'Use a JPEG, PNG, or WebP image.'
  if (file.size > MAX_IMAGE_SIZE) return 'Images must be 5 MB or smaller.'
  return ''
}

function MediaPicker({ label, file, existing, existingPreview, onFile, onRemove }) {
  return (
    <div className="question-media-picker">
      <div><strong>{label}</strong><small>JPEG, PNG or WebP · up to 5 MB</small></div>
      {(file || existing) && <div className="question-media-picker__preview">{file ? <LocalImage file={file} alt={label} /> : existingPreview}</div>}
      <div className="question-media-picker__actions">
        <label><RiImageAddLine size={18} /> {file || existing ? 'Replace image' : 'Attach image'}<input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => event.target.files?.[0] && onFile(event.target.files[0])} /></label>
        {(file || existing) && <button type="button" onClick={onRemove}>Remove</button>}
      </div>
    </div>
  )
}

function LocalImage({ file, alt }) {
  const [url, setUrl] = useState('')
  useEffect(() => {
    const next = URL.createObjectURL(file)
    setUrl(next)
    return () => URL.revokeObjectURL(next)
  }, [file])
  return url ? <img src={url} alt={alt} /> : null
}

function QuestionMedia({ gateway, questionId, optionId, alt }) {
  const [url, setUrl] = useState('')
  useEffect(() => {
    if (!questionId || optionId === null) return undefined
    let cancelled = false
    let objectUrl = ''
    const request = optionId
      ? gateway.questions.getQuestionOptionImage(questionId, optionId)
      : gateway.questions.getQuestionImage(questionId)
    request.then((blob) => {
      if (cancelled) return
      objectUrl = URL.createObjectURL(blob)
      setUrl(objectUrl)
    }).catch(() => null)
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [gateway, optionId, questionId])
  return url ? <img src={url} alt={alt} /> : <span className="question-media-loading">Loading image…</span>
}

function optionLetter(index) {
  return String.fromCharCode(65 + (index % 26))
}
