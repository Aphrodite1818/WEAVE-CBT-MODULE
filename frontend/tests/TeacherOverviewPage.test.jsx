import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { OverviewPage } from '../src/features/teacher/OverviewPage'

describe('Teacher overview', () => {
  it('renders the reference layout with visible KPI icon SVGs and real empty states', () => {
    const dispatch = vi.fn()
    const { container } = render(
      <OverviewPage
        dispatch={dispatch}
        teacherData={{ banks: [], questions: [], loading: false, error: '' }}
      />,
    )

    const summary = screen.getByLabelText(/teacher workspace summary/i)
    expect(within(summary).getAllByRole('article')).toHaveLength(4)
    expect(container.querySelectorAll('.teacher-stat-card__icon .teacher-kpi-icon')).toHaveLength(4)
    expect(screen.getByText(/no recent exams to show yet/i)).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: /teacher quick actions/i })).toBeInTheDocument()
    expect(screen.queryByText('320')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /manage question banks/i }))
    expect(dispatch).toHaveBeenCalledWith({ type: 'staff', patch: { section: 'question-banks' } })
  })
})
