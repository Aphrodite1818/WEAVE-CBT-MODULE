import { act, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { weaveRequest } from '../src/api/client'
import { ToastHost } from '../src/shared/ui/ToastHost'

function response({ status = 200, body = '{}' } = {}) {
  return {
    status,
    ok: status >= 200 && status < 300,
    statusText: status === 204 ? 'No Content' : 'OK',
    text: vi.fn().mockResolvedValue(status === 204 ? '' : body),
  }
}

describe('shared toast confirmations', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows a Weave-style confirmation after a successful mutation response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ body: '{"id":"exam-1"}' })))
    render(<ToastHost />)

    await act(async () => {
      await weaveRequest('/exams/exam-1/activate', {
        method: 'POST',
        successMessage: 'Examination activated.',
      })
    })

    expect(screen.getByText('Examination activated.')).toBeInTheDocument()
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('also confirms successful no-content mutations', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ status: 204 })))
    render(<ToastHost />)

    await act(async () => {
      await weaveRequest('/questions/question-1', {
        method: 'DELETE',
        successMessage: 'Unused question deleted.',
      })
    })

    expect(screen.getByText('Unused question deleted.')).toBeInTheDocument()
  })
})
