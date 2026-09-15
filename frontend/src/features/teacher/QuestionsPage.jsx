import { useState } from 'react'
import { Icon } from '../../shared/icons/Icon'
import { FilterBar, Notice, PageTitle, Panel, SearchField, SegmentedControl } from '../../shared/ui'
import { QuestionRows } from './components'

export function QuestionsPage({ dispatch, teacherData }) {
  return (
    <>
      <div className="teacher-page-head">
        <PageTitle title="Questions" subtitle="Browse questions from backend-authorized banks." />
        <button className="button button--primary" disabled={teacherData.banks.length === 0} onClick={() => dispatch({ type: 'staff', patch: { section: 'create-question', selectedBankId: teacherData.banks[0]?.id } })}>
          <Icon name="plus" size={17} /> Create Question
        </button>
      </div>
      {teacherData.error && <Notice tone="danger">{teacherData.error}</Notice>}
      <FilterBar>
        <SearchField label="Search questions" placeholder="Search loaded questions..." />
        <select aria-label="Question bank filter"><option>All loaded question banks</option>{teacherData.banks.map((bank) => <option key={bank.id}>{bank.name}</option>)}</select>
        <button className="button button--secondary" onClick={teacherData.refresh}>Refresh</button>
      </FilterBar>
      <Panel title="Question Library">{teacherData.loading ? <p>Loading questions...</p> : <QuestionRows questions={teacherData.questions} banks={teacherData.banks} />}</Panel>
    </>
  )
}

export function CreateQuestionPage({ state, dispatch, teacherData, gateway }) {
  const selectedBank = teacherData.banks.find((bank) => bank.id === state.staff.selectedBankId) || teacherData.banks[0]
  const [bankId, setBankId] = useState(selectedBank?.id || '')
  const [type, setType] = useState('single')
  const [correct, setCorrect] = useState(['A'])
  const [prompt, setPrompt] = useState('')
  const [instruction, setInstruction] = useState('')
  const [options, setOptions] = useState([['A', ''], ['B', ''], ['C', ''], ['D', '']])
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const toggleCorrect = (id) => {
    setCorrect((current) => type === 'single' ? [id] : current.includes(id) ? current.filter((item) => item !== id) : [...current, id])
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
      if (type === 'single') await gateway.questions.createSingleChoiceQuestion(bankId, payload)
      else await gateway.questions.createMultipleChoiceQuestion(bankId, payload)
      await teacherData.refresh()
      dispatch({ type: 'staff', patch: { section: 'bank-detail', selectedBankId: bankId } })
    } catch (error) {
      setError(error.userMessage || 'Weave could not save this question.')
    } finally {
      setSaving(false)
    }
  }

  if (!selectedBank) {
    return <><PageTitle title="Create Question" subtitle="No authorable bank is available." /><Notice tone="warning">The backend did not return any question bank you can author into.</Notice></>
  }

  return (
    <>
      <div className="teacher-page-head">
        <div><button className="text-button" onClick={() => dispatch({ type: 'staff', patch: { section: 'questions' } })}>Back to questions</button><PageTitle title="Create Question" subtitle="Save directly to the selected backend question bank." /></div>
        <div className="toolbar"><button className="button button--primary" disabled={saving} onClick={saveQuestion}>{saving ? 'Saving...' : 'Save Question'}</button></div>
      </div>
      {error && <Notice tone="danger">{error}</Notice>}
      <div className="authoring-grid">
        <Panel title="Question content">
          <label className="field-stack"><span>Question Bank</span><select aria-label="Question Bank" value={bankId} onChange={(event) => setBankId(event.target.value)}>{teacherData.banks.map((bank) => <option key={bank.id} value={bank.id}>{bank.name}</option>)}</select></label>
          <label className="field-stack"><span>Prompt</span><textarea aria-label="Question prompt" value={prompt} onChange={(event) => setPrompt(event.target.value)} /></label>
          <label className="field-stack"><span>Instruction</span><textarea aria-label="Question instruction" value={instruction} onChange={(event) => setInstruction(event.target.value)} /></label>
          <Notice>Image upload is available through the media API, but this compact form does not attach images yet.</Notice>
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
    </>
  )
}
