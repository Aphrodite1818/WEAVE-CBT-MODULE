import { getBranding } from '../api/branding'
import { getInstallationStatus } from '../api/installation'
import {
  getStudentStatus,
  loginStudent,
  logoutStudent,
} from '../api/studentAuth'
import {
  getCurrentAttempt,
  heartbeatCurrentAttempt,
  getCurrentQuestionImage,
  getCurrentOptionImage,
  saveCurrentAnswer,
  startCurrentAttempt,
  submitCurrentAttempt,
} from '../api/studentAttempts'

export const studentGateway = {
  installation: {
    getInstallationStatus,
  },
  branding: {
    getBranding,
  },
  auth: {
    getStudentStatus,
    loginStudent,
    logoutStudent,
  },
  attempts: {
    getCurrentAttempt,
    heartbeatCurrentAttempt,
    getCurrentQuestionImage,
    getCurrentOptionImage,
    saveCurrentAnswer,
    startCurrentAttempt,
    submitCurrentAttempt,
  },
}
