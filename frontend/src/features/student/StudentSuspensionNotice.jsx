import { useEffect, useId, useRef } from 'react'
import { RiPauseCircleLine } from '@remixicon/react'
import './student.css'

export function StudentSuspensionNotice({ notice, onDismiss }) {
  const dialog = useRef(null)
  const titleId = useId()
  const descriptionId = useId()
  useEffect(() => {
    if (notice && !dialog.current.open) dialog.current.showModal()
    if (!notice && dialog.current.open) dialog.current.close()
  }, [notice])
  return <dialog ref={dialog} className="student-suspension-dialog" aria-labelledby={titleId} aria-describedby={descriptionId} onCancel={(event) => { event.preventDefault(); if (!notice?.signingOut) onDismiss() }}>
    {notice && <>
      <span className="student-suspension-dialog__icon"><RiPauseCircleLine size={32} aria-hidden="true" /></span>
      <h2 id={titleId}>Exam currently suspended</h2>
      <p id={descriptionId}>{notice.message || 'Your examination has been paused by the school. Your saved answers are protected. Wait for your invigilator to resume the exam before signing in again.'}</p>
      <p>{notice.signingOut ? 'Signing you out…' : 'You have been signed out of this session.'}</p>
      <button type="button" className="premium-btn-primary" disabled={notice.signingOut} onClick={onDismiss}>Understood</button>
    </>}
  </dialog>
}
