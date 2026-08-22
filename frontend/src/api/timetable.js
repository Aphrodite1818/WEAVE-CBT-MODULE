import { leafRequest } from './client'

export function startBatch(examIds) {
  return leafRequest('/exams/start-batch', { method: 'POST', body: { exam_ids: examIds } })
}

export function getTimetableImpact(examId, options = {}) {
  return leafRequest(`/exams/${examId}/timetable-impact`, options)
}
