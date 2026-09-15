import { Icon } from '../../../shared/icons/Icon'

export function ReportsPage() {
  return (
    <>
      <header className="premium-header"><div className="premium-header-content"><p><Icon name="dashboard" size={16} style={{display:'inline', verticalAlign:'text-bottom', marginRight:'4px'}}/> Dashboard &gt; Reports</p><h1>Exam reports</h1><p>Analyze performance and generate reports.</p></div></header>
      <div className="premium-content">
        <div className="form-card">
          <div className="form-grid"><div className="form-group full"><label>Select Exam</label><div style={{display:'flex', gap:'16px'}}><select style={{flex:1}}><option>Mathematics - First Term</option></select><button className="btn-primary">Generate</button></div></div></div>
          <div style={{marginTop:'32px', display:'grid', gridTemplateColumns:'repeat(4, 1fr)', gap:'24px', borderTop:'1px solid #E2E8F0', paddingTop:'32px'}}>
            <ReportMetric value="120" label="Candidates" color="#0F172A" /><ReportMetric value="115" label="Passed" color="#16A34A" /><ReportMetric value="5" label="Failed" color="#DC2626" /><ReportMetric value="72" label="Average score" color="#2563EB" />
          </div>
        </div>
      </div>
    </>
  )
}

function ReportMetric({ value, label, color }) {
  return <div style={{display:'flex', flexDirection:'column'}}><strong style={{fontSize:'32px', color}}>{value}</strong><span style={{color:'#64748B'}}>{label}</span></div>
}
