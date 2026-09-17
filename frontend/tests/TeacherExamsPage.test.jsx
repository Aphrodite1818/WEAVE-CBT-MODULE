import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { TeacherCreateExamPage, TeacherExamsPage } from '../src/features/teacher/TeacherExamsPage'

const teacherData = {
  exams: [
    {
      id: 'exam-1',
      title: 'Mathematics CA 1',
      subjectName: 'Mathematics',
      curriculumSubjectId: 'subject-1',
      assessmentSchemeId: 'scheme-1',
      assessmentComponentId: 'component-1',
      assessmentName: 'CA 1',
      questionBankId: 'bank-1',
      questionCount: 30,
      selectionMode: 'manual',
      durationMinutes: 45,
      shuffleQuestions: true,
      shuffleOptions: true,
      instructions: '',
      status: 'draft',
      statusLabel: 'Draft',
      updatedAt: '2026-09-16T10:00:00Z',
      authoringVersion: 3,
      revisionNumber: 1,
      createdByActorId: 'actor-1',
      rosterCandidateCount: 0,
      scheduledStartAt: null,
      latestNormalStartAt: null,
    },
  ],
  subjects: [{ id: 'subject-1', name: 'Mathematics' }],
  banks: [
    {
      id: 'bank-1',
      curriculumSubjectId: 'subject-1',
      name: 'Mathematics Bank',
      count: 40,
      activeQuestionCount: 40,
    },
  ],
  assessmentSchemes: [
    { id: 'scheme-1', name: 'Standard Scheme', status: 'active' },
  ],
  assessmentComponents: [
    {
      id: 'component-1',
      schemeId: 'scheme-1',
      name: 'CA 1',
      maximumScore: 10,
    },
  ],
  session: { id: 'session-1', name: '2026/2027' },
  term: { id: 'term-1', name: 'First Term' },
  loading: false,
  error: '',
  warning: '',
  refresh: vi.fn().mockResolvedValue(undefined),
}

const teacherState = {
  session: { actor: { id: 'actor-1', role: 'teacher' } },
  staff: { selectedExamId: null },
}

describe('Teacher exams', () => {
  it('renders a readable exam collection and opens the create workflow', () => {
    const dispatch = vi.fn()
    render(
      <TeacherExamsPage
        state={teacherState}
        dispatch={dispatch}
        teacherData={teacherData}
        gateway={{ exams: {} }}
      />,
    )

    expect(screen.getByRole('heading', { name: /examinations/i })).toBeInTheDocument()
    expect(screen.getByText('Mathematics CA 1')).toBeInTheDocument()
    expect(screen.getByText('30 questions')).toBeInTheDocument()
    expect(screen.getByText('45 min')).toBeInTheDocument()
    expect(screen.getByText('Draft')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /^create exam$/i }))
    expect(dispatch).toHaveBeenCalledWith({
      type: 'staff',
      patch: { section: 'create-exam', selectedExamId: null },
    })
  })

  it('creates a draft with synchronized academic and delivery settings', async () => {
    const dispatch = vi.fn()
    const createExam = vi.fn().mockResolvedValue({ id: 'exam-new' })
    const refresh = vi.fn().mockResolvedValue(undefined)

    render(
      <TeacherCreateExamPage
        state={teacherState}
        dispatch={dispatch}
        teacherData={{ ...teacherData, exams: [], refresh }}
        gateway={{ exams: { createExam } }}
      />,
    )

    await waitFor(() =>
      expect(screen.getAllByText('Mathematics Bank').length).toBeGreaterThan(0),
    )
    fireEvent.change(screen.getByLabelText(/exam title/i), {
      target: { value: 'Mathematics Mid Term' },
    })
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
      scheduled_start_at: null,
      latest_normal_start_at: null,
    })
    expect(refresh).toHaveBeenCalled()
    expect(dispatch).toHaveBeenCalledWith({
      type: 'staff',
      patch: { section: 'exams', selectedExamId: null },
    })
  })

  it('uses the current authoring version when submitting a draft', async () => {
    const dispatch = vi.fn()
    const submitExam = vi.fn().mockResolvedValue({})
    const refresh = vi.fn().mockResolvedValue(undefined)

    render(
      <TeacherExamsPage
        state={teacherState}
        dispatch={dispatch}
        teacherData={{ ...teacherData, refresh }}
        gateway={{ exams: { submitExam, deleteDraftExam: vi.fn() } }}
      />,
    )

    fireEvent.click(
      screen.getByRole('button', {
        name: /lifecycle actions for mathematics ca 1/i,
      }),
    )
    fireEvent.click(screen.getByRole('button', { name: /submit for review/i }))
    fireEvent.click(screen.getByRole('button', { name: /^submit for review$/i }))

    await waitFor(() => expect(submitExam).toHaveBeenCalledWith('exam-1', 3))
    expect(refresh).toHaveBeenCalled()
  })
})
