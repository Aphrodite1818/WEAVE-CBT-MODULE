import { Icon } from '../../../shared/icons/Icon'

export function ResultsPage() {
  return (
    <>
      <header className="premium-header"><div className="premium-header-content"><p><Icon name="dashboard" size={16} style={{display:'inline', verticalAlign:'text-bottom', marginRight:'4px'}}/> Dashboard &gt; Results</p><h1>Results</h1></div></header>
      <div className="premium-content"><div className="premium-table-wrap"><table className="premium-table"><thead><tr><th>Candidate</th><th>Raw Score</th><th>Percentage</th><th>Component</th><th>Sync Status</th></tr></thead><tbody><tr><td>GRN/2026/0042</td><td>25/30</td><td>83%</td><td>83/100</td><td><span className="status-pill ongoing">Synced</span></td></tr></tbody></table></div></div>
    </>
  )
}
