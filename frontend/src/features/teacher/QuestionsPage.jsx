import { useEffect, useMemo, useRef, useState } from 'react'
import { RiArchiveLine, RiCloseLine, RiEditLine, RiImageAddLine, RiMore2Line, RiRefreshLine, RiSearchLine } from '@remixicon/react'
import { Icon } from '../../shared/icons/Icon'
import { Notice, PageTitle, Panel, SegmentedControl, StatusBadge } from '../../shared/ui'

const MAX_QUESTION_IMAGE_SIZE = 5 * 1024 * 1024
const QUESTION_IMAGE_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp'])
const PAGE_SIZE = 10

export function QuestionsPage({ dispatch, teacherData, gateway }) {
  const [query, setQuery] = useState('')
  const [bankId, setBankId] = useState('all')
  const [tab, setTab] = useState('all')
  const [page, setPage] = useState(1)
  const [lifecycleQuestionId, setLifecycleQuestionId] = useState(null)
  const [lifecycleBusyId, setLifecycleBusyId] = useState(null)
  const [lifecycleError, setLifecycleError] = useState('')
  const lifecycleRef = useRef(null)

  const counts = useMemo(() => ({
    all: teacherData.questions.length,
    single: teacherData.questions.filter((question) => question.type === 'Single choice').length,
    multiple: teacherData.questions.filter((question) => question.type === 'Multiple choice').length,
    archived: teacherData.questions.filter((question) => question.status === 'Archived').length,
  }), [teacherData.questions])

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return teacherData.questions.filter((question) => {
      if (bankId !== 'all' && question.bankId !== bankId) return false
      if (tab === 'single' && question.type !== 'Single choice') return false
      if (tab === 'multiple' && question.type !== 'Multiple choice') return false
      if (tab === 'archived' && question.status !== 'Archived') return false
      if (tab !== 'archived' && tab !== 'all' && question.status === 'Archived') return false
      if (!needle) return true
      return `${question.prompt} ${question.bankName} ${question.type}`.toLowerCase().includes(needle)
    })
  }, [bankId, query, tab, teacherData.questions])

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const visibleQuestions = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  useEffect(() => {
    if (page > pageCount) setPage(pageCount)
  }, [page, pageCount])

  useEffect(() => {
    if (!lifecycleQuestionId) return undefined

    const closeOnOutsideClick = (event) => {
      if (!lifecycleRef.current?.contains(event.target)) setLifecycleQuestionId(null)
    }
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') setLifecycleQuestionId(null)
    }

    document.addEventListener('pointerdown', closeOnOutsideClick)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('pointerdown', closeOnOutsideClick)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [lifecycleQuestionId])

  const changeFilter = (setter) => (eventOrValue) => {
    const value = eventOrValue?.target ? eventOrValue.target.value : eventOrValue
    setter(value)
    setPage(1)
  }

  const changeLifecycle = async (question) => {
    setLifecycleError('')
    setLifecycleBusyId(question.id)
    try {
      if (question.status === 'Archived') await gateway.questions.reactivateQuestion(question.id)
      else await gateway.questions.archiveQuestion(question.id)
      await teacherData.refresh()
      setLifecycleQuestionId(null)
    } catch (error) {
      setLifecycleError(error.userMessage || `Weave could not ${question.status === 'Archived' ? 'reactivate' : 'archive'} this question.`)
    } finally {
      setLifecycleBusyId(null)
    }
  }

  return (
    <div className="teacher-reference-page">
      <div className="teacher-page-heading">
        <div>
          <h1>Questions</h1>
          <p>Browse and author questions inside the banks available to your current teaching scope.</p>
        </div>
        <button
          className="teacher-primary-action"
          type="button"
          disabled={teacherData.banks.length === 0}
          onClick={() => dispatch({ type: 'staff', patch: { section: 'create-question', selectedBankId: teacherData.banks[0]?.id } })}
        >
          <Icon name="plus" size={17} /> Add Question
        </button>
      </div>

      {teacherData.error && <Notice tone="danger">{teacherData.error}</Notice>}
      {lifecycleError && <Notice tone="danger">{lifecycleError}</Notice>}

      <div className="teacher-question-toolbar">
        <select aria-label="Question bank filter" value={bankId} onChange={changeFilter(setBankId)}>
          <option value="all">All question banks</option>
          {teacherData.banks.map((bank) => <option key={bank.id} value={bank.id}>{bank.name}</option>)}
        </select>
        <label className="teacher-search-control teacher-search-control--grow">
          <RiSearchLine size={17} aria-hidden="true" />
          <input aria-label="Search questions" type="search" value={query} onChange={changeFilter(setQuery)} placeholder="Search questions..." />
        </label>
      </div>

      <nav className="teacher-tab-row" aria-label="Question filters">
        <TabButton label="All" value="all" current={tab} count={counts.all} onClick={changeFilter(setTab)} />
        <TabButton label="Single Choice" value="single" current={tab} count={counts.single} onClick={changeFilter(setTab)} />
        <TabButton label="Multiple Choice" value="multiple" current={tab} count={counts.multiple} onClick={changeFilter(setTab)} />
        <TabButton label="Archived" value="archived" current={tab} count={counts.archived} onClick={changeFilter(setTab)} />
      </nav>

      <section className="teacher-question-catalog" aria-busy={teacherData.loading} aria-label="Questions">
        <div className="teacher-question-catalog__header" aria-hidden="true">
          <span>Question</span>
          <span>Bank</span>
          <span>Type</span>
          <span>Status</span>
          <span>Version</span>
          <span>Actions</span>
        </div>

        {visibleQuestions.map((question, index) => (
          <article className="teacher-question-catalog__row" key={question.id}>
            <span className="teacher-question-catalog__number">{(page - 1) * PAGE_SIZE + index + 1}</span>
            <div className="teacher-question-catalog__prompt">
              <strong>{question.prompt}</strong>
              {question.image && <small>Includes an image</small>}
            </div>
            <span className="teacher-question-catalog__bank">{question.bankName}</span>
            <span className="teacher-type-pill">{question.type}</span>
            <StatusBadge tone={question.status === 'Ready' ? 'success' : 'warning'}>{question.status}</StatusBadge>
            <span className="teacher-question-catalog__version">{question.updated}</span>
            <div className="teacher-question-catalog__actions">
              <button
                type="button"
                className="teacher-question-edit"
                disabled={question.status === 'Archived'}
                title={question.status === 'Archived' ? 'Reactivate this question before editing it.' : undefined}
                onClick={() => dispatch({ type: 'staff', patch: { section: 'edit-question', selectedBankId: question.bankId, selectedQuestionId: question.id } })}
              >
                <RiEditLine size={16} aria-hidden="true" /> Edit
              </button>
              <div ref={lifecycleQuestionId === question.id ? lifecycleRef : undefined} className="teacher-question-lifecycle">
                <button
                  type="button"
                  className="teacher-question-lifecycle__trigger"
                  aria-label={`Question lifecycle for ${question.prompt}`}
                  aria-expanded={lifecycleQuestionId === question.id}
                  onClick={() => setLifecycleQuestionId((current) => current === question.id ? null : question.id)}
                >
                  <RiMore2Line size={19} aria-hidden="true" />
                </button>
                {lifecycleQuestionId === question.id && (
                  <div className="teacher-question-lifecycle__card" role="dialog" aria-label={`Lifecycle for ${question.prompt}`}>
                    <div>
                      <strong>Question lifecycle</strong>
                      <p>{question.status === 'Archived' ? 'Reactivate this question to make it available for authoring again.' : 'Archive this question to remove it from active authoring without deleting its history.'}</p>
                    </div>
                    <button type="button" disabled={lifecycleBusyId === question.id} onClick={() => changeLifecycle(question)}>
                      {question.status === 'Archived' ? <RiRefreshLine size={17} aria-hidden="true" /> : <RiArchiveLine size={17} aria-hidden="true" />}
                      {lifecycleBusyId === question.id ? 'Updating…' : question.status === 'Archived' ? 'Reactivate question' : 'Archive question'}
                    </button>
                  </div>
                )}
              </div>
            </div>
          </article>
        ))}

        {!teacherData.loading && visibleQuestions.length === 0 && <div className="teacher-question-catalog__empty">No questions match the current filters.</div>}
        {teacherData.loading && <div className="teacher-question-catalog__empty">Loading questions…</div>}

        <div className="teacher-table-footer">
          <span>{filtered.length === 0 ? '0 questions' : `Showing ${(page - 1) * PAGE_SIZE + 1}–${Math.min(page * PAGE_SIZE, filtered.length)} of ${filtered.length} questions`}</span>
          <div>
            <button type="button" disabled={page === 1} onClick={() => setPage((current) => current - 1)} aria-label="Previous page">‹</button>
            <span>{page} / {pageCount}</span>
            <button type="button" disabled={page === pageCount} onClick={() => setPage((current) => current + 1)} aria-label="Next page">›</button>
          </div>
        </div>
      </section>
    </div>
  )
}

