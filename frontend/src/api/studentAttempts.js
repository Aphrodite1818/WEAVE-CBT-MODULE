import { weaveRequest } from './client'

export const startCurrentAttempt = () => weaveRequest('/student/attempts/current/start', { method: 'POST', staffAuth: false })
export const getCurrentAttempt = () => weaveRequest('/student/attempts/current', { staffAuth: false })
export const submitCurrentAttempt = () => weaveRequest('/student/attempts/current/submit', { method: 'POST', staffAuth: false })

export function saveCurrentAnswer(attemptQuestionId, payload) {
  return weaveRequest(`/student/attempts/current/questions/${attemptQuestionId}/answer`, {
    method: 'PUT',
    staffAuth: false,
    body: payload,
  })
}
