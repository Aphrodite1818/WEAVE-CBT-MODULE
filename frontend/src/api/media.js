import { leafRequest } from './client'

export function uploadQuestionImage(file) {
  const body = new FormData()
  body.set('file', file)
  return leafRequest('/media/question-images', { method: 'POST', body, formData: true })
}
