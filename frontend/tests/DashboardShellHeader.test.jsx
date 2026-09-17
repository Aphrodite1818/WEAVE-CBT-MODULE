import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { AdminWorkspace } from '../src/features/admin/AdminWorkspace'
import { TeacherLayout } from '../src/features/teacher/TeacherLayout'

const installation = { status: { tenant_name: 'Brightfield Academy', server_name: 'Main CBT Lab' } }
const branding = { school_name: 'Brightfield Academy' }

function createAdminGateway() {
  return {
    questions: {
      listAdminQuestionBanks: vi.fn().mockResolvedValue([]),
      listQuestionsForBank: vi.fn().mockResolvedValue([]),
    },
    academics: {
      getCurrentAcademicSession: vi.fn().mockResolvedValue({ id: 'session-1', name: '2026/2027', status: 'open', is_current: true }),
      getCurrentAcademicTerm: vi.fn().mockResolvedValue({ id: 'term-1', academic_session_id: 'session-1', name: 'First Term', status: 'open', is_current: true }),
      listAuthorableCurriculumSubjects: vi.fn().mockResolvedValue([]),
      listEffectiveTeacherAssignments: vi.fn().mockResolvedValue([]),
      listAssessmentSchemes: vi.fn().mockResolvedValue([]),
      listAssessmentComponents: vi.fn().mockResolvedValue([]),
    },
    exams: {
      listExams: vi.fn().mockResolvedValue({ exams: [] }),
    },
  }
}

describe('Dashboard shell headers', () => {
  it('uses the compact account pill and no notification control for teachers', () => {
    const signOut = vi.fn()
    render(
      <TeacherLayout
        state={{
          branding,
          installation,
          session: { actor: { display_name: 'Mrs. Amina Khan', email: 'teacher@brightfield.test', role: 'teacher' } },
          staff: { section: 'overview' },
        }}
        dispatch={vi.fn()}
        signOut={signOut}
      >
        <p>Teacher content</p>
      </TeacherLayout>,
    )

    const account = screen.getByRole('button', { name: /mrs\. amina khan/i })
    expect(account).toHaveClass('dashboard-account__trigger')
    expect(account.querySelector('.dashboard-account__avatar')).toHaveTextContent('M')
    expect(screen.queryByText('teacher@brightfield.test')).not.toBeInTheDocument()
    expect(screen.getAllByText('Brightfield Academy')).toHaveLength(2)
    const sidebarToggle = screen.getByRole('button', { name: /collapse sidebar/i })
    expect(sidebarToggle.closest('aside')).toHaveClass('teacher-sidebar')
    fireEvent.click(sidebarToggle)
    expect(screen.getByRole('main')).toHaveClass('teacher-shell--collapsed')
    expect(screen.queryByRole('button', { name: /notifications/i })).not.toBeInTheDocument()
    fireEvent.click(account)
    expect(screen.queryByRole('button', { name: /my profile/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /account settings/i })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /logout/i }))
    expect(signOut).toHaveBeenCalledOnce()
  })

  it('uses the same compact shell for admins and removes the old decorative controls', () => {
    render(
      <AdminWorkspace
        state={{
          branding,
          installation,
          session: { actor: { id: 'admin-1', display_name: 'Amina Yusuf', email: 'admin@brightfield.test', role: 'admin' } },
          staff: { section: 'dashboard', selectedBankId: null, selectedQuestionId: null, selectedExamId: null },
        }}
        dispatch={vi.fn()}
        signOut={vi.fn()}
        gateway={createAdminGateway()}
      />,
    )

    const account = screen.getByRole('button', { name: /amina yusuf/i })
    expect(account).toHaveClass('dashboard-account__trigger')
    expect(account.querySelector('.dashboard-account__avatar')).toHaveTextContent('A')
    expect(screen.queryByText('admin@brightfield.test')).not.toBeInTheDocument()
    expect(screen.getAllByText('Brightfield Academy')).toHaveLength(2)

    const sidebarToggle = screen.getByRole('button', { name: /collapse sidebar/i })
    expect(sidebarToggle.closest('aside')).toHaveClass('teacher-sidebar', 'admin-sidebar')
    fireEvent.click(sidebarToggle)
    expect(screen.getByRole('main')).toHaveClass('teacher-shell--collapsed', 'admin-shell--collapsed')

    expect(screen.queryByPlaceholderText(/search anything/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^settings$/i })).not.toBeInTheDocument()
    expect(screen.queryByText(/exams\s+made\s+simple/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /notifications/i })).not.toBeInTheDocument()
  })
})
