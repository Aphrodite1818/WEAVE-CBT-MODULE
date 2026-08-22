import { leafRequest, queryString } from './client'

export function createQuestionBank(curriculumSubjectId, payload) {
  return leafRequest(`/questions/banks/${curriculumSubjectId}`, { method: 'POST', body: payload })
}

export const listAuthorableQuestionBanks = () => leafRequest('/questions/banks/authorable')

export function listAdminQuestionBanks(params = {}, options = {}) {
  return leafRequest(`/questions/banks${queryString(params)}`, options)
}

export function updateQuestionBank(bankId, payload) {
  return leafRequest(`/questions/banks/${bankId}`, { method: 'PATCH', body: payload })
}

export const archiveQuestionBank = (bankId) => leafRequest(`/questions/banks/${bankId}/archive`, { method: 'POST' })
export const reactivateQuestionBank = (bankId) => leafRequest(`/questions/banks/${bankId}/reactivate`, { method: 'POST' })
export const deleteEmptyQuestionBank = (bankId) => leafRequest(`/questions/banks/${bankId}`, { method: 'DELETE' })

export function createSingleChoiceQuestion(bankId, payload) {
  return leafRequest(`/questions/banks/${bankId}/single-choice`, { method: 'POST', body: payload })
}

export function createMultipleChoiceQuestion(bankId, payload) {
  return leafRequest(`/questions/banks/${bankId}/multiple-choice`, { method: 'POST', body: payload })
}

export function listQuestionsForBank(bankId, params = {}, options = {}) {
  return leafRequest(`/questions/banks/${bankId}/items${queryString(params)}`, options)
}

export const getQuestion = (questionId) => leafRequest(`/questions/${questionId}`)

export function updateQuestion(questionId, payload) {
  return leafRequest(`/questions/${questionId}`, { method: 'PATCH', body: payload })
}

export const archiveQuestion = (questionId) => leafRequest(`/questions/${questionId}/archive`, { method: 'POST' })
export const reactivateQuestion = (questionId) => leafRequest(`/questions/${questionId}/reactivate`, { method: 'POST' })
export const deleteUnusedQuestion = (questionId) => leafRequest(`/questions/${questionId}`, { method: 'DELETE' })

export function questionImageUrl(questionId) {
  return `${import.meta.env.VITE_LEAF_API_BASE_URL || '/api/v1'}/questions/${questionId}/image`
}
