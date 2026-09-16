import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { CreateQuestionPage } from '../src/features/teacher/QuestionsPage'

const bank = { id: 'bank-1', name: 'Mathematics', count: 0, status: 'Ready' }

describe('Teacher question creation', () => {
  it('uploads a selected image and sends its asset id with the question payload', async () => {
    const dispatch = vi.fn()
    const refresh = vi.fn().mockResolvedValue(undefined)
    const uploadQuestionImage = vi.fn().mockResolvedValue({ id: 'asset-1' })
    const createSingleChoiceQuestion = vi.fn().mockResolvedValue({ id: 'question-1' })

    render(
      <CreateQuestionPage
        state={{ staff: { selectedBankId: bank.id } }}
        dispatch={dispatch}
        teacherData={{ banks: [bank], refresh }}
        gateway={{
          media: { uploadQuestionImage },
          questions: { createSingleChoiceQuestion, createMultipleChoiceQuestion: vi.fn() },
        }}
      />,
    )

    const image = new File(['image-bytes'], 'diagram.png', { type: 'image/png' })
    fireEvent.change(screen.getByLabelText(/choose image/i), { target: { files: [image] } })
    fireEvent.change(screen.getByLabelText(/question prompt/i), { target: { value: 'What does the diagram show?' } })
    fireEvent.change(screen.getByLabelText(/option a/i), { target: { value: 'A cell' } })
    fireEvent.change(screen.getByLabelText(/option b/i), { target: { value: 'A planet' } })
    fireEvent.click(screen.getByRole('button', { name: /save question/i }))

    await waitFor(() => expect(uploadQuestionImage).toHaveBeenCalledWith(image))
    expect(createSingleChoiceQuestion).toHaveBeenCalledWith(bank.id, {
      prompt: 'What does the diagram show?',
      instruction: null,
      image_asset_id: 'asset-1',
      options: [
        { text: 'A cell', is_correct: true },
        { text: 'A planet', is_correct: false },
      ],
    })
    expect(refresh).toHaveBeenCalled()
    expect(dispatch).toHaveBeenCalledWith({ type: 'staff', patch: { section: 'bank-detail', selectedBankId: bank.id } })
  })
})
