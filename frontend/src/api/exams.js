import { leafRequest } from './client'

export function getExam(examId, options = {}) {
  return leafRequest(`/exams/${examId}`, options)
}

export function createExam(payload) {
  return leafRequest('/exams', { method: 'POST', body: payload })
}

export function updateExam(examId, payload) {
  return leafRequest(`/exams/${examId}`, { method: 'PATCH', body: payload })
}

export function configureExamQuestions(examId, payload) {
  return leafRequest(`/exams/${examId}/questions/configuration`, { method: 'PUT', body: payload })
}

export const submitExam = (examId) => leafRequest(`/exams/${examId}/submit`, { method: 'POST' })
export const returnExamToDraft = (examId) => leafRequest(`/exams/${examId}/return-to-draft`, { method: 'POST' })
export const deleteDraftExam = (examId) => leafRequest(`/exams/${examId}`, { method: 'DELETE' })
export const sealExam = (examId) => leafRequest(`/exams/${examId}/seal`, { method: 'POST' })
export const createRevision = (examId) => leafRequest(`/exams/${examId}/revisions`, { method: 'POST' })
export const activateExam = (examId) => leafRequest(`/exams/${examId}/activate`, { method: 'POST' })
export const closeExam = (examId) => leafRequest(`/exams/${examId}/close`, { method: 'POST' })

export function suspendExam(examId, reason) {
  return leafRequest(`/exams/${examId}/suspend`, { method: 'POST', body: { reason } })
}

export function resumeExam(examId, reason) {
  return leafRequest(`/exams/${examId}/resume`, { method: 'POST', body: reason ? { reason } : {} })
}

export function cancelExam(examId, reason) {
  return leafRequest(`/exams/${examId}/cancel`, { method: 'POST', body: { reason } })
}

export const listAvailableInvigilators = () => leafRequest('/exams/invigilators/available')
export const listExamInvigilators = (examId) => leafRequest(`/exams/${examId}/invigilators`)

export function assignExamInvigilators(examId, teacherIds) {
  return leafRequest(`/exams/${examId}/invigilators`, { method: 'POST', body: { teacher_ids: teacherIds } })
}

export function removeExamInvigilators(examId, teacherIds) {
  return leafRequest(`/exams/${examId}/invigilators/remove`, { method: 'POST', body: { teacher_ids: teacherIds } })
}

export function addManualQuestions(examId, questionIds) {
  return leafRequest(`/exams/${examId}/manual-questions`, { method: 'POST', body: { question_ids: questionIds } })
}

export function removeManualQuestion(examId, questionId) {
  return leafRequest(`/exams/${examId}/manual-questions/remove`, { method: 'POST', body: { question_id: questionId } })
}

export function reorderManualQuestions(examId, questionIds) {
  return leafRequest(`/exams/${examId}/manual-questions/reorder`, { method: 'POST', body: { question_ids: questionIds } })
}
