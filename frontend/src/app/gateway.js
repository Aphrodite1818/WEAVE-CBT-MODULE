import { leafApi } from '../api'

export const leafGateway = {
  installation: leafApi.installation,
  auth: leafApi.auth,
  attempts: leafApi.attempts,
  candidates: leafApi.candidates,
  exams: leafApi.exams,
  makeups: leafApi.makeups,
  media: leafApi.media,
  questions: leafApi.questions,
  results: leafApi.results,
  sync: leafApi.sync,
  timetable: leafApi.timetable,
}
