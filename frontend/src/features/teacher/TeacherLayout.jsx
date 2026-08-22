import { Icon } from '../../lib/icons'
import { LeafLogo } from '../../components/ui'

function teacherNavActive(current, section) {
  if (section === 'question-banks') return current === 'question-banks' || current === 'bank-detail'
  if (section === 'questions') return current === 'questions' || current === 'create-question'
  if (section === 'exams') return current === 'exams' || current === 'create-exam'
  return current === section
}

export function TeacherLayout({ state, dispatch, signOut, children }) {
  const teacherName = state.session?.actor?.display_name || state.session?.name || 'Teacher'
  const teacherRole = state.session?.actor?.role || 'teacher'
  const schoolName = state.installation?.status?.tenant_name || 'Leaf CBT'
  const serverName = state.installation?.status?.server_name || 'Local node'
  const nav = [
    ['overview', 'dashboard', 'Overview'],
    ['question-banks', 'book', 'Question Banks'],
    ['questions', 'questions', 'Questions'],
    ['exams', 'exams', 'Exams'],
  ]
  const pageTitle = {
    overview: 'Overview',
    'question-banks': 'Question Banks',
    'bank-detail': 'Question Banks',
    questions: 'Questions',
    'create-question': 'Create Question',
    exams: 'Exams',
    'create-exam': 'Create Exam',
  }[state.staff.section] || 'Overview'

  return (
    <main className="teacher-shell">
      <aside className="teacher-sidebar">
        <LeafLogo />
        <div className="teacher-profile">
          <span className="teacher-avatar">{initials(teacherName)}</span>
          <div>
            <strong>{teacherName}</strong>
            <small>{teacherRole}</small>
          </div>
        </div>
        <div className="school-card">
          <span><Icon name="school" size={20} /></span>
          <div>
            <strong>{schoolName}</strong>
            <small>{serverName}</small>
          </div>
        </div>
        <nav>
          {nav.map(([section, icon, label]) => (
            <button
              key={section}
              className={teacherNavActive(state.staff.section, section) ? 'active' : ''}
              onClick={() => dispatch({ type: 'staff', patch: { section } })}
            >
              <Icon name={icon} size={18} />
              {label}
            </button>
          ))}
        </nav>
        <button className="sidebar-signout" onClick={signOut}>
          <Icon name="logout" size={18} />
          Sign out
        </button>
      </aside>
      <section className="teacher-main">
        <header className="teacher-topbar">
          <strong>{pageTitle}</strong>
        </header>
        <div className="teacher-content">{children}</div>
      </section>
    </main>
  )
}

function initials(name) {
  return name.split(' ').map((part) => part[0]).join('').slice(0, 2).toUpperCase()
}
