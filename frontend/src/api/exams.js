import { queryString, weaveRequest } from './client'

export function listExams(params = {}, options = {}) {
  return weaveRequest(`/exams${queryString(params)}`, options)
}

export function getExam(examId, options = {}) {
  return weaveRequest(`/exams/${examId}`, options)
}

export function createExam(payload) {
  return weaveRequest('/exams', { method: 'POST', body: payload })
}

export function updateExam(examId, payload) {
  return weaveRequest(`/exams/${examId}`, { method: 'PATCH', body: payload })
}

export function configureExamQuestions(examId, payload) {
  return weaveRequest(`/exams/${examId}/questions/configuration`, { method: 'PUT', body: payload })
}

export const submitExam = (examId) => weaveRequest(`/exams/${examId}/submit`, { method: 'POST' })
export const returnExamToDraft = (examId) => weaveRequest(`/exams/${examId}/return-to-draft`, { method: 'POST' })
export const deleteDraftExam = (examId) => weaveRequest(`/exams/${examId}`, { method: 'DELETE' })
export const sealExam = (examId) => weaveRequest(`/exams/${examId}/seal`, { method: 'POST' })
export const createRevision = (examId) => weaveRequest(`/exams/${examId}/revisions`, { method: 'POST' })
export const activateExam = (examId) => weaveRequest(`/exams/${examId}/activate`, { method: 'POST' })
export const closeExam = (examId) => weaveRequest(`/exams/${examId}/close`, { method: 'POST' })

export function suspendExam(examId, reason) {
  return weaveRequest(`/exams/${examId}/suspend`, { method: 'POST', body: { reason } })
}

export function resumeExam(examId, reason) {
  return weaveRequest(`/exams/${examId}/resume`, { method: 'POST', body: reason ? { reason } : {} })
}

export function cancelExam(examId, reason) {
  return weaveRequest(`/exams/${examId}/cancel`, { method: 'POST', body: { reason } })
}

export const listAvailableInvigilators = () => weaveRequest('/exams/invigilators/available')
export const listExamInvigilators = (examId) => weaveRequest(`/exams/${examId}/invigilators`)

export function assignExamInvigilators(examId, teacherIds) {
  return weaveRequest(`/exams/${examId}/invigilators`, { method: 'POST', body: { teacher_ids: teacherIds } })
}

export function removeExamInvigilators(examId, teacherIds) {
  return weaveRequest(`/exams/${examId}/invigilators/remove`, { method: 'POST', body: { teacher_ids: teacherIds } })
}

export function addManualQuestions(examId, questionIds) {
  return weaveRequest(`/exams/${examId}/manual-questions`, { method: 'POST', body: { question_ids: questionIds } })
}

export function removeManualQuestion(examId, questionId) {
  return weaveRequest(`/exams/${examId}/manual-questions/remove`, { method: 'POST', body: { question_id: questionId } })
}

export function reorderManualQuestions(examId, questionIds) {
  return weaveRequest(`/exams/${examId}/manual-questions/reorder`, { method: 'POST', body: { question_ids: questionIds } })
}
