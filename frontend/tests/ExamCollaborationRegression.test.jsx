import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { TeacherExamsPage } from '../src/features/teacher/TeacherExamsPage'
import { ExamAuthoringPage } from '../src/shared/exams/ExamAuthoringPage'

const state = {
  session: { actor: { id: 'actor-b', role: 'teacher', display_name: 'Teacher B' } },
  staff: { selectedExamId: null },
}

function makeExam(overrides = {}) {
  return {
    id: 'exam-1',
    sessionId: 'session-1',
    termId: 'term-1',
    title: 'JSS1 English Exam',
    academicLevelId: 'level-jss1',
    academicLevelName: 'JSS1',
    subjectName: 'English',
    curriculumSubjectId: 'subject-1',
    assessmentSchemeId: 'scheme-1',
    assessmentComponentId: 'component-1',
    assessmentName: 'EXAM',
    questionBankId: 'bank-1',
    questionCount: 20,
    selectionMode: 'random',
    durationMinutes: 45,
    shuffleQuestions: true,
    shuffleOptions: true,
    instructions: '',
    folderColor: '#b77915',
    status: 'draft',
    statusLabel: 'Draft',
    authoringVersion: 2,
    revisionNumber: 1,
    leadTeacherId: 'teacher-a',
    scheduledStartAt: '2026-09-23T19:00:00.000Z',
    latestNormalStartAt: '2026-09-23T19:14:00.000Z',
    createdAt: '2026-09-23T18:00:00.000Z',
    updatedAt: '2026-09-23T18:30:00.000Z',
    ...overrides,
  }
}

function makeTeacherData(exam, assignmentTeacherId = 'teacher-b') {
  return {
    exams: [exam],
    assignments: [{ teacherMembershipId: assignmentTeacherId, curriculumSubjectId: 'subject-1' }],
    subjects: [{
      id: 'subject-1',
      academicLevelId: 'level-jss1',
      academicLevelName: 'JSS1',
      academicLevelCategory: 'junior_secondary',
      academicLevelPosition: 1,
      name: 'English',
      code: 'ENG',
    }],
    banks: [{
      id: 'bank-1',
      curriculumSubjectId: 'subject-1',
      academicLevelId: 'level-jss1',
      academicLevelName: 'JSS1',
      subjectName: 'English',
      name: 'JSS1 English',
      count: 40,
      activeQuestionCount: 40,
    }],
    assessmentSchemes: [{ id: 'scheme-1', name: '2026/2027 Scheme', status: 'active' }],
    assessmentComponents: [{ id: 'component-1', schemeId: 'scheme-1', name: 'EXAM', maximumScore: 70 }],
    session: { id: 'session-1', name: '2026/2027' },
    term: { id: 'term-1', name: 'First Term' },
    loading: false,
    error: '',
    warning: '',
    refresh: vi.fn().mockResolvedValue(undefined),
  }
}

describe('shared examination collaboration guidance', () => {
  it('explains that a random shared draft needs no collaborator question configuration', () => {
    const exam = makeExam({ selectionMode: 'random' })
    render(
      <TeacherExamsPage
        state={state}
        dispatch={vi.fn()}
        teacherData={makeTeacherData(exam)}
        gateway={{ exams: {} }}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /lifecycle actions for jss1 english exam/i }))

    expect(screen.getByText(/uses Random selection/i)).toBeInTheDocument()
    expect(screen.getByText(/you do not need to add or configure questions/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /contribute questions/i })).not.toBeInTheDocument()
  })

  it('gives an eligible non-lead a contribution path for a manual shared draft', () => {
    const dispatch = vi.fn()
    const exam = makeExam({ selectionMode: 'manual' })
    render(
      <TeacherExamsPage
        state={state}
        dispatch={dispatch}
        teacherData={makeTeacherData(exam)}
        gateway={{ exams: {} }}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /lifecycle actions for jss1 english exam/i }))
    fireEvent.click(screen.getByRole('button', { name: /contribute questions/i }))

    expect(dispatch).toHaveBeenCalledWith({
      type: 'staff',
      patch: { section: 'create-exam', selectedExamId: 'exam-1' },
    })
  })
})

describe('exam question configuration saves', () => {
  it('does not resend an unchanged historical schedule when only question configuration changes', async () => {
    const exam = makeExam({
      selectionMode: 'random',
      leadTeacherId: 'teacher-b',
    })
    const teacherData = makeTeacherData(exam, 'teacher-b')
    const updateExam = vi.fn().mockResolvedValue({ authoring_version: 3 })
    const configureExamQuestions = vi.fn().mockResolvedValue({ authoring_version: 4 })
    const dispatch = vi.fn()

    render(
      <ExamAuthoringPage
        state={{ ...state, staff: { selectedExamId: 'exam-1' } }}
        dispatch={dispatch}
        teacherData={teacherData}
        gateway={{
          exams: { updateExam, configureExamQuestions },
          questions: {},
        }}
      />,
    )

    fireEvent.click(screen.getByRole('radio', { name: /manual selection/i }))
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }))

    await waitFor(() => expect(updateExam).toHaveBeenCalledTimes(1))
    const [, payload] = updateExam.mock.calls[0]
    expect(payload).not.toHaveProperty('scheduled_start_at')
    expect(payload).not.toHaveProperty('latest_normal_start_at')

    await waitFor(() => expect(configureExamQuestions).toHaveBeenCalledWith('exam-1', expect.objectContaining({
      question_selection_mode: 'manual',
      expected_authoring_version: 3,
    })))
  })
})
