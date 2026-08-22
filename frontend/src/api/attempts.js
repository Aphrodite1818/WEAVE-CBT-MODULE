import { leafRequest } from './client'

export const startCurrentAttempt = () => leafRequest('/student/attempts/current/start', { method: 'POST', staffAuth: false })
export const getCurrentAttempt = () => leafRequest('/student/attempts/current', { staffAuth: false })
export const submitCurrentAttempt = () => leafRequest('/student/attempts/current/submit', { method: 'POST', staffAuth: false })

export function saveCurrentAnswer(attemptQuestionId, payload) {
  return leafRequest(`/student/attempts/current/questions/${attemptQuestionId}/answer`, {
    method: 'PUT',
    staffAuth: false,
    body: payload,
  })
}

export function interruptAttempt(attemptId, reason) {
  return leafRequest(`/attempts/${attemptId}/interrupt`, { method: 'POST', body: { reason } })
}

export function resumeAttempt(attemptId, reason) {
  return leafRequest(`/attempts/${attemptId}/resume`, { method: 'POST', body: { reason } })
}

export function terminateAttempt(attemptId, reason) {
  return leafRequest(`/attempts/${attemptId}/terminate`, { method: 'POST', body: { reason } })
}