function TabButton({ label, value, current, count, onClick }) {
  return <button type="button" className={current === value ? 'active' : ''} onClick={() => onClick(value)}>{label} <span>{count}</span></button>
}

export function CreateQuestionPage({ state, dispatch, teacherData, gateway }) {
  const selectedQuestion = teacherData.questions?.find((question) => question.id === state.staff.selectedQuestionId)
  const isEditing = state.staff.section === 'edit-question'
  const selectedBankId = selectedQuestion?.bankId || state.staff.selectedBankId
  const selectedBank = teacherData.banks.find((bank) => bank.id === selectedBankId) || teacherData.banks[0]
  const [bankId, setBankId] = useState(selectedBank?.id || '')
  const [type, setType] = useState(selectedQuestion?.type === 'Multiple choice' ? 'multiple' : 'single')
  const initialOptions = selectedQuestion?.options?.length
    ? selectedQuestion.options.map((option, index) => [String.fromCharCode(65 + index), option.text])
    : [['A', ''], ['B', ''], ['C', ''], ['D', '']]
  const [correct, setCorrect] = useState(() => selectedQuestion?.options?.length
    ? selectedQuestion.options.flatMap((option, index) => option.is_correct ? [String.fromCharCode(65 + index)] : [])
    : ['A'])
  const [prompt, setPrompt] = useState(selectedQuestion?.prompt || '')
  const [instruction, setInstruction] = useState(selectedQuestion?.instruction || '')
  const [options, setOptions] = useState(initialOptions)
  const [imageFile, setImageFile] = useState(null)
  const [imagePreviewUrl, setImagePreviewUrl] = useState('')
  const [removeExistingImage, setRemoveExistingImage] = useState(false)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveStage, setSaveStage] = useState('')
  const imageInputRef = useRef(null)

  useEffect(() => {
    if (!imageFile || typeof URL.createObjectURL !== 'function') {
      setImagePreviewUrl('')
      return undefined
    }
    const objectUrl = URL.createObjectURL(imageFile)
    setImagePreviewUrl(objectUrl)
    return () => URL.revokeObjectURL(objectUrl)
  }, [imageFile])

  const toggleCorrect = (id) => {
    setCorrect((current) => type === 'single' ? [id] : current.includes(id) ? current.filter((item) => item !== id) : [...current, id])
  }

  const selectImage = (event) => {
    const file = event.target.files?.[0]
    setError('')
    if (!file) return
    if (!QUESTION_IMAGE_TYPES.has(file.type)) {
      setImageFile(null)
      setError('Choose a PNG, JPEG, or WebP image.')
      event.target.value = ''
      return
    }
    if (file.size > MAX_QUESTION_IMAGE_SIZE) {
      setImageFile(null)
      setError('Question images must be 5 MB or smaller.')
      event.target.value = ''
      return
    }
    setImageFile(file)
  }

  const removeImage = () => {
    setImageFile(null)
    if (imageInputRef.current) imageInputRef.current.value = ''
  }

  const saveQuestion = async () => {
    setError('')
    if (!bankId) { setError('Select a question bank.'); return }
    if (!prompt.trim()) { setError('Question prompt is required.'); return }
    const payload = {
      prompt,
      instruction: instruction || null,
      options: options.filter(([, text]) => text.trim()).map(([id, text]) => ({ text, is_correct: correct.includes(id) })),
    }
    if (payload.options.length < 2) { setError('At least two options are required.'); return }

    setSaving(true)
    try {
      if (imageFile) {
        setSaveStage('Uploading image…')
        const asset = await gateway.media.uploadQuestionImage(imageFile)
        payload.image_asset_id = asset.id
      } else if (isEditing && selectedQuestion.image && removeExistingImage) {
        payload.image_asset_id = null
      }
      setSaveStage('Saving question…')
      if (isEditing) await gateway.questions.updateQuestion(selectedQuestion.id, payload)
      else if (type === 'single') await gateway.questions.createSingleChoiceQuestion(bankId, payload)
      else await gateway.questions.createMultipleChoiceQuestion(bankId, payload)
      await teacherData.refresh()
      dispatch({ type: 'staff', patch: isEditing ? { section: 'questions', selectedQuestionId: null } : { section: 'bank-detail', selectedBankId: bankId } })
    } catch (error) {
      setError(error.userMessage || 'Weave could not save this question.')
    } finally {
      setSaving(false)
      setSaveStage('')
    }
  }

  if (!selectedBank || (isEditing && !selectedQuestion)) {
    return <><PageTitle title="Create Question" subtitle="No authorable bank is available." /><Notice tone="warning">The backend did not return any question bank you can author into.</Notice></>
  }

  return (
    <div className="teacher-reference-page">
      <div className="teacher-page-head">
        <div><button className="text-button" onClick={() => dispatch({ type: 'staff', patch: { section: 'questions', selectedQuestionId: null } })}>Back to questions</button><PageTitle title={isEditing ? 'Edit Question' : 'Create Question'} subtitle={isEditing ? 'Update this question. Saving a change creates its next version.' : 'Save directly to the selected backend question bank.'} /></div>
        <div className="toolbar"><button className="button button--primary" disabled={saving} onClick={saveQuestion}>{saving ? saveStage || 'Saving…' : isEditing ? 'Save Changes' : 'Save Question'}</button></div>
      </div>
      {error && <Notice tone="danger">{error}</Notice>}
      <div className="authoring-grid">
        <Panel title="Question content">
          <label className="field-stack"><span>Question Bank</span><select aria-label="Question Bank" value={bankId} disabled={isEditing} onChange={(event) => setBankId(event.target.value)}>{teacherData.banks.map((bank) => <option key={bank.id} value={bank.id}>{bank.name}</option>)}</select></label>
          <label className="field-stack"><span>Prompt</span><textarea aria-label="Question prompt" value={prompt} onChange={(event) => setPrompt(event.target.value)} /></label>
          <label className="field-stack"><span>Instruction</span><textarea aria-label="Question instruction" value={instruction} onChange={(event) => setInstruction(event.target.value)} /></label>
          <div className="field-stack">
            <span>Question image <small>(optional)</small></span>
            <div className="upload-zone question-image-upload">
              {imagePreviewUrl ? <img src={imagePreviewUrl} alt="Selected question" /> : <span className="question-image-placeholder"><RiImageAddLine size={30} aria-hidden="true" /></span>}
              <div className="question-image-upload__copy">
                <strong>{imageFile ? imageFile.name : isEditing && selectedQuestion.image && !removeExistingImage ? 'Current question image' : 'Add a diagram or reference image'}</strong>
                <p>{imageFile ? formatFileSize(imageFile.size) : isEditing && selectedQuestion.image && !removeExistingImage ? 'Choose a new image to replace it, or remove it.' : 'PNG, JPEG, or WebP. Maximum 5 MB.'}</p>
                <div className="toolbar">
                  <label className="button button--secondary" htmlFor="question-image-upload">{imageFile ? 'Replace image' : 'Choose image'}</label>
                  {imageFile && <button className="button button--ghost" type="button" onClick={removeImage}><RiCloseLine size={16} /> Remove</button>}
                  {!imageFile && isEditing && selectedQuestion.image && !removeExistingImage && <button className="button button--ghost" type="button" onClick={() => setRemoveExistingImage(true)}><RiCloseLine size={16} /> Remove current image</button>}
                </div>
                <input ref={imageInputRef} id="question-image-upload" className="question-image-input" type="file" accept="image/png,image/jpeg,image/webp" onChange={selectImage} />
              </div>
            </div>
          </div>
        </Panel>
        <Panel title="Question settings">
          <SegmentedControl label="Question Type" value={type} options={[['single', 'Single Choice'], ['multiple', 'Multiple Choice']]} onChange={setType} />
          <div className="answer-options">
            {options.map(([id, text], index) => (
              <label key={id} className="answer-option-row">
                <input type={type === 'single' ? 'radio' : 'checkbox'} checked={correct.includes(id)} onChange={() => toggleCorrect(id)} />
                <span>{id}</span>
                <input aria-label={`Option ${id}`} value={text} onChange={(event) => setOptions((current) => current.map((item, itemIndex) => itemIndex === index ? [id, event.target.value] : item))} />
                <button type="button" aria-label={`Delete option ${id}`} onClick={() => setOptions((current) => current.filter((item) => item[0] !== id))}><Icon name="trash" size={16} /></button>
              </label>
            ))}
            <button className="button button--secondary" onClick={() => setOptions((current) => [...current, [String.fromCharCode(65 + current.length), '']])}><Icon name="plus" size={16} /> Add Option</button>
          </div>
          <Notice tone="success">{type === 'single' ? 'Exactly one answer may be correct.' : 'More than one answer may be marked correct.'}</Notice>
        </Panel>
      </div>
    </div>
  )
}

function formatFileSize(size) {
  if (size < 1024) return `${size} bytes`
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}
