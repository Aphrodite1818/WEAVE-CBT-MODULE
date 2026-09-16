import { weaveBlobRequest, weaveRequest, queryString } from './client'

export function createQuestionBank(curriculumSubjectId, payload) {
  return weaveRequest(`/questions/banks/${curriculumSubjectId}`, { method: 'POST', body: payload })
}

export const listAuthorableQuestionBanks = () => weaveRequest('/questions/banks/authorable')

export function listAdminQuestionBanks(params = {}, options = {}) {
  return weaveRequest(`/questions/banks${queryString(params)}`, options)
}

export function updateQuestionBank(bankId, payload) {
  return weaveRequest(`/questions/banks/${bankId}`, { method: 'PATCH', body: payload })
}

export const archiveQuestionBank = (bankId) => weaveRequest(`/questions/banks/${bankId}/archive`, { method: 'POST' })
export const reactivateQuestionBank = (bankId) => weaveRequest(`/questions/banks/${bankId}/reactivate`, { method: 'POST' })
export const deleteEmptyQuestionBank = (bankId) => weaveRequest(`/questions/banks/${bankId}`, { method: 'DELETE' })

export function createSingleChoiceQuestion(bankId, payload) {
  return weaveRequest(`/questions/banks/${bankId}/single-choice`, { method: 'POST', body: payload })
}

export function createMultipleChoiceQuestion(bankId, payload) {
  return weaveRequest(`/questions/banks/${bankId}/multiple-choice`, { method: 'POST', body: payload })
}

export function listQuestionsForBank(bankId, params = {}, options = {}) {
  return weaveRequest(`/questions/banks/${bankId}/items${queryString(params)}`, options)
}

export const getQuestion = (questionId) => weaveRequest(`/questions/${questionId}`)

export function updateQuestion(questionId, payload) {
  return weaveRequest(`/questions/${questionId}`, { method: 'PATCH', body: payload })
}

export const archiveQuestion = (questionId) => weaveRequest(`/questions/${questionId}/archive`, { method: 'POST' })
export const reactivateQuestion = (questionId) => weaveRequest(`/questions/${questionId}/reactivate`, { method: 'POST' })
export const deleteUnusedQuestion = (questionId) => weaveRequest(`/questions/${questionId}`, { method: 'DELETE' })

export const getQuestionImage = (questionId, options = {}) => weaveBlobRequest(`/questions/${questionId}/image`, options)

export const getQuestionOptionImage = (questionId, optionId, options = {}) => (
  weaveBlobRequest(`/questions/${questionId}/options/${optionId}/image`, options)
)

export function questionImageUrl(questionId) {
  return `${import.meta.env.VITE_WEAVE_API_BASE_URL || '/api/v1'}/questions/${questionId}/image`
}
