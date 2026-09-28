import { useState } from 'react'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { StudentWorkspace } from '../src/features/student/StudentWorkspace'

function setup({ suspended = false, save, stage = 'active', availability = 'ready', onSuspended = vi.fn() } = {}) {
  const question = { id: 'q1', prompt: 'First question', question_type: 'single_choice', selected_option_ids: ['a'], is_flagged: false, mutation_sequence: 1, options: [{ id: 'a', text: 'First answer' }, { id: 'b', text: 'Second answer' }] }
  const attempt = { id: 'attempt', exam_title: 'English exam', status: 'in_progress', time_limit_seconds: 2700, remaining_seconds: 2700, exam_suspended: suspended, questions: [question, { ...question, id: 'q2', prompt: 'Second question', selected_option_ids: [] }] }
  const gateway = { auth: { getStudentStatus: vi.fn().mockResolvedValue({ availability, exam_id: 'exam', status_message: 'Please wait for your invigilator.' }) }, attempts: {
    getCurrentAttempt: vi.fn().mockResolvedValue(attempt),
    startCurrentAttempt: vi.fn().mockResolvedValue(attempt),
    heartbeatCurrentAttempt: vi.fn().mockResolvedValue({ status: 'in_progress', remaining_seconds: 2700, exam_suspended: suspended, next_heartbeat_after_seconds: 20 }),
    saveCurrentAnswer: save || vi.fn(async (_id, payload) => ({ ...payload, remaining_seconds: 2699 })),
  } }
  function Harness() {
    const [exam, setExam] = useState({ stage, index: 0 })
    return <StudentWorkspace exam={exam} resolution={{ state: 'ready', exam: { id: 'exam', title: 'English exam' }, candidate: { name: 'Ada' } }} onExamSuspended={onSuspended} serverName="Debright hall server 1" gateway={gateway} dispatch={({ patch }) => setExam((current) => ({ ...current, ...patch }))} returnToSignIn={vi.fn()} branding={{ school_name: 'Debright college', is_enabled: true, logo_path: 'school.png', logo_revision: '3' }} />
  }
  render(<Harness />)
  return gateway
}

afterEach(() => vi.useRealTimers())

