import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { OverviewPage } from '../src/features/teacher/OverviewPage'

describe('Teacher overview', () => {
  it('renders real academic and exam data in the reference dashboard layout', () => {
    const dispatch = vi.fn()
    const { container } = render(
      <OverviewPage
        state={{ session: { actor: { display_name: 'Taiwo A.', role: 'teacher' } } }}
        dispatch={dispatch}
        teacherData={{
          banks: [{ id: 'bank-1', name: 'Mathematics', count: 12 }],
          questions: [],
          subjects: [{ id: 'subject-1', name: 'Mathematics' }, { id: 'subject-2', name: 'Physics' }],
          assignments: [{ curriculumSubjectId: 'subject-1', subjectName: 'Mathematics', className: 'SS2 A' }],
          exams: [
            { id: 'exam-1', title: 'Mathematics CA 1', subjectName: 'Mathematics', questionCount: 30, selectionMode: 'manual', status: 'draft' },
            { id: 'exam-2', title: 'Physics Test', subjectName: 'Physics', questionCount: 20, selectionMode: 'random', status: 'submitted' },
          ],
          session: { id: 'session-1', name: '2026/2027 Academic Session' },
          term: { id: 'term-1', name: 'First Term' },
          loading: false,
          error: '',
          warning: '',
        }}
      />,
    )

    expect(screen.getByRole('heading', { name: /good morning, taiwo/i })).toBeInTheDocument()
    expect(screen.getByText(/2026\/2027 academic session/i)).toBeInTheDocument()
    expect(container.querySelectorAll('.teacher-overview-stat')).toHaveLength(4)
    expect(screen.getByText('Mathematics CA 1')).toBeInTheDocument()
    expect(screen.getByText('SS2 A')).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: /teacher quick actions/i })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /^question banks$/i }))
    expect(dispatch).toHaveBeenCalledWith({ type: 'staff', patch: { section: 'question-banks' } })

    fireEvent.click(screen.getByRole('button', { name: /continue/i }))
    expect(dispatch).toHaveBeenCalledWith({ type: 'staff', patch: { section: 'exams', selectedExamId: 'exam-1' } })
  })
})
