import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { BrowserRouter } from 'react-router-dom'
import StudentApp from '../src/app/StudentApp'
import { studentGateway } from '../src/app/studentGateway'
import { heartbeatCurrentAttempt } from '../src/api/studentAttempts'

afterEach(() => vi.unstubAllGlobals())

it('exposes the real heartbeat endpoint in the student gateway', () => {
  expect(studentGateway.attempts.heartbeatCurrentAttempt).toBe(heartbeatCurrentAttempt)
})

it('logs out a suspended student and retains the explanation modal after navigation', async () => {
  window.history.replaceState({}, '', '/student')
  window.localStorage.clear()
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
  HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); this.dispatchEvent(new Event('close')) }
  const reply = (body) => Promise.resolve(new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  const fetchMock = vi.fn((url, options = {}) => {
    const path = new URL(url, 'http://localhost').pathname
    if (path.endsWith('/installation/status')) return reply({ configured: true, tenant_name: 'School', server_name: 'Hall 1' })
    if (path.endsWith('/branding')) return reply({ school_name: 'School', is_enabled: false })
    if (path.endsWith('/student/auth/status')) return reply({ availability: 'suspended', display_name: 'Ada', exam_id: 'exam', exam_title: 'English', status_message: 'The school has paused this examination.' })
    if (path.endsWith('/student/auth/logout') && options.method === 'POST') return reply({})
    return Promise.reject(new Error(`Unexpected request ${path}`))
  })
  vi.stubGlobal('fetch', fetchMock)
  render(<BrowserRouter><StudentApp /></BrowserRouter>)
  await waitFor(() => expect(fetchMock.mock.calls.some(([url, options]) => String(url).endsWith('/student/auth/logout') && options.method === 'POST')).toBe(true))
  const modal = await screen.findByRole('dialog', { name: 'Exam currently suspended' })
  await waitFor(() => expect(window.location.pathname).toBe('/'))
  expect(modal).toHaveTextContent('The school has paused this examination.')
  expect(modal).toHaveTextContent('You have been signed out')
  fireEvent.click(screen.getByRole('button', { name: 'Understood' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
})
