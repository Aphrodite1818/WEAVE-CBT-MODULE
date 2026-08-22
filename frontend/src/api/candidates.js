import { leafRequest, queryString } from './client'

export function listExamRoster(examId, params = {}, options = {}) {
  return leafRequest(`/exams/${examId}/candidates${queryString(params)}`, options)
}

export function getCandidate(candidateId, options = {}) {
  return leafRequest(`/candidates/${candidateId}`, options)
}

export function blockCandidate(candidateId, reason) {
  return leafRequest(`/candidates/${candidateId}/block`, {
    method: 'POST',
    body: { reason },
  })
}

export function unblockCandidate(candidateId) {
  return leafRequest(`/candidates/${candidateId}/unblock`, { method: 'POST' })
}

export function grantLateStart(candidateId, payload) {
  return leafRequest(`/candidates/${candidateId}/late-start-authorizations`, {
    method: 'POST',
    body: payload,
  })
}

export function listLateStartAuthorizations(candidateId, options = {}) {
  return leafRequest(`/candidates/${candidateId}/late-start-authorizations`, options)
}

export function revokeLateStart(authorizationId, reason) {
  return leafRequest(`/late-start-authorizations/${authorizationId}/revoke`, {
    method: 'POST',
    body: { reason },
  })
}
