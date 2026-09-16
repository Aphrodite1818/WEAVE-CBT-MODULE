import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { AdminWorkspace } from '../src/features/admin/AdminWorkspace'
import { TeacherLayout } from '../src/features/teacher/TeacherLayout'

const installation = { status: { tenant_name: 'Brightfield Academy', server_name: 'Main CBT Lab' } }
const branding = { school_name: 'Brightfield Academy' }

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

  it('uses the same compact account pill and no notification control for admins', () => {
    render(
      <AdminWorkspace
        state={{
          branding,
          installation,
          session: { actor: { display_name: 'Amina Yusuf', email: 'admin@brightfield.test', role: 'admin' } },
          staff: { section: 'dashboard' },
        }}
        dispatch={vi.fn()}
        signOut={vi.fn()}
      />,
    )

    const account = screen.getByRole('button', { name: /amina yusuf/i })
    expect(account).toHaveClass('dashboard-account__trigger')
    expect(account.querySelector('.dashboard-account__avatar')).toHaveTextContent('A')
    expect(screen.queryByText('admin@brightfield.test')).not.toBeInTheDocument()
    expect(screen.getAllByText('Brightfield Academy')).toHaveLength(2)
    const sidebarToggle = screen.getByRole('button', { name: /collapse sidebar/i })
    expect(sidebarToggle.closest('aside')).toHaveClass('premium-sidebar')
    fireEvent.click(sidebarToggle)
    expect(sidebarToggle.closest('.premium-admin-shell')).toHaveClass('premium-admin-shell--collapsed')
    expect(screen.queryByRole('button', { name: /notifications/i })).not.toBeInTheDocument()
  })
})
