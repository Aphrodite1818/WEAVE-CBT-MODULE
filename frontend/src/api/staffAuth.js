import { clearStaffAccessToken, setStaffAccessToken, weaveRequest } from './client'

export async function loginStaff({ email, password }) {
  const session = await weaveRequest('/auth/login', {
    method: 'POST',
    staffAuth: false,
    body: { email, password },
  })
  setStaffAccessToken(session.access_token)
  return { type: 'staff', role: session.actor.role, name: session.actor.display_name, actor: session.actor }
}

export async function refreshStaff() {
  const session = await weaveRequest('/auth/refresh', {
    method: 'POST',
    staffAuth: false,
  })
  setStaffAccessToken(session.access_token)
  return { type: 'staff', role: session.actor.role, name: session.actor.display_name, actor: session.actor }
}

export async function signOutStaff() {
  try {
    await weaveRequest('/auth/logout', { method: 'POST', staffAuth: false })
  } finally {
    clearStaffAccessToken()
  }
}

export function clearStaffSession() {
  clearStaffAccessToken()
}
