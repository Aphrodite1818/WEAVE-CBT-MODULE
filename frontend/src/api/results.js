import { weaveRequest, queryString } from './client'

export function listExamResults(examId, params = {}, options = {}) {
  return weaveRequest(`/exams/${examId}/results${queryString(params)}`, options)
}

export function getResult(resultId, options = {}) {
  return weaveRequest(`/results/${resultId}`, options)
}

export function retryExamResultSync(examId, options = {}) {
  return weaveRequest(`/exams/${examId}/results/retry-sync`, {
    ...options,
    method: 'POST',
  })
}
