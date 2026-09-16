import { Icon } from '../../../shared/icons/Icon'

export function ReportsPage() {
  return (
    <>
      <header className="premium-header"><div className="premium-header-content"><p><Icon name="dashboard" size={16} style={{display:'inline', verticalAlign:'text-bottom', marginRight:'4px'}}/> Dashboard &gt; Reports</p><h1>Exam reports</h1><p>Analyze performance and generate reports.</p></div></header>
      <div className="premium-content">
        <div className="form-card">
          <div className="form-grid"><div className="form-group full"><label>Select Exam</label><div style={{display:'flex', gap:'16px'}}><select style={{flex:1}}><option>No exams loaded</option></select><button className="btn-primary" disabled>Generate</button></div></div></div>
          <div className="admin-empty-state" style={{marginTop:'32px'}}><strong>No report data loaded</strong><p>Reports need an exam list and result aggregation endpoint before metrics can be rendered.</p></div>
        </div>
      </div>
    </>
  )
}
