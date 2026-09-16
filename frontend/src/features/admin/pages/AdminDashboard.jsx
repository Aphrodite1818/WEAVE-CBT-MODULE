import { Icon } from '../../../shared/icons/Icon'

export function AdminDashboard({ adminName, onNavigate }) {
  const firstName = adminName === 'Administrator' ? '' : adminName.split(' ')[0]

  return (
    <>
      <header className="premium-header">
        <div className="premium-header-content">
          <p><Icon name="dashboard" size={16} style={{display:'inline', verticalAlign:'text-bottom', marginRight:'4px'}}/> Dashboard</p>
          <h1>{firstName ? `Welcome back, ${firstName}.` : 'Welcome back.'}</h1>
          <p>Live dashboard metrics will appear here after the admin read contracts are connected.</p>
        </div>
        <button className="btn-primary" onClick={() => onNavigate('exams')}>
          <Icon name="plus" size={18} /> Create exam
        </button>
      </header>

      <div className="premium-content">
        <div className="metrics-grid">
          <MetricCard label="upcoming exams" value="-" icon="clock" tone="blue" />
          <MetricCard label="ongoing exams" value="-" icon="bolt" tone="green" />
          <MetricCard label="completed exams" value="-" icon="check" tone="purple" />
          <MetricCard label="total candidates" value="-" icon="users" tone="orange" />
        </div>

        <div className="dashboard-layout">
          <div className="panel-card">
            <div className="panel-header">
              <h2>Today's schedule</h2>
              <a href="#view-all" onClick={(event) => { event.preventDefault(); onNavigate('exams') }}>View all</a>
            </div>
            <EmptyPanel title="No schedule loaded" copy="The frontend is waiting for a backend-backed exam schedule endpoint." />
          </div>

          <div className="panel-card">
            <div className="panel-header"><h2>Recent activity</h2></div>
            <EmptyPanel title="No activity loaded" copy="Activity will show here once an audit/activity feed is exposed." />
          </div>
        </div>
      </div>
    </>
  )
}

function MetricCard({ label, value, icon, tone }) {
  return (
    <div className="metric-card">
      <div className="metric-card-header"><h3>{label}</h3><div className={`metric-icon ${tone}`}><Icon name={icon} size={24} /></div></div>
      <div className="metric-card-value"><strong>{value}</strong></div>
    </div>
  )
}

function EmptyPanel({ title, copy }) {
  return (
    <div className="admin-empty-state">
      <strong>{title}</strong>
      <p>{copy}</p>
    </div>
  )
}