it('uses school branding and clean navigation labels', async () => {
  setup()
  await screen.findByText('First question')
  expect(screen.getByText('Debright college')).toBeInTheDocument()
  expect(screen.getByText('Debright hall server 1')).toBeInTheDocument()
  expect(screen.getByRole('heading', { level: 1, name: 'English exam' })).toBeInTheDocument()
  expect(document.querySelector('.student-avatar')).toHaveTextContent('A')
  expect(screen.queryByText('(AD)')).not.toBeInTheDocument()
  expect(document.querySelector('.dashboard-school-identity img').src).toContain('/branding/logo?v=3')
  expect(screen.queryByText('Normal examination')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Save and next' })).toBeInTheDocument()
})

it('counts down between heartbeats and resynchronizes with the server', async () => {
  vi.useFakeTimers()
  const gateway = setup()
  await act(async () => { await Promise.resolve() })
  expect(screen.getByText('45:00')).toBeInTheDocument()
  await act(async () => { await vi.advanceTimersByTimeAsync(3000) })
  expect(screen.getByText('44:57')).toBeInTheDocument()
  gateway.attempts.heartbeatCurrentAttempt.mockResolvedValue({ status: 'in_progress', remaining_seconds: 2670, exam_suspended: false, next_heartbeat_after_seconds: 20 })
  await act(async () => { await vi.advanceTimersByTimeAsync(17000) })
  expect(screen.getByText('44:30')).toBeInTheDocument()
})

it('blocks a suspended restored attempt and requests logout once', async () => {
  const onSuspended = vi.fn()
  setup({ suspended: true, onSuspended })
  await screen.findByRole('heading', { name: 'Exam currently suspended' })
  expect(screen.queryByText('First question')).not.toBeInTheDocument()
  expect(onSuspended).toHaveBeenCalledOnce()
})

it('persists review flags without replacing answers and shows them across navigation', async () => {
  const gateway = setup()
  const mark = await screen.findByRole('checkbox', { name: 'Mark for review' })
  fireEvent.click(mark)
  await waitFor(() => expect(mark).not.toBeDisabled())
  expect(gateway.attempts.saveCurrentAnswer).toHaveBeenCalledWith('q1', { mutation_sequence: 2, selected_option_ids: ['a'], is_flagged: true })
  expect(screen.getByRole('button', { name: 'Question 1, marked for review' })).toHaveClass('flagged')
  fireEvent.click(screen.getByRole('button', { name: 'Save and next' }))
  expect(screen.getByRole('button', { name: 'Question 1, marked for review' })).toHaveClass('flagged')
  fireEvent.click(screen.getByRole('button', { name: 'Previous' }))
  expect(screen.getByRole('checkbox', { name: 'Mark for review' })).toBeChecked()
  fireEvent.click(screen.getByRole('checkbox', { name: 'Mark for review' }))
  await waitFor(() => expect(screen.getByRole('checkbox', { name: 'Mark for review' })).not.toBeDisabled())
  expect(screen.getByRole('button', { name: 'Question 1' })).not.toHaveClass('flagged')
})

it('rolls back review marking when saving fails', async () => {
  setup({ save: vi.fn().mockRejectedValue(new Error('offline')) })
  fireEvent.click(await screen.findByRole('checkbox', { name: 'Mark for review' }))
  await waitFor(() => expect(screen.getByRole('checkbox', { name: 'Mark for review' })).not.toBeChecked())
  expect(screen.getByRole('button', { name: 'Question 1' })).not.toHaveClass('flagged')
})


it('detects suspension during a live heartbeat and removes exam controls', async () => {
  vi.useFakeTimers()
  const onSuspended = vi.fn()
  const gateway = setup({ onSuspended })
  await act(async () => { await Promise.resolve() })
  expect(screen.getByText('First question')).toBeInTheDocument()
  gateway.attempts.heartbeatCurrentAttempt.mockResolvedValue({ status: 'in_progress', remaining_seconds: 2680, exam_suspended: true, next_heartbeat_after_seconds: 20 })
  await act(async () => { await vi.advanceTimersByTimeAsync(20000) })
  expect(onSuspended).toHaveBeenCalledOnce()
  expect(screen.queryByText('First question')).not.toBeInTheDocument()
  await act(async () => { await vi.advanceTimersByTimeAsync(20000) })
  expect(gateway.attempts.heartbeatCurrentAttempt).toHaveBeenCalledTimes(2)
})

it('checks live availability before starting an active exam', async () => {
  const gateway = setup({ stage: 'lobby' })
  fireEvent.click(screen.getByRole('button', { name: /Start Exam/ }))
  await screen.findByText('First question')
  expect(gateway.auth.getStudentStatus).toHaveBeenCalledOnce()
  expect(gateway.attempts.startCurrentAttempt).toHaveBeenCalledOnce()
  expect(gateway.auth.getStudentStatus.mock.invocationCallOrder[0]).toBeLessThan(gateway.attempts.startCurrentAttempt.mock.invocationCallOrder[0])
})

it('does not start an exam that has become suspended', async () => {
  const onSuspended = vi.fn()
  const gateway = setup({ stage: 'lobby', availability: 'suspended', onSuspended })
  fireEvent.click(screen.getByRole('button', { name: /Start Exam/ }))
  await waitFor(() => expect(onSuspended).toHaveBeenCalledOnce())
  expect(gateway.attempts.startCurrentAttempt).not.toHaveBeenCalled()
  expect(screen.queryByText('First question')).not.toBeInTheDocument()
})

it('handles suspension between the availability check and the start request', async () => {
  const onSuspended = vi.fn()
  const gateway = setup({ stage: 'lobby', onSuspended })
  gateway.attempts.startCurrentAttempt.mockRejectedValue(new Error('suspended'))
  gateway.auth.getStudentStatus.mockResolvedValueOnce({ availability: 'ready', exam_id: 'exam' }).mockResolvedValue({ availability: 'suspended', exam_id: 'exam', status_message: 'Exam paused.' })
  fireEvent.click(screen.getByRole('button', { name: /Start Exam/ }))
  await waitFor(() => expect(onSuspended).toHaveBeenCalledWith('Exam paused.'))
  expect(screen.queryByText('First question')).not.toBeInTheDocument()
})

it('does not start if the availability check fails', async () => {
  const gateway = setup({ stage: 'lobby' })
  gateway.auth.getStudentStatus.mockRejectedValue(new Error('offline'))
  fireEvent.click(screen.getByRole('button', { name: /Start Exam/ }))
  await waitFor(() => expect(screen.getByRole('button', { name: /Start Exam/ })).not.toBeDisabled())
  expect(gateway.attempts.startCurrentAttempt).not.toHaveBeenCalled()
})
