import { weaveApi } from '../api'

export const weaveGateway = {
  installation: weaveApi.installation,
  branding: weaveApi.branding,
  auth: weaveApi.auth,
  attempts: weaveApi.attempts,
  candidates: weaveApi.candidates,
  exams: weaveApi.exams,
  makeups: weaveApi.makeups,
  media: weaveApi.media,
  questions: weaveApi.questions,
  results: weaveApi.results,
  sync: weaveApi.sync,
  timetable: weaveApi.timetable,
}
