import { weaveRequest, queryString } from './client'

export function listMissedCandidates(examId, params = {}, options = {}) {
  return weaveRequest(`/exams/${examId}/missed-candidates${queryString(params)}`, options)
}

export function approveMakeup(candidateId, reason) {
  return weaveRequest(`/candidates/${candidateId}/makeup-authorizations`, {
    method: 'POST',
    body: { reason },
  })
}

export function listMakeupAuthorizations(candidateId, options = {}) {
  return weaveRequest(`/candidates/${candidateId}/makeup-authorizations`, options)
}

export function revokeMakeup(authorizationId, reason) {
  return weaveRequest(`/makeup-authorizations/${authorizationId}/revoke`, {
    method: 'POST',
    body: { reason },
  })
}
