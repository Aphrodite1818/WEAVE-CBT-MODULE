import { useEffect, useState } from 'react'
import { AppRouter } from './routes/AppRouter'

const CONFIG_KEY = 'weave-cbt-prototype-configured'

function getPath() {
  return window.location.pathname === '/' ? '/setup' : window.location.pathname
}

export default function App() {
  const [path, setPath] = useState(getPath)
  const [configured, setConfigured] = useState(
    () => window.localStorage.getItem(CONFIG_KEY) === 'true',
  )
  const [staffRole, setStaffRole] = useState(null)

  useEffect(() => {
    const onPopState = () => setPath(getPath())
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  const navigate = (nextPath) => {
    window.history.pushState({}, '', nextPath)
    setPath(nextPath)
    window.scrollTo({ top: 0, behavior: 'instant' })
  }

  const completeSetup = () => {
    window.localStorage.setItem(CONFIG_KEY, 'true')
    setConfigured(true)
    navigate('/welcome')
  }

  const resetSetup = () => {
    window.localStorage.removeItem(CONFIG_KEY)
    setConfigured(false)
    navigate('/setup')
  }

  const loginStaff = (role) => {
    setStaffRole(role)
    navigate(role === 'admin' ? '/admin' : '/teacher')
  }

  const logoutStaff = () => {
    setStaffRole(null)
    navigate('/staff-login')
  }

  return (
    <AppRouter
      path={path}
      configured={configured}
      navigate={navigate}
      completeSetup={completeSetup}
      resetSetup={resetSetup}
      staffRole={staffRole}
      loginStaff={loginStaff}
      logoutStaff={logoutStaff}
    />
  )
}
