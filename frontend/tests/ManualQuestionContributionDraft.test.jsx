import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ManualQuestionPicker } from '../src/shared/exams/ManualQuestionPicker'

const questions = [
  {
    id: 'question-1',
    prompt: 'What is 2 + 2?',
    instruction: '',
    question_type: 'multiple_choice',
    is_active: true,
    image_asset_id: null,
    options: [],
  },
  {
    id: 'question-2',
    prompt: 'What is 3 + 3?',
    instruction: '',
    question_type: 'multiple_choice',
    is_active: true,
    image_asset_id: null,
    options: [],
  },
]

function makeGateway() {
  return {
    questions: {
      listQuestionsForBank: vi.fn().mockResolvedValue(questions),
    },
    exams: {
      listManualQuestions: vi.fn().mockResolvedValue([]),
      getExam: vi.fn().mockResolvedValue({ authoring_version: 7 }),
      addManualQuestions: vi.fn().mockResolvedValue({ authoring_version: 8 }),
      removeManualQuestion: vi.fn(),
    },
  }
}

function renderContributor(gateway, onSaved = vi.fn()) {
  return render(
    <ManualQuestionPicker
      bankId="bank-1"
      exam={{ id: 'exam-1', questionCount: 2 }}
      gateway={gateway}
      selectedIds={[]}
      onChange={vi.fn()}
      disabled={false}
      onBusyChange={vi.fn()}
      onSaved={onSaved}
      actorId="actor-b"
      canManageAllSelections={false}
    />,
  )
}

describe('manual examination contribution drafts', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('keeps new contributor picks in local storage until Save contribution is used', async () => {
    const gateway = makeGateway()
    const onSaved = vi.fn().mockResolvedValue(undefined)
    const storageKey = 'weave-cbt:manual-contribution:exam-1:actor-b:bank-1'

    const firstRender = renderContributor(gateway, onSaved)
    const firstQuestion = await screen.findByRole('checkbox', { name: 'Select question: What is 2 + 2?' })

    fireEvent.click(firstQuestion)

    expect(gateway.exams.addManualQuestions).not.toHaveBeenCalled()
    expect(JSON.parse(window.localStorage.getItem(storageKey))).toEqual({ questionIds: ['question-1'] })
    expect(screen.getByText(/1 question waiting to be saved/i)).toBeInTheDocument()

    firstRender.unmount()

    renderContributor(gateway, onSaved)
    const restoredQuestion = await screen.findByRole('checkbox', { name: 'Select question: What is 2 + 2?' })
    expect(restoredQuestion).toBeChecked()
    expect(screen.getByText(/not saved yet/i)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /save contribution/i }))

    await waitFor(() => expect(gateway.exams.addManualQuestions).toHaveBeenCalledWith(
      'exam-1',
      ['question-1'],
      7,
    ))
    await waitFor(() => expect(window.localStorage.getItem(storageKey)).toBeNull())
    expect(onSaved).toHaveBeenCalledTimes(1)
  })
})
