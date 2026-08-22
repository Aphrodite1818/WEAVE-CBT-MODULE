import { leafRequest, queryString } from './client'

export function listMissedCandidates(examId, params = {}, options = {}) {
  return leafRequest(`/exams/${examId}/missed-candidates${queryString(params)}`, options)
}

export function approveMakeup(candidateId, reason) {
  return leafRequest(`/candidates/${candidateId}/makeup-authorizations`, {
    method: 'POST',
    body: { reason },
  })
}

export function listMakeupAuthorizations(candidateId, options = {}) {
  return leafRequest(`/candidates/${candidateId}/makeup-authorizations`, options)
}

export function revokeMakeup(authorizationId, reason) {
  return leafRequest(`/makeup-authorizations/${authorizationId}/revoke`, {
    method: 'POST',
    body: { reason },
  })
}
