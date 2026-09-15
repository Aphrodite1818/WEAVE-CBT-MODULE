import { Icon } from '../../../shared/icons/Icon'

export function SettingsPage() {
  return (
    <>
      <header className="premium-header"><div className="premium-header-content"><p><Icon name="dashboard" size={16} style={{display:'inline', verticalAlign:'text-bottom', marginRight:'4px'}}/> Dashboard &gt; Settings</p><h1>Settings</h1><p>Manage your CBT server and preferences.</p></div></header>
      <div className="premium-content">
        <div className="form-card" style={{maxWidth: '800px'}}>
          <div style={{display:'flex', gap:'24px', borderBottom:'1px solid #E2E8F0', paddingBottom:'16px', marginBottom:'24px'}}><span style={{color:'#2563EB', fontWeight:'600', borderBottom:'2px solid #2563EB', paddingBottom:'16px', marginBottom:'-17px'}}>General</span><span style={{color:'#64748B', fontWeight:'500'}}>Security</span><span style={{color:'#64748B', fontWeight:'500'}}>Exam</span><span style={{color:'#64748B', fontWeight:'500'}}>Sync</span><span style={{color:'#64748B', fontWeight:'500'}}>About</span></div>
          <div className="form-grid"><div className="form-group full"><label>Server Name</label><input type="text" defaultValue="Main computer lab" /></div><div className="form-group full"><label>Idle time before inactivity</label><select><option>30 minutes</option></select></div></div>
          <div style={{marginTop:'32px', display:'flex', justifyContent:'space-between', alignItems:'center', borderTop:'1px solid #E2E8F0', paddingTop:'24px'}}><div><strong style={{display:'block', fontSize:'14px', color:'#0F172A'}}>Show school name on login screen</strong><span style={{fontSize:'13px', color:'#64748B'}}>Display the school name prominently</span></div><label className="toggle-switch"><input type="checkbox" defaultChecked /><span className="slider"></span></label></div>
          <div className="form-actions"><button className="btn-primary">Save changes</button></div>
        </div>
      </div>
    </>
  )
}
