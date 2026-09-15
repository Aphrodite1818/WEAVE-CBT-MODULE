import { Icon } from '../../shared/icons/Icon'
import { WeaveLogo } from '../../shared/ui'
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
  const adminName = actor?.display_name || state.session?.name || 'Taiwo Okafor'

  const handleNavClick = (item) => {
    dispatch({ type: 'staff', patch: { section: item } })
  }

  return (
    <div className="premium-admin-shell">
      <aside className="premium-sidebar">
        <WeaveLogo />

        <div className="premium-school-badge">
            <div className="school-icon">{getLocalBrandLogoSrc(state.branding) ? <img src={getLocalBrandLogoSrc(state.branding)} alt="School logo" /> : <Icon name="school" size={18} />}</div>
          <div className="school-info">
            <strong>{state.branding?.school_name || state.installation?.status?.tenant_name || 'Weave CBT'}</strong>
            <small>{state.installation?.status?.server_name || 'Local CBT server'}</small>
          </div>
        </div>

        <nav className="premium-nav" aria-label="Admin navigation">
          {adminNav.map(([item, label, icon]) => (
            <button key={item} className={section === item ? 'active' : ''} onClick={() => handleNavClick(item)}>
              <Icon name={icon} size={20} />
              {label}
            </button>
          ))}
        </nav>

        <div className="premium-sidebar-footer">
          <div className="user-avatar">TO</div>
          <div className="user-info">
            <strong>{adminName}</strong>
            <small>Administrator</small>
          </div>
          <button className="logout-btn" type="button" aria-label="Sign out" onClick={signOut}>
            <Icon name="logout" size={18} />
          </button>
        </div>
      </aside>

      <main className="premium-main">
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
