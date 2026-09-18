import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { AdminRosterDetailPage, AdminRostersPage } from '../src/features/admin/pages/AdminRostersPage'

function makeSubject(overrides = {}) {
  return {
    id: 'jss1-math',
    academicLevelId: 'jss1',
    academicLevelName: 'JSS1',
    academicLevelCategory: 'junior_secondary',
    academicLevelPosition: 1,
    name: 'Mathematics',
    code: 'MTH',
    ...overrides,
  }
}

function makeExam(overrides = {}) {
  return {
    id: 'exam-1',
    title: 'Mathematics CA 1',
    academicLevelId: 'jss1',
    academicLevelName: 'JSS1',
    subjectName: 'Mathematics',
    subjectCode: 'MTH',
    curriculumSubjectId: 'jss1-math',
    assessmentName: 'CA 1',
    status: 'sealed',
    statusLabel: 'Sealed',
    rosterStatus: 'ready',
    rosterVersion: 2,
    rosterCandidateCount: 126,
    rosterPreparedAt: '2026-09-18T08:00:00Z',
    rosterError: '',
    revisionNumber: 1,
    scheduledStartAt: '2026-09-19T09:00:00Z',
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
      }),
      makeSubject({
        id: 'jss2-science',
        academicLevelId: 'jss2',
        academicLevelName: 'JSS2',
        academicLevelPosition: 2,
        name: 'Basic Science',
        code: 'BSC',
      }),
    ],
    loading: false,
    error: '',
    warning: '',
    refreshExams: vi.fn().mockResolvedValue(undefined),
  }
}

describe('Admin roster workspace', () => {
  it('shows only prepared exam rosters and scopes subjects through academic level first', () => {
    const data = makeAdminData([
      makeExam({ id: 'exam-jss1', title: 'JSS1 Mathematics CA 1' }),
      makeExam({
        id: 'exam-jss2-math',
        title: 'JSS2 Mathematics CA 1',
        academicLevelId: 'jss2',
        academicLevelName: 'JSS2',
        curriculumSubjectId: 'jss2-math',
      }),
      makeExam({
        id: 'exam-jss2-science',
        title: 'JSS2 Basic Science CA 1',
        academicLevelId: 'jss2',
        academicLevelName: 'JSS2',
        curriculumSubjectId: 'jss2-science',
        subjectName: 'Basic Science',
        subjectCode: 'BSC',
      }),
      makeExam({
        id: 'draft-exam',
        title: 'Draft Mathematics Paper',
        status: 'draft',
        statusLabel: 'Draft',
        rosterStatus: 'not_prepared',
      }),
    ])

    render(<AdminRostersPage adminData={data} onNavigate={vi.fn()} />)

    expect(screen.getByText('JSS1 Mathematics CA 1')).toBeInTheDocument()
    expect(screen.getByText('JSS2 Mathematics CA 1')).toBeInTheDocument()
    expect(screen.queryByText('Draft Mathematics Paper')).not.toBeInTheDocument()

    const levelFilter = screen.getByRole('combobox', { name: /roster level filter/i })
    const subjectFilter = screen.getByRole('combobox', { name: /roster subject filter/i })
    expect(subjectFilter).toBeDisabled()

    fireEvent.click(levelFilter)
    fireEvent.click(screen.getByRole('option', { name: /^JSS2$/i }))

    expect(subjectFilter).toBeEnabled()
    expect(screen.queryByText('JSS1 Mathematics CA 1')).not.toBeInTheDocument()
    expect(screen.getByText('JSS2 Mathematics CA 1')).toBeInTheDocument()
    expect(screen.getByText('JSS2 Basic Science CA 1')).toBeInTheDocument()

    fireEvent.click(subjectFilter)
    expect(screen.getByRole('option', { name: /mathematics/i })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /basic science/i })).toBeInTheDocument()
  })

  it('opens the exact examination roster from its ledger card', () => {
    const onNavigate = vi.fn()
    render(<AdminRostersPage adminData={makeAdminData([makeExam()])} onNavigate={onNavigate} />)

    fireEvent.click(screen.getByRole('button', { name: /open roster for mathematics ca 1/i }))

    expect(onNavigate).toHaveBeenCalledWith('roster-detail', { selectedExamId: 'exam-1' })
  })

  it('loads eligible candidates with server-side paging metadata and renders class context', async () => {
    const exam = makeExam()
    const listExamRoster = vi.fn().mockResolvedValue({
      exam_id: exam.id,
      roster_status: 'ready',
      roster_version: 2,
      roster_candidate_count: 126,
      offset: 0,
      limit: 50,
      total: 1,
      classes: [{ id: 'class-a', display_name: 'JSS1 A' }],
      candidates: [{
        id: 'candidate-1',
        exam_id: exam.id,
        enrollment_id: 'enrollment-1',
        student_id: 'student-1',
        class_id: 'class-a',
        class_name: 'JSS1 A',
        admission_number: 'JSS1/001',
        display_name: 'Ada Okafor',
        status: 'eligible',
        status_reason: null,
        roster_version: 2,
      }],
    })
    const gateway = { candidates: { listExamRoster } }
    const state = { staff: { selectedExamId: exam.id } }

    render(
      <AdminRosterDetailPage
        state={state}
        adminData={makeAdminData([exam])}
        gateway={gateway}
        onNavigate={vi.fn()}
      />,
    )

    await waitFor(() => expect(listExamRoster).toHaveBeenCalledWith('exam-1', {
      offset: 0,
      limit: 50,
      status: 'eligible',
    }))

    expect(await screen.findByText('Ada Okafor')).toBeInTheDocument()
    expect(screen.getByText('JSS1/001')).toBeInTheDocument()
    expect(screen.getByText('JSS1 A')).toBeInTheDocument()
    expect(screen.getAllByText('Eligible').length).toBeGreaterThan(0)
  })
})
