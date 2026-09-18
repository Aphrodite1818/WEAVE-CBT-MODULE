import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ExamOperations, ExamOperationsDetail } from '../src/features/admin/pages/ExamOperations'

function todayAt(hour = 9, minute = 0) {
  const now = new Date()
  return new Date(now.getFullYear(), now.getMonth(), now.getDate(), hour, minute, 0).toISOString()
}

function makeSubject(overrides = {}) {
  return {
    id: 'jss1-english',
    academicLevelId: 'jss1',
    academicLevelName: 'JSS1',
    academicLevelCategory: 'junior_secondary',
    academicLevelPosition: 1,
    name: 'English Language',
    code: 'ENG',
    ...overrides,
  }
}

function makeExam(overrides = {}) {
  return {
    id: 'exam-1',
    title: 'English CA 1',
    academicLevelId: 'jss1',
    academicLevelName: 'JSS1',
    subjectName: 'English Language',
    subjectCode: 'ENG',
    curriculumSubjectId: 'jss1-english',
    assessmentName: 'CA 1',
    status: 'sealed',
    statusLabel: 'Sealed',
    rosterStatus: 'ready',
    rosterVersion: 2,
    rosterCandidateCount: 126,
    rosterPreparedAt: todayAt(7),
    rosterError: '',
    revisionNumber: 1,
    scheduledStartAt: todayAt(9),
    latestNormalStartAt: todayAt(9, 15),
    durationMinutes: 45,
    questionCount: 30,
    ...overrides,
  }
}

function makeAdminData(exams) {
  return {
    exams,
    subjects: [
      makeSubject(),
      makeSubject({
        id: 'jss2-math',
        academicLevelId: 'jss2',
        academicLevelName: 'JSS2',
        academicLevelPosition: 2,
        name: 'Mathematics',
        code: 'MTH',
      }),
    ],
    loading: false,
    error: '',
    warning: '',
    refreshExams: vi.fn().mockResolvedValue(undefined),
  }
}

function makeGateway() {
  return {
    exams: {
      activateExam: vi.fn().mockResolvedValue({}),
      suspendExam: vi.fn().mockResolvedValue({}),
      resumeExam: vi.fn().mockResolvedValue({}),
      closeExam: vi.fn().mockResolvedValue({}),
      cancelExam: vi.fn().mockResolvedValue({}),
    },
  }
}

describe('Admin exam operations workspace', () => {
  it('shows operational papers on the day-of timetable and excludes unsealed authoring work', () => {
    const data = makeAdminData([
      makeExam(),
      makeExam({ id: 'submitted-1', title: 'Submitted English Paper', status: 'submitted', statusLabel: 'Submitted', rosterStatus: 'not_prepared' }),
    ])

    render(<ExamOperations adminData={data} onNavigate={vi.fn()} />)

    expect(screen.getByText('English CA 1')).toBeInTheDocument()
    expect(screen.queryByText('Submitted English Paper')).not.toBeInTheDocument()
    expect(screen.getByText('Scheduled today')).toBeInTheDocument()
    expect(screen.getByText('Ready to start')).toBeInTheDocument()
  })

  it('keeps level-first subject filtering in the operations workspace', () => {
    const data = makeAdminData([
      makeExam(),
      makeExam({
        id: 'math-exam',
        title: 'JSS2 Mathematics CA 1',
        academicLevelId: 'jss2',
        academicLevelName: 'JSS2',
        subjectName: 'Mathematics',
        curriculumSubjectId: 'jss2-math',
      }),
    ])

    render(<ExamOperations adminData={data} onNavigate={vi.fn()} />)

    const levelFilter = screen.getByRole('combobox', { name: /operations level filter/i })
    const subjectFilter = screen.getByRole('combobox', { name: /operations subject filter/i })
    expect(subjectFilter).toBeDisabled()

    fireEvent.click(levelFilter)
    fireEvent.click(screen.getByRole('option', { name: /^JSS2$/i }))

    expect(subjectFilter).toBeEnabled()
    expect(screen.queryByText('English CA 1')).not.toBeInTheDocument()
    expect(screen.getByText('JSS2 Mathematics CA 1')).toBeInTheDocument()
  })

  it('activates a sealed examination from the operations control room', async () => {
    const exam = makeExam()
    const data = makeAdminData([exam])
    const gateway = makeGateway()

    render(
      <ExamOperationsDetail
        state={{ staff: { selectedExamId: exam.id } }}
        adminData={data}
        gateway={gateway}
        onNavigate={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /activate examination/i }))
    const dialog = screen.getByRole('alertdialog')
    expect(dialog).toHaveTextContent(/activate this examination/i)
    fireEvent.click(within(dialog).getByRole('button', { name: /^activate examination$/i }))

    await waitFor(() => expect(gateway.exams.activateExam).toHaveBeenCalledWith('exam-1'))
    expect(data.refreshExams).toHaveBeenCalled()
  })

  it('requires an audit reason before suspending a live examination', async () => {
    const exam = makeExam({ status: 'active', statusLabel: 'Active' })
    const data = makeAdminData([exam])
    const gateway = makeGateway()

    render(
      <ExamOperationsDetail
        state={{ staff: { selectedExamId: exam.id } }}
        adminData={data}
        gateway={gateway}
        onNavigate={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /suspend examination/i }))
    const dialog = screen.getByRole('alertdialog')
    fireEvent.click(within(dialog).getByRole('button', { name: /^suspend examination$/i }))

    expect(within(dialog).getByText(/enter a reason before continuing/i)).toBeInTheDocument()
    expect(gateway.exams.suspendExam).not.toHaveBeenCalled()

    fireEvent.change(within(dialog).getByRole('textbox', { name: /reason/i }), { target: { value: 'Network interruption' } })
    fireEvent.click(within(dialog).getByRole('button', { name: /^suspend examination$/i }))

    await waitFor(() => expect(gateway.exams.suspendExam).toHaveBeenCalledWith('exam-1', 'Network interruption'))
  })
})
