import { Icon } from '../../../shared/icons/Icon'

export function ResultsPage() {
  return (
    <>
      <header className="premium-header"><div className="premium-header-content"><p><Icon name="dashboard" size={16} style={{display:'inline', verticalAlign:'text-bottom', marginRight:'4px'}}/> Dashboard &gt; Results</p><h1>Results</h1></div></header>
      <div className="premium-content"><div className="premium-table-wrap"><table className="premium-table"><thead><tr><th>Candidate</th><th>Raw Score</th><th>Percentage</th><th>Component</th><th>Sync Status</th></tr></thead><tbody><tr><td colSpan={5}><div className="admin-empty-state"><strong>No results loaded</strong><p>Select a real exam with published results before showing candidate scores.</p></div></td></tr></tbody></table></div></div>
    </>
  )
}
