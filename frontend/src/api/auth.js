import { clearStaffAccessToken, weaveRequest, setStaffAccessToken } from './client'

export async function loginStaff({ email, password }) {
  const session = await weaveRequest('/auth/login', {
    method: 'POST',
    staffAuth: false,
    body: { email, password },
  })
  setStaffAccessToken(session.access_token)
  return { type: 'staff', role: session.actor.role, name: session.actor.display_name, actor: session.actor }
}

export async function loginStudent({ admissionNumber, pin }) {
  const session = await weaveRequest('/student/auth/login', {
    method: 'POST',
    staffAuth: false,
    body: { admission_number: admissionNumber, pin },
  })
  return { type: 'student', name: session.display_name, ...session }
}

export async function logoutStudent() {
  return weaveRequest('/student/auth/logout', { method: 'POST', staffAuth: false })
}

export function signOutStaff() {
  clearStaffAccessToken()
}
