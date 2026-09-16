import { weaveRequest } from './client'

export function interruptAttempt(attemptId, reason) {
  return weaveRequest(`/attempts/${attemptId}/interrupt`, { method: 'POST', body: { reason } })
}

export function resumeAttempt(attemptId, reason) {
  return weaveRequest(`/attempts/${attemptId}/resume`, { method: 'POST', body: { reason } })
}

export function terminateAttempt(attemptId, reason) {
  return weaveRequest(`/attempts/${attemptId}/terminate`, { method: 'POST', body: { reason } })
}
