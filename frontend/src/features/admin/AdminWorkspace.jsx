import { Icon } from '../../shared/icons/Icon'
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
  const section = state.staff.section === 'overview' ? 'dashboard' : state.staff.section
  const actor = state.session?.actor
  const adminName = actor?.display_name || state.session?.name || 'Administrator'
  const adminInitials = adminName
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('') || 'AD'

  const handleNavClick = (item) => {
    dispatch({ type: 'staff', patch: { section: item } })
  }

  return (
    <div className="premium-admin-shell">
      <aside className="premium-sidebar">
        <div className="premium-school-badge">
          <div className="school-icon">{getLocalBrandLogoSrc(state.branding) ? <img src={getLocalBrandLogoSrc(state.branding)} alt="School logo" /> : <Icon name="school" size={22} />}</div>
          <div className="school-info">
            <strong>{state.branding?.school_name || state.installation?.status?.tenant_name || 'Weave CBT'}</strong>
            <small>{state.installation?.status?.server_name || 'Local CBT server'}</small>
          </div>
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
          <label className="premium-searchbox">
            <Icon name="search" size={18} />
            <input type="search" placeholder="Search anything..." />
          </label>
          <div className="premium-account">
            <button className="premium-icon-button" type="button" aria-label="Notifications"><Icon name="bell" size={20} /></button>
            <div className="premium-user-menu">
              <span>{adminInitials}</span>
              <div>
                <strong>{adminName}</strong>
                <small>Administrator</small>
              </div>
              <Icon name="chevronDown" size={18} />
              <div className="premium-user-menu__dropdown">
                <button type="button"><Icon name="profile" size={17} /> My Profile</button>
                <button type="button"><Icon name="settings" size={17} /> Account Settings</button>
                <button type="button" onClick={signOut}><Icon name="logout" size={17} /> Logout</button>
              </div>
            </div>
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
