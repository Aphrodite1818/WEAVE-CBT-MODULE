import { useEffect, useState } from 'react'
import {
  RiCheckboxCircleLine,
  RiCloseLine,
  RiErrorWarningLine,
  RiInformationLine,
} from '@remixicon/react'
import { toastBus } from './useToast'
import './toast.css'

const icons = {
  info: RiInformationLine,
  success: RiCheckboxCircleLine,
  warning: RiErrorWarningLine,
  error: RiErrorWarningLine,
}

function ToastCard({ toast, onClose }) {
  const ToastIcon = icons[toast.type] || icons.info

  useEffect(() => {
    const timeoutId = window.setTimeout(() => onClose(toast.id), toast.duration)
    return () => window.clearTimeout(timeoutId)
  }, [onClose, toast.duration, toast.id])

  return (
    <div
      className={`weave-toast weave-toast--${toast.type || 'info'}`}
      role={toast.type === 'error' ? 'alert' : 'status'}
      aria-live={toast.type === 'error' ? 'assertive' : 'polite'}
    >
      <ToastIcon className="weave-toast__icon" size={20} aria-hidden="true" />
      <p>{toast.message}</p>
      <button type="button" onClick={() => onClose(toast.id)} aria-label="Dismiss notification">
        <RiCloseLine size={17} aria-hidden="true" />
      </button>
    </div>
  )
}

export function ToastHost() {
  const [toasts, setToasts] = useState([])

  useEffect(() => toastBus.subscribe((nextToast) => {
    setToasts((current) => [...current, nextToast].slice(-4))
  }), [])

  const closeToast = (id) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }

  if (toasts.length === 0) return null

  return (
    <div className="weave-toast-host" aria-label="Notifications">
      {toasts.map((toast) => <ToastCard key={toast.id} toast={toast} onClose={closeToast} />)}
    </div>
  )
}
