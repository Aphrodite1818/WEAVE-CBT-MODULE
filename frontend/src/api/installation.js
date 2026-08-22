import { leafRequest } from './client'

export function getInstallationStatus({ signal } = {}) {
  return leafRequest('/installation/status', { signal, staffAuth: false })
}

export function pairInstallation({ pairingCode, serverName }) {
  return leafRequest('/installation/pair', {
    method: 'POST',
    staffAuth: false,
    body: { pairing_code: pairingCode, server_name: serverName },
  })
}
