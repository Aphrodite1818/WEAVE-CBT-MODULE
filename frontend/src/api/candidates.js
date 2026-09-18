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
    successMessage: 'Candidate blocked from this examination.',
  })
}

export function unblockCandidate(candidateId) {
  return weaveRequest(`/candidates/${candidateId}/unblock`, {
    method: 'POST',
    successMessage: 'Candidate unblocked for this examination.',
  })
}

export function grantLateStart(candidateId, payload) {
  return weaveRequest(`/candidates/${candidateId}/late-start-authorizations`, {
    method: 'POST',
    body: payload,
    successMessage: 'Late-start authorization granted.',
  })
}

export function listLateStartAuthorizations(candidateId, options = {}) {
  return weaveRequest(`/candidates/${candidateId}/late-start-authorizations`, options)
}

export function revokeLateStart(authorizationId, reason) {
  return weaveRequest(`/late-start-authorizations/${authorizationId}/revoke`, {
    method: 'POST',
    body: { reason },
    successMessage: 'Late-start authorization revoked.',
  })
}
