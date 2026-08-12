import { SetupPage } from '../pages/SetupPage'
import { LandingPage } from '../pages/LandingPage'
import { StaffLoginPage } from '../pages/StaffLoginPage'
import { StudentLoginPage } from '../pages/StudentLoginPage'
import { DashboardPage } from '../pages/DashboardPage'
import { WorkspacePage } from '../pages/WorkspacePage'
import { ExamPage } from '../pages/ExamPage'
import { SubmissionPage } from '../pages/SubmissionPage'
import { ResultDetailsPage } from '../pages/ResultDetailsPage'

const adminSections = ['exams', 'question-bank', 'candidates', 'invigilators', 'results', 'reports', 'audit', 'settings']
const teacherSections = ['my-exams', 'question-bank', 'candidates', 'results', 'profile']

export function AppRouter({ path, configured, navigate, completeSetup, resetSetup, staffRole, loginStaff, logoutStaff }) {
  if (!configured && path !== '/setup') return <SetupPage onComplete={completeSetup} />
  if (path === '/setup') return <SetupPage configured={configured} onComplete={completeSetup} onContinue={() => navigate('/welcome')} />
  if (path === '/welcome') return <LandingPage navigate={navigate} resetSetup={resetSetup} />
  if (path === '/staff-login') return <StaffLoginPage navigate={navigate} onLogin={loginStaff} />
  if (path === '/student-login') return <StudentLoginPage navigate={navigate} />
  if (path === '/exam') return <ExamPage navigate={navigate} />
  if (path === '/submission') return <SubmissionPage navigate={navigate} />
  if (path === '/result-details') return <ResultDetailsPage navigate={navigate} />

  const adminMatch = path.match(/^\/admin(?:\/(.+))?$/)
  if (adminMatch && (!adminMatch[1] || adminSections.includes(adminMatch[1]))) {
    return adminMatch[1]
      ? <WorkspacePage role="admin" section={adminMatch[1]} navigate={navigate} onLogout={logoutStaff} />
      : <DashboardPage role="admin" navigate={navigate} onLogout={logoutStaff} />
  }

  const teacherMatch = path.match(/^\/teacher(?:\/(.+))?$/)
  if (teacherMatch && (!teacherMatch[1] || teacherSections.includes(teacherMatch[1]))) {
    return teacherMatch[1]
      ? <WorkspacePage role="teacher" section={teacherMatch[1]} navigate={navigate} onLogout={logoutStaff} />
      : <DashboardPage role="teacher" navigate={navigate} onLogout={logoutStaff} />
  }

  if (staffRole) return <DashboardPage role={staffRole} navigate={navigate} onLogout={logoutStaff} />
  return <LandingPage navigate={navigate} resetSetup={resetSetup} />
}
