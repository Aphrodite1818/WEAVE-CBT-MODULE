import {
  clearStaffAccessToken,
  setStaffAccessToken,
  weaveRequest,
} from './client'

const STAFF_REFRESH_OPERATION_KEY = 'weave.staffRefreshOperationId'
const REFRESH_EARLY_MS = 5 * 60 * 1000
const REFRESH_JITTER_MS = 60 * 1000
const REFRESH_RETRY_MS = 30 * 1000

let refreshTimer = null
let refreshInFlight = null

function normalizeStaffSession(session) {
  return {
    type: 'staff',
    role: session.actor.role,
    name: session.actor.display_name,
    actor: session.actor,
    accessTokenExpiresAt: session.access_token_expires_at,
    sessionExpiresAt: session.session_expires_at,
    cloudAuthState: session.cloud_auth_state,
  }
}

function pendingRefreshOperationId() {
  const existing = window.localStorage.getItem(STAFF_REFRESH_OPERATION_KEY)
  if (existing) return existing

  const operationId = window.crypto.randomUUID()
  window.localStorage.setItem(STAFF_REFRESH_OPERATION_KEY, operationId)
  return operationId
}

function clearPendingRefreshOperation() {
  window.localStorage.removeItem(STAFF_REFRESH_OPERATION_KEY)
}

function clearRefreshTimer() {
  if (refreshTimer !== null) {
    window.clearTimeout(refreshTimer)
    refreshTimer = null
  }
}

function scheduleStaffRefresh(accessTokenExpiresAt) {
  clearRefreshTimer()

  const expiresAt = Date.parse(accessTokenExpiresAt || '')
  if (!Number.isFinite(expiresAt)) return

  const jitter = Math.floor(Math.random() * REFRESH_JITTER_MS)
  const targetAt = expiresAt - REFRESH_EARLY_MS - jitter
  const delay = Math.max(1000, targetAt - Date.now())

  refreshTimer = window.setTimeout(() => {
    refreshTimer = null
    runScheduledRefresh()
  }, delay)
}

function scheduleRefreshRetry() {
  clearRefreshTimer()
  refreshTimer = window.setTimeout(() => {
    refreshTimer = null
    runScheduledRefresh()
  }, REFRESH_RETRY_MS)
}

async function runScheduledRefresh() {
  try {
    await refreshStaff()
  } catch (error) {
    if (error?.status === 401) {
      clearStaffSession()
      window.location.assign('/staff/login')
      return
    }

    // A transient local-server/coordination failure should not turn into a
    // logout. Keep the same pending idempotency key and retry shortly.
    scheduleRefreshRetry()
  }
}

export async function loginStaff({ email, password }) {
  const session = await weaveRequest('/auth/login', {
    method: 'POST',
    staffAuth: false,
    body: { email, password },
  })

  clearPendingRefreshOperation()
  setStaffAccessToken(session.access_token)
  scheduleStaffRefresh(session.access_token_expires_at)
  return normalizeStaffSession(session)
}

export async function refreshStaff() {
  if (refreshInFlight) return refreshInFlight

  const operationId = pendingRefreshOperationId()
  refreshInFlight = weaveRequest('/auth/refresh', {
    method: 'POST',
    staffAuth: false,
    headers: { 'Idempotency-Key': operationId },
  })
    .then((session) => {
      setStaffAccessToken(session.access_token)
      clearPendingRefreshOperation()
      scheduleStaffRefresh(session.access_token_expires_at)
      return normalizeStaffSession(session)
    })
    .catch((error) => {
      if (error?.status === 401) {
        clearStaffAccessToken()
        clearPendingRefreshOperation()
        clearRefreshTimer()
      }
      throw error
    })
    .finally(() => {
      refreshInFlight = null
    })

  return refreshInFlight
}

export async function signOutStaff() {
  try {
    await weaveRequest('/auth/logout', { method: 'POST', staffAuth: false })
  } finally {
    clearStaffSession()
  }
}

export function clearStaffSession() {
  clearRefreshTimer()
  clearPendingRefreshOperation()
  clearStaffAccessToken()
}
