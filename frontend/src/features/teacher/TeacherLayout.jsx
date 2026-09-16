import { useState } from 'react'
import { Icon } from '../../shared/icons/Icon'
import { getLocalBrandLogoSrc } from '../../api/branding'

function teacherNavActive(current, section) {
  if (section === 'question-banks') return current === 'question-banks' || current === 'bank-detail'
  if (section === 'questions') return current === 'questions' || current === 'create-question'
  if (section === 'exams') return current === 'exams' || current === 'create-exam'
  return current === section
}

export function TeacherLayout({ state, dispatch, signOut, children }) {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const teacherName = state.session?.actor?.display_name || state.session?.name || 'Teacher'
  const teacherRole = state.session?.actor?.role || 'teacher'
  const schoolName = state.branding?.school_name || state.installation?.status?.tenant_name || 'Weave CBT'
  const serverName = state.installation?.status?.server_name || 'Local node'
  const nav = [
    ['overview', 'home', 'Overview'],
    ['question-banks', 'database', 'Question Banks'],
    ['questions', 'fileText', 'Questions'],
    ['exams', 'calendar', 'Exams'],
  ]

  return (
    <main className={`teacher-shell${sidebarOpen ? '' : ' teacher-shell--collapsed'}`}>
      <aside className="teacher-sidebar">
        <div className="school-card">
          <span>{getLocalBrandLogoSrc(state.branding) ? <img className="school-brand-logo" src={getLocalBrandLogoSrc(state.branding)} alt="School logo" /> : <Icon name="school" size={20} />}</span>
          <div><strong>{schoolName}</strong><small>{serverName}</small></div>
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
          <button className="teacher-icon-button teacher-sidebar-toggle" type="button" aria-label={sidebarOpen ? 'Collapse sidebar' : 'Open sidebar'} aria-expanded={sidebarOpen} onClick={() => setSidebarOpen((open) => !open)}>
            <Icon name={sidebarOpen ? 'back' : 'menu'} size={19} />
          </button>
          <label className="teacher-search">
            <Icon name="search" size={18} />
            <input type="search" placeholder="Search anything..." />
          </label>
          <div className="teacher-topbar__actions">
            <button className="teacher-icon-button" type="button" aria-label="Notifications"><Icon name="bell" size={20} /></button>
            <div className="teacher-account">
              <span className="teacher-avatar">{initials(teacherName)}</span>
              <div><strong>{teacherName}</strong><small>{teacherRole}</small></div>
              <Icon name="chevronDown" size={18} />
              <div className="teacher-account__menu">
                <button type="button"><Icon name="profile" size={17} /> My Profile</button>
                <button type="button"><Icon name="settings" size={17} /> Account Settings</button>
                <button type="button" onClick={signOut}><Icon name="logout" size={17} /> Logout</button>
              </div>
            </div>
          </div>
        </header>
        <div className="teacher-content">{children}</div>
      </section>
    </main>
  )
}

function initials(name) {
  return name.split(' ').map((part) => part[0]).join('').slice(0, 2).toUpperCase()
}
