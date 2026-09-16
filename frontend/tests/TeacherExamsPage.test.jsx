import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { CreateExamPage, ExamsPage } from '../src/features/teacher/ExamsPage'

const teacherData = {
  exams: [
    {
      id: 'exam-1',
      title: 'Mathematics CA 1',
      subjectName: 'Mathematics',
      curriculumSubjectId: 'subject-1',
      assessmentComponentId: 'component-1',
      assessmentName: 'CA 1',
      questionCount: 30,
      selectionMode: 'manual',
      durationMinutes: 45,
      status: 'draft',
      statusLabel: 'Draft',
      updatedAt: '2026-09-16T10:00:00Z',
      authoringVersion: 1,
      rosterCandidateCount: 0,
      scheduledStartAt: null,
    },
  ],
  subjects: [{ id: 'subject-1', name: 'Mathematics' }],
  banks: [{ id: 'bank-1', curriculumSubjectId: 'subject-1', name: 'Mathematics Bank' }],
  assessmentSchemes: [{ id: 'scheme-1', name: 'Standard Scheme', status: 'active' }],
  assessmentComponents: [{ id: 'component-1', schemeId: 'scheme-1', name: 'CA 1', maximumScore: 10 }],
  session: { id: 'session-1', name: '2026/2027' },
  term: { id: 'term-1', name: 'First Term' },
  loading: false,
  error: '',
  refresh: vi.fn().mockResolvedValue(undefined),
}

describe('Teacher exams', () => {
  it('renders the real teacher exam collection and status filters', () => {
    const dispatch = vi.fn()
    render(<ExamsPage state={{ staff: {} }} dispatch={dispatch} teacherData={teacherData} />)

    expect(screen.getByRole('heading', { name: /examinations/i })).toBeInTheDocument()
    expect(screen.getByText('Mathematics CA 1')).toBeInTheDocument()
    expect(screen.getByText('CA 1')).toBeInTheDocument()
    expect(screen.getByText('Draft')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /create exam/i }))
    expect(dispatch).toHaveBeenCalledWith({ type: 'staff', patch: { section: 'create-exam' } })
  })

  it('creates a draft using synchronized academic ids instead of placeholder values', async () => {
    const dispatch = vi.fn()
    const createExam = vi.fn().mockResolvedValue({ id: 'exam-new' })
    const refresh = vi.fn().mockResolvedValue(undefined)

    render(
      <CreateExamPage
        dispatch={dispatch}
        teacherData={{ ...teacherData, exams: [], refresh }}
        gateway={{ exams: { createExam } }}
      />,
    )

    await waitFor(() => expect(screen.getByLabelText(/subject/i)).toHaveValue('subject-1'))
    fireEvent.change(screen.getByLabelText(/exam title/i), { target: { value: 'Mathematics Mid Term' } })
    fireEvent.click(screen.getByRole('button', { name: /create draft exam/i }))

    await waitFor(() => expect(createExam).toHaveBeenCalledTimes(1))
    expect(createExam).toHaveBeenCalledWith({
      session_id: 'session-1',
      term_id: 'term-1',
      curriculum_subject_id: 'subject-1',
      assessment_scheme_id: 'scheme-1',
      assessment_component_id: 'component-1',
      question_bank_id: 'bank-1',
      question_selection_mode: 'random',
      question_count: 20,
      title: 'Mathematics Mid Term',
      instructions: null,
      duration_minutes: 45,
      shuffle_questions: true,
      shuffle_options: true,
    })
    expect(refresh).toHaveBeenCalled()
    expect(dispatch).toHaveBeenCalledWith({ type: 'staff', patch: { section: 'exams', selectedExamId: 'exam-new' } })
  })
})
