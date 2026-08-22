import { leafRequest, queryString } from './client'

export function listExamResults(examId, params = {}, options = {}) {
  return leafRequest(`/exams/${examId}/results${queryString(params)}`, options)
}

export function getResult(resultId, options = {}) {
  return leafRequest(`/results/${resultId}`, options)
}
