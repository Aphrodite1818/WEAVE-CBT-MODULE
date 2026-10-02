import { useEffect, useRef, useState } from 'react'

export function StudentLogoutConfirmation({ children, onLogout }) {
  const [logoutRequested, setLogoutRequested] = useState(false)
  const dialogRef = useRef(null)

  useEffect(() => {
    if (logoutRequested) dialogRef.current?.showModal()
  }, [logoutRequested])

  return (
    <>
      {children(() => setLogoutRequested(true))}
      {logoutRequested && (
        <dialog
          ref={dialogRef}
          className="student-logout-dialog"
          aria-labelledby="student-logout-title"
          aria-describedby="student-logout-description"
          onCancel={() => setLogoutRequested(false)}
          onClose={() => setLogoutRequested(false)}
        >
          <h2 id="student-logout-title">Confirm logout</h2>
          <p id="student-logout-description">Are you sure you want to log out?</p>
          <div className="student-logout-dialog__actions">
            <button className="premium-btn-secondary" type="button" autoFocus onClick={() => setLogoutRequested(false)}>Cancel</button>
            <button className="premium-btn-primary" type="button" onClick={() => {
              setLogoutRequested(false)
              onLogout()
            }}>OK</button>
          </div>
        </dialog>
      )}
    </>
  )
}

