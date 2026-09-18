import { useCallback, useEffect, useMemo, useState } from 'react'
import { getLocalBrandLogoSrc } from '../../api/branding'
import { Icon } from '../../shared/icons/Icon'
import { DashboardAccountMenu, DashboardSchoolIdentity } from '../../shared/ui'
import { QuestionBuilder } from '../teacher/QuestionBuilder'
import { ExamAuthoringPage } from '../../shared/exams/ExamAuthoringPage'
import { TeacherQuestionPreviewPage } from '../teacher/TeacherQuestionPreviewPage'
import { AdminExamsPage } from './pages/AdminExamsPage'
import { AdminOverview } from './pages/AdminOverview'
import { AdminBankDetailPage, AdminQuestionBanksPage } from './pages/AdminQuestionBanks'
import { AdminQuestionsPage } from './pages/AdminQuestionsPage'
import { AdminRosterDetailPage, AdminRostersPage } from './pages/AdminRostersPage'
import { useAdminData } from './useAdminData'
import '../teacher/teacher-dashboard.css'
import '../teacher/teacher-selects.css'
import '../teacher/teacher-exams.css'
import './admin.css'

const bankViews = new Set(['question-banks', 'create-bank', 'bank-detail', 'questions', 'create-question', 'edit-question', 'preview-question'])
const examViews = new Set(['exams', 'create-exam'])
const rosterViews = new Set(['roster', 'roster-detail'])
const placeholderViews = new Set(['invigilators', 'results', 'reports'])

const adminNav = [
  ['dashboard', 'home', 'Dashboard'],
  ['question-banks', 'bank', 'Question Banks'],
  ['questions', 'fileText', 'Questions'],
  ['exams', 'calendar', 'Exams'],
  ['roster', 'roster', 'Roster'],
  ['invigilators', 'shield', 'Invigilators'],
  ['results', 'results', 'Results'],
  ['reports', 'reports', 'Reports'],
]

