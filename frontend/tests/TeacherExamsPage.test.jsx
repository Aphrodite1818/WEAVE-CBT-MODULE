import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { TeacherExamsPage } from '../src/features/teacher/TeacherExamsPage'

import { ExamAuthoringPage } from '../src/shared/exams/ExamAuthoringPage'

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
      folderColor: '#397fd6',
      status: 'draft',
      statusLabel: 'Draft',
      updatedAt: '2026-09-16T10:00:00Z',
      authoringVersion: 3,
      revisionNumber: 1,
      createdByActorId: 'actor-1',
      leadTeacherId: 'teacher-1',
      rosterCandidateCount: 0,
      scheduledStartAt: null,
      latestNormalStartAt: null,
    },
  ],
  assignments: [{ teacherMembershipId: 'teacher-1', curriculumSubjectId: 'subject-1' }],
  subjects: [
    {
      id: 'subject-1',
      academicLevelId: 'level-jss1',
      academicLevelName: 'JSS1',
      academicLevelCategory: 'junior_secondary',
      academicLevelPosition: 1,
      name: 'Mathematics',
      code: 'MTH',
    },
  ],
  banks: [
    {
      id: 'bank-1',
      curriculumSubjectId: 'subject-1',
      academicLevelId: 'level-jss1',
      academicLevelName: 'JSS1',
      subjectName: 'Mathematics',
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
    expect(screen.getByRole('heading', { name: 'Mathematics CA 1' })).toBeInTheDocument()
    expect(screen.getByText(/30 questions/)).toHaveTextContent('45 min')
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
      <ExamAuthoringPage
        state={teacherState}
        dispatch={dispatch}
        teacherData={{ ...teacherData, exams: [], refresh }}
        gateway={{ exams: { createExam } }}
      />,
    )

    await waitFor(() =>
      expect(screen.getAllByText('Mathematics Bank').length).toBeGreaterThan(0),
    )
    expect(screen.getByRole('combobox', { name: /academic level/i })).toHaveTextContent('JSS1')
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
      folder_color: '#8190a5',
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

  it('filters duplicate subject names by academic level before exam creation', () => {
    const scopedData = {
      ...teacherData,
      exams: [],
      subjects: [
        ...teacherData.subjects,
        {
          id: 'subject-2',
          academicLevelId: 'level-jss2',
          academicLevelName: 'JSS2',
          academicLevelCategory: 'junior_secondary',
          academicLevelPosition: 2,
          name: 'Mathematics',
          code: 'MTH',
        },
        {
          id: 'subject-3',
          academicLevelId: 'level-jss2',
          academicLevelName: 'JSS2',
          academicLevelCategory: 'junior_secondary',
          academicLevelPosition: 2,
          name: 'Basic Science',
          code: 'BSC',
        },
      ],
      banks: [
        ...teacherData.banks,
        {
          id: 'bank-2',
          curriculumSubjectId: 'subject-2',
          academicLevelId: 'level-jss2',
          academicLevelName: 'JSS2',
          subjectName: 'Mathematics',
          name: 'JSS2 Mathematics Bank',
          count: 30,
          activeQuestionCount: 30,
        },
        {
          id: 'bank-3',
          curriculumSubjectId: 'subject-3',
          academicLevelId: 'level-jss2',
          academicLevelName: 'JSS2',
          subjectName: 'Basic Science',
          name: 'JSS2 Science Bank',
          count: 25,
          activeQuestionCount: 25,
        },
      ],
    }

    render(
      <ExamAuthoringPage
        state={teacherState}
        dispatch={vi.fn()}
        teacherData={scopedData}
        gateway={{ exams: { createExam: vi.fn() } }}
      />,
    )

    const levelSelect = screen.getByRole('combobox', { name: /academic level/i })
    const subjectSelect = screen.getByRole('combobox', { name: /^subject$/i })
    expect(levelSelect).toHaveTextContent('JSS1')
    expect(subjectSelect).toHaveTextContent('Mathematics')

    fireEvent.click(levelSelect)
    fireEvent.click(screen.getByRole('option', { name: /JSS2/i }))

    expect(screen.getByRole('combobox', { name: /^subject$/i })).toHaveTextContent('Mathematics')
    fireEvent.click(screen.getByRole('combobox', { name: /^subject$/i }))
    expect(screen.getByRole('option', { name: /Basic Science/i })).toBeInTheDocument()
    expect(screen.getAllByRole('option', { name: /Mathematics/i })).toHaveLength(1)

    fireEvent.click(screen.getByRole('option', { name: /Basic Science/i }))
    expect(screen.getByRole('combobox', { name: /question bank/i })).toHaveTextContent('JSS2 Science Bank')
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
