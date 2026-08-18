import { DashboardLayout } from '../layouts/DashboardLayout'
import { PageHeader, StatCard, DataTable } from '../components/DashboardParts'
import { Button, StatusBadge } from '../components/Ui'
import { adminNav, teacherNav, recentActivity } from '../mocks/data'
import { Icon } from '../lib/icons'

const adminStats = [
  ['Enrolled students', '842', '+28 this term', 'users'],
  ['Active exams', '6', '3 scheduled today', 'exams'],
  ['Registered candidates', '376', 'Across active exams', 'candidate'],
  ['Submissions', '1,284', '97.8% completion', 'submission'],
  ['Pending result sync', '18', 'Ready for Weave', 'sync', 'warm'],
]

const teacherStats = [
  ['My exams', '8', '2 currently active', 'exams'],
  ['Question bank', '146', 'Across 4 subjects', 'questions'],
  ['Candidates', '214', '12 absent today', 'candidate'],
  ['Marked submissions', '392', '18 awaiting review', 'results'],
]

export function DashboardPage({ role, navigate, onLogout }) {
  const isAdmin = role === 'admin'
  const nav = isAdmin ? adminNav : teacherNav
  const stats = isAdmin ? adminStats : teacherStats
  const go = (label) => {
    if (label === 'logout') return onLogout()
    if (label === 'Dashboard') return navigate(`/${role}`)
    navigate(`/${role}/${label.toLowerCase().replaceAll(' ', '-').replace('/', '')}`)
  }
  return <DashboardLayout role={isAdmin ? 'Admin' : 'Teacher'} nav={nav} active="Dashboard" onNavigate={go}>
    <div className="dashboard-content">
      <PageHeader eyebrow="Wednesday, 12 August" title={`Good morning, ${isAdmin ? 'Amara' : 'Chidi'}.`} description={isAdmin ? 'Here is what is happening across your assessment workspace.' : 'Your classes and assessments are ready for the day.'} action={<Button icon="plus" onClick={() => go(isAdmin ? 'Exams' : 'My Exams')}>Create exam</Button>} />
      <section className={`stats-grid ${isAdmin ? 'stats-grid--admin' : ''}`}>{stats.map(([label, value, detail, icon, tone]) => <StatCard key={label} label={label} value={value} detail={detail} icon={icon} tone={tone} />)}</section>
      <section className="dashboard-columns">
        <article className="panel panel--wide">
          <div className="panel__head"><div><h2>{isAdmin ? 'Today’s examinations' : 'My upcoming exams'}</h2><p>Live schedule and candidate readiness</p></div><button className="text-button" onClick={() => go(isAdmin ? 'Exams' : 'My Exams')}>View all</button></div>
          <DataTable columns={['Examination', 'Class', 'Candidates', 'Time', 'Status']} rows={[
            ['SS2 Biology Mock', 'SS2 Science', '42 / 44', '09:00 – 09:20', { badge: 'In progress', tone: 'success' }],
            ['JSS3 Mathematics', 'JSS3', '88', '11:30 – 12:15', { badge: 'Scheduled', tone: 'neutral' }],
            ['SS1 English Language', 'SS1', '104', '13:00 – 13:45', { badge: 'Draft', tone: 'warning' }],
          ]} />
        </article>
        <article className="panel activity-panel">
          <div className="panel__head"><div><h2>Recent activity</h2><p>Latest workspace updates</p></div></div>
          <div className="activity-list">{recentActivity.map(([title, action, time], index) => <div className="activity-item" key={title}><span className="activity-icon"><Icon name={['exams', 'users', 'sync'][index]} /></span><div><strong>{title}</strong><span>{action}</span><small>{time}</small></div></div>)}</div>
        </article>
      </section>
      <section className="sync-banner"><span className="sync-banner__icon"><Icon name="sync" /></span><div><strong>18 component results are ready to sync</strong><p>CBT sends normalized component scores to Weave. Final academic grades remain calculated in Weave.</p></div><StatusBadge tone="warning">Pending sync</StatusBadge></section>
    </div>
  </DashboardLayout>
}
