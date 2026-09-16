import { Icon } from '../../../shared/icons/Icon'

export function InvigilatorPanel() {
  return (
    <>
      <header className="premium-header">
        <div className="premium-header-content"><p><Icon name="dashboard" size={16} style={{display:'inline', verticalAlign:'text-bottom', marginRight:'4px'}}/> Dashboard &gt; Active Session</p><h1>Invigilation</h1><p>Live exam monitoring will appear after an active backend session is selected.</p></div>
      </header>
      <div className="premium-content">
        <div className="monitoring-layout">
          <div>
            <div className="monitoring-stats"><MonitoringStat value="-" label="Registered" /><MonitoringStat value="-" label="Signed in" color="#16A34A" /><MonitoringStat value="-" label="Absent" color="#DC2626" /><MonitoringStat value="-" label="In progress" color="#64748B" /></div>
            <div className="premium-table-wrap" style={{marginBottom:'24px'}}>
              <div className="premium-table-header"><div className="premium-search" style={{width:'100%'}}><Icon name="search" size={16} /><input type="text" placeholder="Search student by name or admission number..." /></div></div>
              <table className="premium-table">
                <thead><tr><th>#</th><th>Name</th><th>Admission No.</th><th>Status</th><th>Last Seen</th></tr></thead>
                <tbody><tr><td colSpan={5}><div className="admin-empty-state"><strong>No roster loaded</strong><p>Select a real active exam session before showing candidates.</p></div></td></tr></tbody>
              </table>
            </div>
            <div style={{display:'flex', gap:'12px', justifyContent:'center'}}><button className="btn-secondary" disabled style={{color:'#DC2626', borderColor:'#FCA5A5'}}>End exam</button><button className="btn-primary" disabled>Pause exam</button></div>
          </div>
          <div>
            <div className="panel-card" style={{height:'100%'}}>
              <div className="panel-header"><h2>Live monitoring</h2><div style={{display:'flex', alignItems:'center', gap:'8px'}}><span style={{fontSize:'13px', color:'#64748B'}}>Auto-refresh</span><label className="toggle-switch"><input type="checkbox" defaultChecked /><span className="slider"></span></label></div></div>
              <div className="admin-empty-state"><strong>No live activity</strong><p>Student activity will render here from the attempt monitoring API.</p></div>
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
