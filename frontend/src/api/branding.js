import { leafRequest } from './client'

export function getBranding({ signal } = {}) {
  return leafRequest('/branding', { signal, staffAuth: false })
}