export function AdminWorkspace({ state, dispatch, signOut, gateway }) {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [workspaceView, setWorkspaceView] = useState(() => topLevelView(state.staff.section))
  const adminData = useAdminData(gateway)
  const activeAuthoringData = useMemo(() => ({
    ...adminData,
    banks: adminData.banks.filter((bank) => bank.status === 'Ready'),
  }), [adminData])
  const examFormData = state.staff.selectedExamId ? adminData : activeAuthoringData
  const actor = state.session?.actor
  const adminName = actor?.display_name || state.session?.name || 'Administrator'
  const schoolName = state.branding?.school_name || state.installation?.status?.tenant_name || 'Weave CBT'
  const serverName = state.installation?.status?.server_name || 'Local CBT server'
  const schoolLogoSrc = getLocalBrandLogoSrc(state.branding)

  useEffect(() => {
    const className = 'teacher-dashboard-active'
    document.documentElement.classList.add(className)
    document.body.classList.add(className)
    return () => {
      document.documentElement.classList.remove(className)
      document.body.classList.remove(className)
    }
  }, [])

  useEffect(() => {
    const next = topLevelView(state.staff.section)
    if (state.staff.section === 'dashboard' || state.staff.section === 'students' || placeholderViews.has(state.staff.section)) setWorkspaceView(next)
    if (state.staff.section === 'question-banks' && !bankViews.has(workspaceView)) setWorkspaceView('question-banks')
    if (state.staff.section === 'exams' && !examViews.has(workspaceView)) setWorkspaceView('exams')
    if (state.staff.section === 'roster' && !rosterViews.has(workspaceView)) setWorkspaceView('roster')
  }, [state.staff.section, workspaceView])

  const navigate = useCallback((view, patch = {}) => {
    const parentSection = bankViews.has(view)
      ? 'question-banks'
      : examViews.has(view)
        ? 'exams'
        : rosterViews.has(view)
          ? 'roster'
          : view
    const previewPatch = view === 'preview-question'
      ? { questionPreviewOrigin: workspaceView === 'bank-detail' ? 'bank-detail' : 'questions' }
      : {}
    setWorkspaceView(view)
    dispatch({ type: 'staff', patch: { section: parentSection, ...previewPatch, ...patch } })
  }, [dispatch, workspaceView])

  const workspaceDispatch = useCallback((action) => {
    if (action?.type === 'staff' && action.patch?.section) {
      const { section, ...patch } = action.patch
      navigate(section, patch)
      return
    }
    dispatch(action)
  }, [dispatch, navigate])

  const navActive = (section) => {
    if (section === 'question-banks') return workspaceView === 'question-banks' || workspaceView === 'create-bank' || workspaceView === 'bank-detail'
    if (section === 'questions') return workspaceView === 'questions' || workspaceView === 'create-question' || workspaceView === 'edit-question' || workspaceView === 'preview-question'
    if (section === 'exams') return examViews.has(workspaceView)
    if (section === 'roster') return rosterViews.has(workspaceView)
    return workspaceView === section
  }

  return (
    <main className={`teacher-shell admin-shell${sidebarOpen ? '' : ' teacher-shell--collapsed admin-shell--collapsed'}`}>
      <aside className="teacher-sidebar admin-sidebar">
        <div className="teacher-sidebar__header">
          <div className="school-card">
            <span>{schoolLogoSrc ? <img className="school-brand-logo" src={schoolLogoSrc} alt="School logo" /> : <Icon name="school" size={20} />}</span>
            <div><strong>{schoolName}</strong><small>{serverName}</small></div>
          </div>
          <button className="dashboard-sidebar-toggle" type="button" aria-label={sidebarOpen ? 'Collapse sidebar' : 'Open sidebar'} aria-expanded={sidebarOpen} onClick={() => setSidebarOpen((open) => !open)}>
            <Icon name={sidebarOpen ? 'back' : 'menu'} size={18} />
          </button>
        </div>
        <nav aria-label="Administrator navigation">
          {adminNav.map(([section, icon, label]) => (
            <button key={section} type="button" className={navActive(section) ? 'active' : ''} onClick={() => navigate(section)} title={sidebarOpen ? undefined : label}>
              <Icon name={icon} size={17} /><span>{label}</span>
            </button>
          ))}
        </nav>
      </aside>

      <section className="teacher-main admin-main">
        <header className="teacher-topbar">
          <DashboardSchoolIdentity schoolName={schoolName} logoSrc={schoolLogoSrc} />
          <div className="teacher-topbar__actions"><DashboardAccountMenu actor={actor} fallbackName={adminName} roleLabel="Administrator" onSignOut={signOut} /></div>
        </header>
        <div className="teacher-content admin-content">
          {workspaceView === 'dashboard' && <AdminOverview state={state} adminData={adminData} onNavigate={navigate} />}
          {(workspaceView === 'question-banks' || workspaceView === 'create-bank') && (
            <AdminQuestionBanksPage adminData={adminData} gateway={gateway} onNavigate={navigate} createRequested={workspaceView === 'create-bank'} onCreateHandled={() => setWorkspaceView('question-banks')} />
          )}
          {workspaceView === 'bank-detail' && <AdminBankDetailPage state={state} adminData={adminData} onNavigate={navigate} />}
          {workspaceView === 'questions' && <AdminQuestionsPage state={state} dispatch={workspaceDispatch} adminData={adminData} gateway={gateway} onNavigate={navigate} />}
          {workspaceView === 'preview-question' && <TeacherQuestionPreviewPage state={state} dispatch={workspaceDispatch} teacherData={adminData} gateway={gateway} />}
          {workspaceView === 'create-question' && <QuestionBuilder mode="create" state={state} dispatch={workspaceDispatch} teacherData={activeAuthoringData} gateway={gateway} />}
          {workspaceView === 'edit-question' && <QuestionBuilder key={state.staff.selectedQuestionId || 'admin-question-editor'} mode="edit" state={state} dispatch={workspaceDispatch} teacherData={adminData} gateway={gateway} />}
          {workspaceView === 'exams' && <AdminExamsPage state={state} adminData={adminData} gateway={gateway} onNavigate={navigate} />}
          {workspaceView === 'create-exam' && <ExamAuthoringPage state={state} dispatch={workspaceDispatch} teacherData={examFormData} gateway={gateway} />}
          {workspaceView === 'roster' && <AdminRostersPage adminData={adminData} onNavigate={navigate} />}
          {workspaceView === 'roster-detail' && <AdminRosterDetailPage state={state} adminData={adminData} gateway={gateway} onNavigate={navigate} />}
          {placeholderViews.has(workspaceView) && <AdminPlaceholderPage section={workspaceView} />}
        </div>
      </section>
    </main>
  )
}

function AdminPlaceholderPage({ section }) {
  const labels = {
    invigilators: ['Invigilators', 'Invigilation assignment and monitoring will be connected in a later workspace pass.'],
    results: ['Results', 'Result review and synchronization controls will be connected in a later workspace pass.'],
    reports: ['Reports', 'Administrative reporting will be connected in a later workspace pass.'],
  }
  const [title, copy] = labels[section] || ['Administrator', 'This workspace is not connected yet.']
  return (
    <div className="teacher-reference-page admin-placeholder-page">
      <div className="teacher-page-heading"><div><div className="teacher-page-title-line"><h1>{title}</h1></div><p>{copy}</p></div></div>
      <div className="teacher-reference-empty teacher-reference-empty--large"><div><strong>{title} placeholder</strong><p>No fake data or controls are shown until the required backend workflow is implemented.</p></div></div>
    </div>
  )
}

function topLevelView(section) {
  if (section === 'overview') return 'dashboard'
  if (section === 'students') return 'roster'
  return section || 'dashboard'
}
