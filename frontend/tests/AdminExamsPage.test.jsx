import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { AdminExamsPage } from '../src/features/admin/pages/AdminExamsPage'

function makeExam(overrides = {}) {
  return {
    id: 'exam-1',
    title: 'English CA 1',
    subjectName: 'English Language',
    assessmentName: 'CA 1',
    curriculumSubjectId: 'subject-1',
    assessmentComponentId: 'component-1',
    questionCount: 20,
    durationMinutes: 45,
    selectionMode: 'random',
    status: 'submitted',
    statusLabel: 'Submitted',
    rosterStatus: 'pending',
    authoringVersion: 4,
    revisionNumber: 1,
    scheduledStartAt: null,
    updatedAt: '2026-09-17T09:00:00Z',
    ...overrides,
  }
}

function makeAdminData(exams) {
  return {
    exams,
    subjects: [{ id: 'subject-1', name: 'English Language', code: 'ENG' }],
    assessmentComponents: [{ id: 'component-1', name: 'CA 1', maximumScore: 10 }],
    loading: false,
    error: '',
    warning: '',
    refresh: vi.fn().mockResolvedValue(undefined),
  }
}

function makeGateway() {
  return {
    exams: {
      submitExam: vi.fn().mockResolvedValue({}),
      deleteDraftExam: vi.fn().mockResolvedValue(null),
      returnExamToDraft: vi.fn().mockResolvedValue({}),
      sealExam: vi.fn().mockResolvedValue({}),
      createRevision: vi.fn().mockResolvedValue({}),
      activateExam: vi.fn().mockResolvedValue({}),
      suspendExam: vi.fn().mockResolvedValue({}),
      resumeExam: vi.fn().mockResolvedValue({}),
      closeExam: vi.fn().mockResolvedValue({}),
      cancelExam: vi.fn().mockResolvedValue({}),
    },
  }
}

describe('Admin examination workspace', () => {
  it('exposes submitted-paper review actions and executes sealing through the real gateway', async () => {
    const data = makeAdminData([makeExam()])
    const gateway = makeGateway()

    render(<AdminExamsPage adminData={data} gateway={gateway} onNavigate={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: /lifecycle actions for english ca 1/i }))
    expect(screen.getByRole('button', { name: /return to draft/i })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /seal examination/i }))

    expect(screen.getByRole('alertdialog')).toHaveTextContent(/seal this examination/i)
    fireEvent.click(screen.getByRole('button', { name: /^seal examination$/i }))

    await waitFor(() => expect(gateway.exams.sealExam).toHaveBeenCalledWith('exam-1'))
    expect(data.refresh).toHaveBeenCalled()
  })

  it('prevents activation in the UI until the candidate roster is ready', () => {
    const data = makeAdminData([
      makeExam({ id: 'exam-2', title: 'English Final', status: 'sealed', statusLabel: 'Sealed', rosterStatus: 'pending' }),
    ])

    render(<AdminExamsPage adminData={data} gateway={makeGateway()} onNavigate={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: /lifecycle actions for english final/i }))
    const activate = screen.getByRole('button', { name: /activate examination/i })
    expect(activate).toBeDisabled()
    expect(activate).toHaveTextContent(/candidate roster must be ready/i)
    expect(screen.getByRole('button', { name: /create revision/i })).toBeEnabled()
  })

  it('requires an audit reason before suspending an active examination', async () => {
    const data = makeAdminData([
      makeExam({ id: 'exam-3', title: 'English Mock', status: 'active', statusLabel: 'Active', rosterStatus: 'ready' }),
    ])
    const gateway = makeGateway()

    render(<AdminExamsPage adminData={data} gateway={gateway} onNavigate={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: /lifecycle actions for english mock/i }))
    fireEvent.click(screen.getByRole('button', { name: /suspend examination/i }))
    fireEvent.click(screen.getByRole('button', { name: /^suspend exam$/i }))

    expect(screen.getByText(/enter a reason before continuing/i)).toBeInTheDocument()
    expect(gateway.exams.suspendExam).not.toHaveBeenCalled()

    fireEvent.change(screen.getByRole('textbox', { name: /reason/i }), { target: { value: 'Network maintenance' } })
    fireEvent.click(screen.getByRole('button', { name: /^suspend exam$/i }))

    await waitFor(() => expect(gateway.exams.suspendExam).toHaveBeenCalledWith('exam-3', 'Network maintenance'))
  })
})
