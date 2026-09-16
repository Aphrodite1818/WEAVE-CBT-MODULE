import { useState } from 'react'
import { Icon } from '../../shared/icons/Icon'
import { DashboardAccountMenu, DashboardSchoolIdentity } from '../../shared/ui'
import { getLocalBrandLogoSrc } from '../../api/branding'
import { AdminDashboard } from './pages/AdminDashboard'
import { ExamOperations } from './pages/ExamOperations'
import { InvigilatorPanel } from './pages/InvigilatorPanel'
import { QuestionBank } from './pages/QuestionBank'
import { ReportsPage } from './pages/ReportsPage'
import { ResultsPage } from './pages/ResultsPage'
import { SettingsPage } from './pages/SettingsPage'
import { StudentsView } from './pages/StudentsView'
import './admin.css'

const adminNav = [
  ['dashboard', 'Dashboard', 'dashboard'],
  ['exams', 'Exams', 'exams'],
  ['question-banks', 'Question Bank', 'book'],
  ['students', 'Students', 'users'],
  ['invigilators', 'Invigilators', 'shield'],
  ['results', 'Results', 'results'],
  ['reports', 'Reports', 'reports'],
  ['settings', 'Settings', 'settings'],
]

export function AdminWorkspace({ state, dispatch, signOut }) {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const section = state.staff.section === 'overview' ? 'dashboard' : state.staff.section
  const actor = state.session?.actor
  const adminName = actor?.display_name || state.session?.name || 'Administrator'
  const schoolName = state.branding?.school_name || state.installation?.status?.tenant_name || 'Weave CBT'
  const serverName = state.installation?.status?.server_name || 'Local CBT server'
  const schoolLogoSrc = getLocalBrandLogoSrc(state.branding)

  const handleNavClick = (item) => {
    dispatch({ type: 'staff', patch: { section: item } })
  }

  return (
    <div className={`premium-admin-shell${sidebarOpen ? '' : ' premium-admin-shell--collapsed'}`}>
      <aside className="premium-sidebar">
        <div className="premium-sidebar__header">
          <div className="premium-school-badge">
            <div className="school-icon">{schoolLogoSrc ? <img src={schoolLogoSrc} alt="School logo" /> : <Icon name="school" size={22} />}</div>
            <div className="school-info">
              <strong>{schoolName}</strong>
              <small>{serverName}</small>
            </div>
          </div>
          <button className="dashboard-sidebar-toggle" type="button" aria-label={sidebarOpen ? 'Collapse sidebar' : 'Open sidebar'} aria-expanded={sidebarOpen} onClick={() => setSidebarOpen((open) => !open)}>
            <Icon name={sidebarOpen ? 'back' : 'menu'} size={18} />
          </button>
        </div>

        <nav className="premium-nav" aria-label="Admin navigation">
          {adminNav.map(([item, label, icon]) => (
            <button key={item} className={section === item ? 'active' : ''} onClick={() => handleNavClick(item)}>
              <Icon name={icon} size={20} />
              <span>{label}</span>
            </button>
          ))}
        </nav>

        <div className="premium-sidebar-tagline">
          <Icon name="school" size={44} />
          <span>Exams<br />made<br />simple</span>
        </div>
      </aside>

      <main className="premium-main">
        <header className="premium-topbar">
          <div className="premium-topbar__leading">
            <DashboardSchoolIdentity schoolName={schoolName} logoSrc={schoolLogoSrc} />
            <label className="premium-searchbox">
              <Icon name="search" size={18} />
              <input type="search" placeholder="Search anything..." />
            </label>
          </div>
          <div className="premium-account">
            <DashboardAccountMenu actor={actor} fallbackName={adminName} roleLabel="Administrator" onSignOut={signOut} />
          </div>
        </header>
        {section === 'dashboard' && <AdminDashboard adminName={adminName} onNavigate={handleNavClick} />}
        {section === 'exams' && <ExamOperations />}
        {section === 'question-banks' && <QuestionBank />}
        {section === 'students' && <StudentsView />}
        {section === 'invigilators' && <InvigilatorPanel />}
        {section === 'results' && <ResultsPage />}
        {section === 'reports' && <ReportsPage />}
        {section === 'settings' && <SettingsPage />}
      </main>
    </div>
  )
}
