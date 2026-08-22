import { leafRequest, queryString } from './client'

export const getSyncStatus = (options = {}) => leafRequest('/sync/status', options)

export function reconcileSync({ forceFull = false } = {}) {
  return leafRequest(`/sync/reconcile${queryString({ force_full: forceFull })}`, { method: 'POST' })
}
