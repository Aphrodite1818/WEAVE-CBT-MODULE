import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import App from '../src/App'

describe('Weave CBT prototype', () => {
  beforeEach(() => {
    window.localStorage.clear()
    window.history.replaceState({}, '', '/')
  })

  it('starts with the installation flow when unconfigured', () => {
    render(<App />)

    expect(screen.getByRole('heading', { name: /connect this cbt workspace/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /verify & continue/i })).toBeInTheDocument()
  })

  it('completes setup and opens the main portal', async () => {
    render(<App />)

    fireEvent.change(screen.getByLabelText(/setup code/i), { target: { value: 'WCBT-DEMO-2026' } })
    fireEvent.click(screen.getByRole('button', { name: /verify & continue/i }))

    expect(await screen.findByRole('heading', { name: /focused exams/i })).toBeInTheDocument()
    expect(window.localStorage.getItem('weave-cbt-prototype-configured')).toBe('true')
  })

  it('navigates from the portal to staff login', async () => {
    window.localStorage.setItem('weave-cbt-prototype-configured', 'true')
    window.history.replaceState({}, '', '/welcome')
    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: /staff login/i }))

    await waitFor(() => expect(screen.getByRole('heading', { name: /welcome back/i })).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /sign in as admin/i })).toBeInTheDocument()
  })
})
