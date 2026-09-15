import { Icon } from '../../../shared/icons/Icon'

const candidates = [
  ['Amina Okafor', 'GRN/2026/0042', 'Active', '09:05', '#16A34A'],
  ['David Adebayo', 'GRN/2026/0101', 'Active', '09:05', '#16A34A'],
  ['Isabella Martins', 'GRN/2026/0115', 'Active', '09:05', '#16A34A'],
  ['Kunle Adeyemi', 'GRN/2026/0156', 'Signed in', '09:02', '#64748B'],
  ['Zainab Bello', 'GRN/2026/0189', 'Not signed in', '-', '#DC2626'],
]

const liveStudents = [
  ['Amina Okafor', 'GRN/2026/0042', 'Question 12/30', 'Active', 'active'],
  ['David Adebayo', 'GRN/2026/0101', 'Question 8/30', 'Active', 'active'],
  ['Zainab Bello', 'GRN/2026/0189', 'Not started', 'Signed in', 'not-started'],
  ['Tomiwa Olaniyan', 'GRN/2026/0251', 'Question 11/30', 'Warning (2 mins)', 'idle'],
]

export function InvigilatorPanel() {
  return (
    <>
      <header className="premium-header">
        <div className="premium-header-content"><p><Icon name="dashboard" size={16} style={{display:'inline', verticalAlign:'text-bottom', marginRight:'4px'}}/> Dashboard &gt; Active Session</p><h1>Mathematics</h1><p>SS 2 • First Term Examination</p></div>
        <div style={{display:'flex', alignItems:'center', gap:'12px'}}><span style={{padding:'6px 12px', background:'#F0FDF4', color:'#16A34A', borderRadius:'999px', fontSize:'13px', fontWeight:'600'}}><Icon name="bolt" size={14} style={{display:'inline', verticalAlign:'text-bottom', marginRight:'4px'}}/> Active</span></div>
      </header>
      <div className="premium-content">
        <div className="monitoring-layout">
          <div>
            <div className="monitoring-stats"><MonitoringStat value="120" label="Registered" /><MonitoringStat value="118" label="Signed in" color="#16A34A" /><MonitoringStat value="2" label="Absent" color="#DC2626" /><MonitoringStat value="0" label="In progress" color="#64748B" /></div>
            <div className="premium-table-wrap" style={{marginBottom:'24px'}}>
              <div className="premium-table-header"><div className="premium-search" style={{width:'100%'}}><Icon name="search" size={16} /><input type="text" placeholder="Search student by name or admission number..." /></div></div>
              <table className="premium-table">
                <thead><tr><th>#</th><th>Name</th><th>Admission No.</th><th>Status</th><th>Last Seen</th></tr></thead>
                <tbody>{candidates.map(([name, admission, status, lastSeen, color], index) => <tr key={admission}><td>{index + 1}</td><td><strong>{name}</strong></td><td>{admission}</td><td><span style={{color, fontWeight:'500'}}>{status}</span></td><td>{lastSeen}</td></tr>)}</tbody>
              </table>
            </div>
            <div style={{display:'flex', gap:'12px', justifyContent:'center'}}><button className="btn-secondary" style={{color:'#DC2626', borderColor:'#FCA5A5'}}>End exam</button><button className="btn-primary">Pause exam</button></div>
          </div>
          <div>
            <div className="panel-card" style={{height:'100%'}}>
              <div className="panel-header"><h2>Live monitoring</h2><div style={{display:'flex', alignItems:'center', gap:'8px'}}><span style={{fontSize:'13px', color:'#64748B'}}>Auto-refresh</span><label className="toggle-switch"><input type="checkbox" defaultChecked /><span className="slider"></span></label></div></div>
              <p style={{fontSize:'13px', color:'#64748B', marginBottom:'16px'}}>Student activity during the examination.</p>
              <div className="live-students-grid">{liveStudents.map(([name, admission, progress, status, tone]) => <div className="live-student-card" key={admission}><div className="live-student-header"><div className="live-student-info"><strong>{name}</strong><span>{admission}</span></div></div><div className="live-progress">{progress}</div><div className={`live-status ${tone}`}>{status}</div></div>)}</div>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

function MonitoringStat({ value, label, color }) {
  return <div className="monitoring-stat"><strong style={color ? {color} : undefined}>{value}</strong><span>{label}</span></div>
}
