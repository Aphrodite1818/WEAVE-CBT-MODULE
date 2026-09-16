import { useEffect, useState } from 'react'
import { Icon } from '../../shared/icons/Icon'
import { DashboardAccountMenu, DashboardSchoolIdentity } from '../../shared/ui'
import { getLocalBrandLogoSrc } from '../../api/branding'

function teacherNavActive(current, section) {
  if (section === 'question-banks') return current === 'question-banks' || current === 'bank-detail'
  if (section === 'questions') return current === 'questions' || current === 'create-question' || current === 'edit-question'
  if (section === 'exams') return current === 'exams' || current === 'create-exam'
  return current === section
}

export function TeacherLayout({ state, dispatch, signOut, children }) {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const actor = state.session?.actor
  const teacherName = actor?.display_name || state.session?.name || 'Teacher'
  const teacherRole = actor?.role || 'teacher'
  const schoolName = state.branding?.school_name || state.installation?.status?.tenant_name || 'Weave CBT'
  const serverName = state.installation?.status?.server_name || 'Local node'
  const schoolLogoSrc = getLocalBrandLogoSrc(state.branding)
  const nav = [
    ['overview', 'home', 'Overview'],
    ['question-banks', 'bank', 'Question Banks'],
    ['questions', 'fileText', 'Questions'],
    ['exams', 'calendar', 'Exams'],
  ]

  useEffect(() => {
    const className = 'teacher-dashboard-active'
    document.documentElement.classList.add(className)
    document.body.classList.add(className)
    return () => {
      document.documentElement.classList.remove(className)
      document.body.classList.remove(className)
    }
  }, [])

  return (
    <main className={`teacher-shell${sidebarOpen ? '' : ' teacher-shell--collapsed'}`}>
      <aside className="teacher-sidebar">
        <div className="teacher-sidebar__header">
          <div className="school-card">
            <span>{schoolLogoSrc ? <img className="school-brand-logo" src={schoolLogoSrc} alt="School logo" /> : <Icon name="school" size={20} />}</span>
            <div><strong>{schoolName}</strong><small>{serverName}</small></div>
          </div>
          <button className="dashboard-sidebar-toggle" type="button" aria-label={sidebarOpen ? 'Collapse sidebar' : 'Open sidebar'} aria-expanded={sidebarOpen} onClick={() => setSidebarOpen((open) => !open)}>
            <Icon name={sidebarOpen ? 'back' : 'menu'} size={18} />
          </button>
        </div>
        <nav aria-label="Teacher navigation">
          {nav.map(([section, icon, label]) => (
            <button key={section} className={teacherNavActive(state.staff.section, section) ? 'active' : ''} onClick={() => dispatch({ type: 'staff', patch: { section } })} title={sidebarOpen ? undefined : label}>
              <Icon name={icon} size={17} /><span>{label}</span>
            </button>
          ))}
        </nav>
      </aside>

      <section className="teacher-main">
        <header className="teacher-topbar">
          <DashboardSchoolIdentity schoolName={schoolName} logoSrc={schoolLogoSrc} />

          <div className="teacher-topbar__actions">
            <DashboardAccountMenu actor={actor} fallbackName={teacherName} roleLabel={teacherRole} onSignOut={signOut} />
          </div>
        </header>
        <div className="teacher-content">{children}</div>
      </section>
    </main>
  )
}
