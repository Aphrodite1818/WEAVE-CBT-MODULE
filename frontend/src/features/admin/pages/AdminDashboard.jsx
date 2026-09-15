import { Icon } from '../../../shared/icons/Icon'

export function AdminDashboard({ adminName, onNavigate }) {
  const firstName = adminName.split(' ')[0]

  return (
    <>
      <header className="premium-header">
        <div className="premium-header-content">
          <p><Icon name="dashboard" size={16} style={{display:'inline', verticalAlign:'text-bottom', marginRight:'4px'}}/> Dashboard</p>
          <h1>Welcome back, {firstName}.</h1>
          <p>Here's what's happening with your examinations.</p>
        </div>
        <button className="btn-primary" onClick={() => onNavigate('exams')}>
          <Icon name="plus" size={18} /> Create exam
        </button>
      </header>

      <div className="premium-content">
        <div className="metrics-grid">
          <MetricCard label="upcoming exams" value="3" icon="clock" tone="blue" />
          <MetricCard label="ongoing exam" value="1" icon="bolt" tone="green" />
          <MetricCard label="completed exams" value="5" icon="check" tone="purple" arrow />
          <MetricCard label="Total candidates" value="426" icon="users" tone="orange" arrow />
        </div>

        <div className="dashboard-layout">
          <div className="panel-card">
            <div className="panel-header">
              <h2>Today's schedule</h2>
              <a href="#view-all" onClick={(event) => { event.preventDefault(); onNavigate('exams') }}>View all</a>
            </div>
            <div className="schedule-list">
              <ScheduleItem subject="Mathematics" level="SS 3 • Third Term" candidates="95 candidates" status="Ongoing" tone="ongoing" />
              <ScheduleItem subject="English Language" level="SS 1 • First Term" candidates="105 candidates" status="Upcoming" tone="upcoming" />
              <ScheduleItem subject="Biology" level="SS 2 • First Term" candidates="86 candidates" status="Upcoming" tone="upcoming" />
            </div>
          </div>

          <div className="panel-card">
            <div className="panel-header"><h2>Recent activity</h2></div>
            <div className="activity-list">
              <ActivityItem icon="bolt" tone="green" title="Mathematics started" time="5 Sep 2026, 09:00" />
              <ActivityItem icon="users" tone="blue" title="85 students signed in" time="5 Sep 2026, 09:12" />
              <ActivityItem icon="plus" tone="blue" title="New questions added" time="4 Sep 2026, 18:31" />
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

function MetricCard({ label, value, icon, tone, arrow = false }) {
  return (
    <div className="metric-card">
      <div className="metric-card-header"><h3>{label}</h3><div className={`metric-icon ${tone}`}><Icon name={icon} size={24} /></div></div>
      <div className="metric-card-value"><strong>{value}</strong>{arrow && <span><Icon name="arrow" size={16} style={{transform: 'rotate(45deg)'}} /></span>}</div>
    </div>
  )
}

function ScheduleItem({ subject, level, candidates, status, tone }) {
  return (
    <div className="schedule-item">
      <div className="schedule-info"><strong>{subject}</strong><span>{level}</span><span>{candidates}</span></div>
      <div className={`status-pill ${tone}`}>{status}</div>
    </div>
  )
}

function ActivityItem({ icon, tone, title, time }) {
  return (
    <div className="activity-item">
      <div className={`activity-icon ${tone}`}><Icon name={icon} size={16} /></div>
      <div className="activity-info"><strong>{title}</strong><span>{time}</span></div>
    </div>
  )
}
