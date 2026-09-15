import { useEffect, useState } from 'react'
import { Pictogram } from '../../shared/icons/Pictogram'
import { WeaveMark } from '../../shared/ui'
import './landing.css'

const WORDMARK_TEXT = 'Weave'
const TYPEWRITER_CHAR_DELAY_MS = 145
const TYPEWRITER_PAUSE_MS = 3200
const BOOK_OPEN_DELAY_MS = 760

function LandingWordmarkTypewriter() {
  const [loopKey, setLoopKey] = useState(0)

  useEffect(() => {
    const typingMs = WORDMARK_TEXT.length * TYPEWRITER_CHAR_DELAY_MS + 10
    let timeoutId
    const loop = () => {
      setLoopKey((key) => key + 1)
      timeoutId = setTimeout(loop, typingMs + TYPEWRITER_PAUSE_MS)
    }
    timeoutId = setTimeout(loop, typingMs + TYPEWRITER_PAUSE_MS)
    return () => clearTimeout(timeoutId)
  }, [])

  return (
    <div key={loopKey} className="landing-wordmark weave-logo large" aria-label={WORDMARK_TEXT}>
      {Array.from(WORDMARK_TEXT).map((character, index) => (
        <span
          key={`${character}-${index}`}
          aria-hidden="true"
          className="landing-typewriter__char weave-logo__word"
          style={{ '--typing-delay': `${index * (TYPEWRITER_CHAR_DELAY_MS / 1000)}s` }}
        >
          {character}
        </span>
      ))}
    </div>
  )
}

export function LandingPage({ dispatch }) {
  const [openingKind, setOpeningKind] = useState('')

  useEffect(() => {
    if (!openingKind) return undefined

    const nextView = openingKind === 'student' ? 'student-login' : 'staff-login'
    const canReadMotionPreference = typeof window.matchMedia === 'function'
    const prefersReducedMotion = canReadMotionPreference
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches

    if (!canReadMotionPreference || prefersReducedMotion) {
      dispatch({ type: 'view', view: nextView })
      return undefined
    }

    const timeoutId = window.setTimeout(() => {
      dispatch({ type: 'view', view: nextView })
    }, BOOK_OPEN_DELAY_MS)

    return () => window.clearTimeout(timeoutId)
  }, [dispatch, openingKind])

  const openLogin = (kind) => {
    if (openingKind) return
    setOpeningKind(kind)
  }

  return (
    <main className={`landing-page${openingKind ? ` landing-page--opening landing-page--opening-${openingKind}` : ''}`}>
      <nav className="landing-nav" aria-label="Sign in">
        <button className="landing-primary" type="button" disabled={Boolean(openingKind)} onClick={() => openLogin('student')}>
          Login as Student <Pictogram name="student" size={18} />
        </button>
        <button
          className="landing-primary landing-primary--ghost"
          type="button"
          disabled={Boolean(openingKind)}
          onClick={() => openLogin('staff')}
        >
          Login as Staff <Pictogram name="staff" size={18} />
        </button>
      </nav>

      <section className="landing-center landing-enter" aria-label="Weave">
        <WeaveMark className="landing-mark" />
        <LandingWordmarkTypewriter />
      </section>

      {openingKind && (
        <div className="landing-page-turn" aria-hidden="true">
          <div className="landing-page-turn__sheet" />
        </div>
      )}
    </main>
  )
}
