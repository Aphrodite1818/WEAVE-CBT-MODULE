import { Icon } from '../../../shared/icons/Icon'

export function StudentsView() {
  return (
    <>
      <header className="premium-header"><div className="premium-header-content"><p><Icon name="dashboard" size={16} style={{display:'inline', verticalAlign:'text-bottom', marginRight:'4px'}}/> Dashboard &gt; Students</p><h1>Students Roster</h1></div></header>
      <div className="premium-content">
        <div className="premium-table-wrap">
          <div className="premium-table-header"><div className="premium-search"><Icon name="search" size={16} /><input type="text" placeholder="Search by name or admission number..." /></div></div>
          <table className="premium-table"><thead><tr><th>Name</th><th>Admission No.</th><th>Class</th><th>Status</th></tr></thead><tbody><tr><td><strong>Amina Okafor</strong></td><td>GRN/2026/0042</td><td>SS 3A</td><td><span className="status-pill ongoing">Eligible</span></td></tr></tbody></table>
        </div>
      </div>
    </>
  )
}
