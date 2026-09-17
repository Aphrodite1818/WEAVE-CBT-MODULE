import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { AdminQuestionBanksPage } from '../src/features/admin/pages/AdminQuestionBanks'

function adminData() {
  return {
    banks: [
      {
        id: 'bank-1',
        curriculumSubjectId: 'subject-1',
        subjectName: 'English Language',
        subjectCode: 'ENG',
        name: 'JSS1 English',
        description: 'First year English questions',
        status: 'Ready',
        count: 4,
        activeQuestionCount: 3,
      },
      {
        id: 'bank-2',
        curriculumSubjectId: 'subject-2',
        subjectName: 'Mathematics',
        subjectCode: 'MTH',
        name: 'JSS1 Mathematics Archive',
        description: null,
        status: 'Archived',
        count: 0,
        activeQuestionCount: 0,
      },
    ],
    subjects: [
      { id: 'subject-1', name: 'English Language', code: 'ENG' },
      { id: 'subject-2', name: 'Mathematics', code: 'MTH' },
    ],
    loading: false,
    error: '',
    warning: '',
    refresh: vi.fn().mockResolvedValue(undefined),
  }
}

describe('Admin question bank workspace', () => {
  it('shows all school banks and exposes admin bank lifecycle actions', async () => {
    const data = adminData()
    const gateway = {
      questions: {
        archiveQuestionBank: vi.fn().mockResolvedValue({}),
        reactivateQuestionBank: vi.fn().mockResolvedValue({}),
        deleteEmptyQuestionBank: vi.fn().mockResolvedValue(null),
        createQuestionBank: vi.fn(),
        updateQuestionBank: vi.fn(),
      },
    }

    render(
      <AdminQuestionBanksPage
        adminData={data}
        gateway={gateway}
        onNavigate={vi.fn()}
      />,
    )

    expect(screen.getByRole('heading', { name: /question banks/i })).toBeInTheDocument()
    expect(screen.getByText('JSS1 English')).toBeInTheDocument()
    expect(screen.getByText('JSS1 Mathematics Archive')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /create bank/i })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /manage jss1 english/i }))
    fireEvent.click(screen.getByRole('menuitem', { name: /archive bank/i }))
    expect(screen.getByRole('alertdialog')).toHaveTextContent(/archive this question bank/i)
    fireEvent.click(screen.getByRole('button', { name: /^archive bank$/i }))

    await waitFor(() => expect(gateway.questions.archiveQuestionBank).toHaveBeenCalledWith('bank-1'))
    expect(data.refresh).toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: /manage jss1 mathematics archive/i }))
    expect(screen.getByRole('menuitem', { name: /reactivate bank/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /delete empty bank/i })).toBeEnabled()
  })

  it('opens the backend-backed create-bank form rather than a fake question form', () => {
    const data = adminData()
    render(
      <AdminQuestionBanksPage
        adminData={data}
        gateway={{ questions: {} }}
        onNavigate={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /create bank/i }))
    expect(screen.getByRole('heading', { name: /create question bank/i })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: /curriculum subject/i })).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/jss1 english language/i)).toBeInTheDocument()
  })
})
