import { weaveRequest, queryString } from './client'

export function listExamRoster(examId, params = {}, options = {}) {
  return weaveRequest(`/exams/${examId}/candidates${queryString(params)}`, options)
}

export function getCandidate(candidateId, options = {}) {
  return weaveRequest(`/candidates/${candidateId}`, options)
}

export function blockCandidate(candidateId, reason) {
  return weaveRequest(`/candidates/${candidateId}/block`, {
    method: 'POST',
    body: { reason },
  })
}

export function unblockCandidate(candidateId) {
  return weaveRequest(`/candidates/${candidateId}/unblock`, { method: 'POST' })
}

export function grantLateStart(candidateId, payload) {
  return weaveRequest(`/candidates/${candidateId}/late-start-authorizations`, {
    method: 'POST',
    body: payload,
  })
}

export function listLateStartAuthorizations(candidateId, options = {}) {
  return weaveRequest(`/candidates/${candidateId}/late-start-authorizations`, options)
}

export function revokeLateStart(authorizationId, reason) {
  return weaveRequest(`/late-start-authorizations/${authorizationId}/revoke`, {
    method: 'POST',
    body: { reason },
  })
}
