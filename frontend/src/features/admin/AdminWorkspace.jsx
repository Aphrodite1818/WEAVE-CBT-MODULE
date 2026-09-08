import { useEffect, useMemo, useState } from 'react'
import { Icon } from '../../lib/icons'
import { Notice } from '../../components/ui'
import { leafGateway } from '../../services/leafGateway'
import './admin.css' // Import the premium styles

const PAGE_SIZE = 100

const adminNav = [
  ['dashboard', 'Dashboard', 'dashboard'],
  ['exams', 'Exams', 'exams'],
  ['question-banks', 'Question Bank', 'book'],
  ['students', 'Students', 'users'],
  ['invigilators', 'Invigilators', 'shield'],
  ['results', 'Results', 'results'],
  ['reports', 'Reports', 'reports'],
  ['settings', 'Settings', 'settings'],
]

export function AdminWorkspace({ state, dispatch, signOut, gateway = leafGateway }) {
  const section = state.staff.section === 'overview' ? 'dashboard' : state.staff.section
  const actor = state.session?.actor
  const adminName = actor?.display_name || state.session?.name || 'Taiwo Okafor'

  const handleNavClick = (item) => {
    dispatch({ type: 'staff', patch: { section: item } })
  }

  return (
    <div className="premium-admin-shell">
      <aside className="premium-sidebar">
        <div className="leaf-logo">
          <strong><span style={{color: '#2563EB'}}>W</span> Weave</strong> CBT
        </div>
        
        <div className="premium-school-badge">
          <div className="school-icon">
            <Icon name="school" size={18} />
          </div>
          <div className="school-info">
            <strong>Greenfield College</strong>
            <small>Main computer lab</small>
          </div>
        </div>
        
        <nav className="premium-nav" aria-label="Admin navigation">
          {adminNav.map(([item, label, icon]) => (
            <button 
              key={item} 
              className={section === item ? 'active' : ''} 
              onClick={() => handleNavClick(item)}
            >
              <Icon name={icon} size={20} />
              {label}
            </button>
          ))}
        </nav>
        
        <div className="premium-sidebar-footer">
          <div className="user-avatar">TO</div>
          <div className="user-info">
            <strong>{adminName}</strong>
            <small>Administrator</small>
          </div>
        </div>
      </aside>
      
      <main className="premium-main">
        {section === 'dashboard' && <AdminDashboard adminName={adminName} gateway={gateway} onNavigate={handleNavClick} />}
        {section === 'exams' && <ExamOperations gateway={gateway} />}
        {section === 'question-banks' && <QuestionBank gateway={gateway} />}
        {section === 'students' && <StudentsView gateway={gateway} />}
        {section === 'invigilators' && <InvigilatorPanel gateway={gateway} />}
        {section === 'results' && <ResultsPage gateway={gateway} />}
        {section === 'reports' && <ReportsPage gateway={gateway} />}
        {section === 'settings' && <SettingsPage gateway={gateway} />}
      </main>
    </div>
  )
}

function AdminDashboard({ adminName, onNavigate }) {
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
          <div className="metric-card">
            <div className="metric-card-header">
              <h3>upcoming exams</h3>
              <div className="metric-icon blue"><Icon name="clock" size={24} /></div>
            </div>
            <div className="metric-card-value">
              <strong>3</strong>
            </div>
          </div>
          <div className="metric-card">
            <div className="metric-card-header">
              <h3>ongoing exam</h3>
              <div className="metric-icon green"><Icon name="bolt" size={24} /></div>
            </div>
            <div className="metric-card-value">
              <strong>1</strong>
            </div>
          </div>
          <div className="metric-card">
            <div className="metric-card-header">
              <h3>completed exams</h3>
              <div className="metric-icon purple"><Icon name="check" size={24} /></div>
            </div>
            <div className="metric-card-value">
              <strong>5</strong>
              <span><Icon name="arrow" size={16} style={{transform: 'rotate(45deg)'}} /></span>
            </div>
          </div>
          <div className="metric-card">
            <div className="metric-card-header">
              <h3>Total candidates</h3>
              <div className="metric-icon orange"><Icon name="users" size={24} /></div>
            </div>
            <div className="metric-card-value">
              <strong>426</strong>
              <span><Icon name="arrow" size={16} style={{transform: 'rotate(45deg)'}} /></span>
            </div>
          </div>
        </div>
        
        <div className="dashboard-layout">
          <div className="panel-card">
            <div className="panel-header">
              <h2>Today's schedule</h2>
              <a href="#view-all" onClick={(e) => { e.preventDefault(); onNavigate('exams'); }}>View all</a>
            </div>
            <div className="schedule-list">
              <div className="schedule-item">
                <div className="schedule-info">
                  <strong>Mathematics</strong>
                  <span>SS 3 • Third Term</span>
                  <span>95 candidates</span>
                </div>
                <div className="status-pill ongoing">Ongoing</div>
              </div>
              <div className="schedule-item">
                <div className="schedule-info">
                  <strong>English Language</strong>
                  <span>SS 1 • First Term</span>
                  <span>105 candidates</span>
                </div>
                <div className="status-pill upcoming">Upcoming</div>
              </div>
              <div className="schedule-item">
                <div className="schedule-info">
                  <strong>Biology</strong>
                  <span>SS 2 • First Term</span>
                  <span>86 candidates</span>
                </div>
                <div className="status-pill upcoming">Upcoming</div>
              </div>
            </div>
          </div>
          
          <div className="panel-card">
            <div className="panel-header">
              <h2>Recent activity</h2>
            </div>
            <div className="activity-list">
              <div className="activity-item">
                <div className="activity-icon green"><Icon name="bolt" size={16} /></div>
                <div className="activity-info">
                  <strong>Mathematics started</strong>
                  <span>5 Sep 2026, 09:00</span>
                </div>
              </div>
              <div className="activity-item">
                <div className="activity-icon blue"><Icon name="users" size={16} /></div>
                <div className="activity-info">
                  <strong>85 students signed in</strong>
                  <span>5 Sep 2026, 09:12</span>
                </div>
              </div>
              <div className="activity-item">
                <div className="activity-icon blue"><Icon name="plus" size={16} /></div>
                <div className="activity-info">
                  <strong>New questions added</strong>
                  <span>4 Sep 2026, 18:31</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

function ExamOperations({ gateway }) {
  const [view, setView] = useState('list')
  
  if (view === 'create') {
    return <CreateExamView gateway={gateway} onCancel={() => setView('list')} />
  }
  
  return (
    <>
      <header className="premium-header">
        <div className="premium-header-content">
          <p><Icon name="dashboard" size={16} style={{display:'inline', verticalAlign:'text-bottom', marginRight:'4px'}}/> Dashboard &gt; Exams</p>
          <h1>Exams</h1>
        </div>
        <button className="btn-primary" onClick={() => setView('create')}>
          <Icon name="plus" size={18} /> Create new exam
        </button>
      </header>
      <div className="premium-content">
        <div className="premium-table-wrap">
          <div className="premium-table-header">
            <div className="premium-search">
              <Icon name="search" size={16} />
              <input type="text" placeholder="Search exams..." />
            </div>
            <button className="btn-secondary"><Icon name="filter" size={16} /> Filter</button>
          </div>
          <table className="premium-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Subject</th>
                <th>Class/Level</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>Mathematics First Term</strong><br/><small>5 Sep 2026</small></td>
                <td>Mathematics</td>
                <td>SS 2</td>
                <td><span className="status-pill ongoing">Active</span></td>
                <td><button className="btn-secondary" style={{padding: '6px 10px'}}>Manage</button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}

function CreateExamView({ gateway, onCancel }) {
  return (
    <>
      <header className="premium-header">
        <div className="premium-header-content">
          <p><Icon name="dashboard" size={16} style={{display:'inline', verticalAlign:'text-bottom', marginRight:'4px'}}/> Dashboard &gt; Exams</p>
          <h1>Create new exam</h1>
          <p>Set up an examination session for your students.</p>
        </div>
      </header>
      <div className="premium-content">
        <div className="form-card">
          <div className="form-grid">
            <div className="form-group full">
              <label>Exam title</label>
              <input type="text" placeholder="e.g. Mathematics First Term Examination" />
            </div>
            <div className="form-group">
              <label>Subject</label>
              <select><option>Select subject</option></select>
            </div>
            <div className="form-group">
              <label>Class / Level</label>
              <select><option>Select class</option></select>
            </div>
            <div className="form-group">
              <label>Term</label>
              <select><option>Select term</option></select>
            </div>
            <div className="form-group">
              <label>Start time</label>
              <input type="time" />
            </div>
            <div className="form-group">
              <label>Start date</label>
              <input type="date" />
            </div>
            <div className="form-group">
              <label>Duration (minutes)</label>
              <input type="number" placeholder="e.g. 60" />
            </div>
            <div className="form-group">
              <label>Total questions</label>
              <input type="number" placeholder="e.g. 30" />
            </div>
            <div className="form-group full">
              <label>Instructions for students (optional)</label>
              <textarea placeholder="Enter any special instructions..."></textarea>
            </div>
          </div>
          <div className="form-actions">
            <button className="btn-secondary" onClick={onCancel}>Save as draft</button>
            <button className="btn-primary" onClick={onCancel}>Create exam</button>
          </div>
        </div>
      </div>
    </>
  )
}

function QuestionBank({ gateway }) {
  const [view, setView] = useState('list')
  
  if (view === 'create') {
    return <CreateQuestionView onCancel={() => setView('list')} />
  }

  return (
    <>
      <header className="premium-header">
        <div className="premium-header-content">
          <p><Icon name="dashboard" size={16} style={{display:'inline', verticalAlign:'text-bottom', marginRight:'4px'}}/> Dashboard &gt; Question Bank</p>
          <h1>Question Bank</h1>
        </div>
        <button className="btn-primary" onClick={() => setView('create')}>
          <Icon name="plus" size={18} /> Create question
        </button>
      </header>
      <div className="premium-content">
        <div className="premium-table-wrap">
          <div className="premium-table-header">
            <div className="premium-search">
              <Icon name="search" size={16} />
              <input type="text" placeholder="Search questions..." />
            </div>
          </div>
          <table className="premium-table">
            <thead>
              <tr>
                <th>Question Stem</th>
                <th>Subject</th>
                <th>Type</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>What is the value of x in the equation 2x + 3 = 11?</td>
                <td>Mathematics</td>
                <td>Multiple Choice</td>
                <td><button className="btn-secondary" style={{padding: '6px 10px'}}>Edit</button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}

function CreateQuestionView({ onCancel }) {
  return (
    <>
      <header className="premium-header">
        <div className="premium-header-content">
          <p><Icon name="dashboard" size={16} style={{display:'inline', verticalAlign:'text-bottom', marginRight:'4px'}}/> Dashboard &gt; Question Bank &gt; Create</p>
          <h1>Create question</h1>
        </div>
      </header>
      <div className="premium-content">
        <div className="form-card" style={{maxWidth: '800px'}}>
          <div className="form-group full">
            <label style={{display:'flex', justifyContent:'space-between'}}>
              <span>Question stem</span>
              <label style={{display:'flex', alignItems:'center', gap:'8px', fontWeight:'normal'}}>
                <input type="radio" name="qtype" defaultChecked /> Multiple choice
              </label>
            </label>
            <div style={{border:'1px solid #E2E8F0', borderRadius:'8px', overflow:'hidden'}}>
              <div style={{background:'#F8FAFC', padding:'8px 12px', borderBottom:'1px solid #E2E8F0', display:'flex', gap:'12px', color:'#64748B'}}>
                <Icon name="math" size={18} />
                <Icon name="link" size={18} />
              </div>
              <textarea placeholder="Type your question here..." style={{border:'none', borderRadius:'0', minHeight:'120px'}}></textarea>
            </div>
          </div>
          
          <div className="form-group full" style={{marginTop:'24px'}}>
            <label>Answer options</label>
            <div style={{display:'flex', flexDirection:'column', gap:'12px'}}>
              {['A', 'B', 'C', 'D'].map((opt) => (
                <div key={opt} style={{display:'flex', alignItems:'center', gap:'12px'}}>
                  <div style={{width:'32px', height:'32px', background:'#F1F5F9', borderRadius:'50%', display:'grid', placeItems:'center', color:'#64748B', fontWeight:'600'}}>{opt}</div>
                  <input type="text" placeholder={`Enter option ${opt}`} style={{flex:1}} />
                  <button style={{background:'transparent', border:'none', color:'#EF4444', cursor:'pointer'}}><Icon name="trash" size={18} /></button>
                </div>
              ))}
            </div>
          </div>
          
          <div className="form-group full" style={{marginTop:'24px'}}>
            <label>Correct answer</label>
            <select><option>Select correct option</option><option>A</option><option>B</option></select>
          </div>
          
          <div className="form-actions">
            <button className="btn-secondary" onClick={onCancel}>Cancel</button>
            <button className="btn-primary" onClick={onCancel}>Save question</button>
          </div>
        </div>
      </div>
    </>
  )
}

function StudentsView({ gateway }) {
  return (
    <>
      <header className="premium-header">
        <div className="premium-header-content">
          <p><Icon name="dashboard" size={16} style={{display:'inline', verticalAlign:'text-bottom', marginRight:'4px'}}/> Dashboard &gt; Students</p>
          <h1>Students Roster</h1>
        </div>
      </header>
      <div className="premium-content">
        <div className="premium-table-wrap">
          <div className="premium-table-header">
            <div className="premium-search">
              <Icon name="search" size={16} />
              <input type="text" placeholder="Search by name or admission number..." />
            </div>
          </div>
          <table className="premium-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Admission No.</th>
                <th>Class</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>Amina Okafor</strong></td>
                <td>GRN/2026/0042</td>
                <td>SS 3A</td>
                <td><span className="status-pill ongoing">Eligible</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}

function InvigilatorPanel({ gateway }) {
  return (
    <>
      <header className="premium-header">
        <div className="premium-header-content">
          <p><Icon name="dashboard" size={16} style={{display:'inline', verticalAlign:'text-bottom', marginRight:'4px'}}/> Dashboard &gt; Active Session</p>
          <h1>Mathematics</h1>
          <p>SS 2 • First Term Examination</p>
        </div>
        <div style={{display:'flex', alignItems:'center', gap:'12px'}}>
          <span style={{padding:'6px 12px', background:'#F0FDF4', color:'#16A34A', borderRadius:'999px', fontSize:'13px', fontWeight:'600'}}>
            <Icon name="bolt" size={14} style={{display:'inline', verticalAlign:'text-bottom', marginRight:'4px'}}/> Active
          </span>
        </div>
      </header>
      <div className="premium-content">
        <div className="monitoring-layout">
          <div>
            <div className="monitoring-stats">
              <div className="monitoring-stat">
                <strong>120</strong>
                <span>Registered</span>
              </div>
              <div className="monitoring-stat">
                <strong style={{color:'#16A34A'}}>118</strong>
                <span>Signed in</span>
              </div>
              <div className="monitoring-stat">
                <strong style={{color:'#DC2626'}}>2</strong>
                <span>Absent</span>
              </div>
              <div className="monitoring-stat">
                <strong style={{color:'#64748B'}}>0</strong>
                <span>In progress</span>
              </div>
            </div>
            
            <div className="premium-table-wrap" style={{marginBottom:'24px'}}>
              <div className="premium-table-header">
                <div className="premium-search" style={{width:'100%'}}>
                  <Icon name="search" size={16} />
                  <input type="text" placeholder="Search student by name or admission number..." />
                </div>
              </div>
              <table className="premium-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Name</th>
                    <th>Admission No.</th>
                    <th>Status</th>
                    <th>Last Seen</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>1</td>
                    <td><strong>Amina Okafor</strong></td>
                    <td>GRN/2026/0042</td>
                    <td><span style={{color:'#16A34A', fontWeight:'500'}}>Active</span></td>
                    <td>09:05</td>
                  </tr>
                  <tr>
                    <td>2</td>
                    <td><strong>David Adebayo</strong></td>
                    <td>GRN/2026/0101</td>
                    <td><span style={{color:'#16A34A', fontWeight:'500'}}>Active</span></td>
                    <td>09:05</td>
                  </tr>
                  <tr>
                    <td>3</td>
                    <td><strong>Isabella Martins</strong></td>
                    <td>GRN/2026/0115</td>
                    <td><span style={{color:'#16A34A', fontWeight:'500'}}>Active</span></td>
                    <td>09:05</td>
                  </tr>
                  <tr>
                    <td>4</td>
                    <td><strong>Kunle Adeyemi</strong></td>
                    <td>GRN/2026/0156</td>
                    <td><span style={{color:'#64748B', fontWeight:'500'}}>Signed in</span></td>
                    <td>09:02</td>
                  </tr>
                  <tr>
                    <td>5</td>
                    <td><strong>Zainab Bello</strong></td>
                    <td>GRN/2026/0189</td>
                    <td><span style={{color:'#DC2626', fontWeight:'500'}}>Not signed in</span></td>
                    <td>-</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div style={{display:'flex', gap:'12px', justifyContent:'center'}}>
              <button className="btn-secondary" style={{color:'#DC2626', borderColor:'#FCA5A5'}}>End exam</button>
              <button className="btn-primary">Pause exam</button>
            </div>
          </div>
          
          <div>
            <div className="panel-card" style={{height:'100%'}}>
              <div className="panel-header">
                <h2>Live monitoring</h2>
                <div style={{display:'flex', alignItems:'center', gap:'8px'}}>
                  <span style={{fontSize:'13px', color:'#64748B'}}>Auto-refresh</span>
                  <label className="toggle-switch">
                    <input type="checkbox" defaultChecked />
                    <span className="slider"></span>
                  </label>
                </div>
              </div>
              <p style={{fontSize:'13px', color:'#64748B', marginBottom:'16px'}}>Student activity during the examination.</p>
              
              <div className="live-students-grid">
                <div className="live-student-card">
                  <div className="live-student-header">
                    <div className="live-student-info">
                      <strong>Amina Okafor</strong>
                      <span>GRN/2026/0042</span>
                    </div>
                  </div>
                  <div className="live-progress">Question 12/30</div>
                  <div className="live-status active">Active</div>
                </div>
                <div className="live-student-card">
                  <div className="live-student-header">
                    <div className="live-student-info">
                      <strong>David Adebayo</strong>
                      <span>GRN/2026/0101</span>
                    </div>
                  </div>
                  <div className="live-progress">Question 8/30</div>
                  <div className="live-status active">Active</div>
                </div>
                <div className="live-student-card">
                  <div className="live-student-header">
                    <div className="live-student-info">
                      <strong>Zainab Bello</strong>
                      <span>GRN/2026/0189</span>
                    </div>
                  </div>
                  <div className="live-progress">Not started</div>
                  <div className="live-status not-started">Signed in</div>
                </div>
                <div className="live-student-card">
                  <div className="live-student-header">
                    <div className="live-student-info">
                      <strong>Tomiwa Olaniyan</strong>
                      <span>GRN/2026/0251</span>
                    </div>
                  </div>
                  <div className="live-progress">Question 11/30</div>
                  <div className="live-status idle">Warning (2 mins)</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

function ResultsPage({ gateway }) {
  return (
    <>
      <header className="premium-header">
        <div className="premium-header-content">
          <p><Icon name="dashboard" size={16} style={{display:'inline', verticalAlign:'text-bottom', marginRight:'4px'}}/> Dashboard &gt; Results</p>
          <h1>Results</h1>
        </div>
      </header>
      <div className="premium-content">
        <div className="premium-table-wrap">
          <table className="premium-table">
            <thead>
              <tr>
                <th>Candidate</th>
                <th>Raw Score</th>
                <th>Percentage</th>
                <th>Component</th>
                <th>Sync Status</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>GRN/2026/0042</td>
                <td>25/30</td>
                <td>83%</td>
                <td>83/100</td>
                <td><span className="status-pill ongoing">Synced</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}

function ReportsPage({ gateway }) {
  return (
    <>
      <header className="premium-header">
        <div className="premium-header-content">
          <p><Icon name="dashboard" size={16} style={{display:'inline', verticalAlign:'text-bottom', marginRight:'4px'}}/> Dashboard &gt; Reports</p>
          <h1>Exam reports</h1>
          <p>Analyze performance and generate reports.</p>
        </div>
      </header>
      <div className="premium-content">
        <div className="form-card">
          <div className="form-grid">
            <div className="form-group full">
              <label>Select Exam</label>
              <div style={{display:'flex', gap:'16px'}}>
                <select style={{flex:1}}><option>Mathematics - First Term</option></select>
                <button className="btn-primary">Generate</button>
              </div>
            </div>
          </div>
          
          <div style={{marginTop:'32px', display:'grid', gridTemplateColumns:'repeat(4, 1fr)', gap:'24px', borderTop:'1px solid #E2E8F0', paddingTop:'32px'}}>
            <div style={{display:'flex', flexDirection:'column'}}>
              <strong style={{fontSize:'32px', color:'#0F172A'}}>120</strong>
              <span style={{color:'#64748B'}}>Candidates</span>
            </div>
            <div style={{display:'flex', flexDirection:'column'}}>
              <strong style={{fontSize:'32px', color:'#16A34A'}}>115</strong>
              <span style={{color:'#64748B'}}>Passed</span>
            </div>
            <div style={{display:'flex', flexDirection:'column'}}>
              <strong style={{fontSize:'32px', color:'#DC2626'}}>5</strong>
              <span style={{color:'#64748B'}}>Failed</span>
            </div>
            <div style={{display:'flex', flexDirection:'column'}}>
              <strong style={{fontSize:'32px', color:'#2563EB'}}>72</strong>
              <span style={{color:'#64748B'}}>Average score</span>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

function SettingsPage({ gateway }) {
  return (
    <>
      <header className="premium-header">
        <div className="premium-header-content">
          <p><Icon name="dashboard" size={16} style={{display:'inline', verticalAlign:'text-bottom', marginRight:'4px'}}/> Dashboard &gt; Settings</p>
          <h1>Settings</h1>
          <p>Manage your CBT server and preferences.</p>
        </div>
      </header>
      <div className="premium-content">
        <div className="form-card" style={{maxWidth: '800px'}}>
          <div style={{display:'flex', gap:'24px', borderBottom:'1px solid #E2E8F0', paddingBottom:'16px', marginBottom:'24px'}}>
            <span style={{color:'#2563EB', fontWeight:'600', borderBottom:'2px solid #2563EB', paddingBottom:'16px', marginBottom:'-17px'}}>General</span>
            <span style={{color:'#64748B', fontWeight:'500'}}>Security</span>
            <span style={{color:'#64748B', fontWeight:'500'}}>Exam</span>
            <span style={{color:'#64748B', fontWeight:'500'}}>Sync</span>
            <span style={{color:'#64748B', fontWeight:'500'}}>About</span>
          </div>
          <div className="form-grid">
            <div className="form-group full">
              <label>Server Name</label>
              <input type="text" defaultValue="Main computer lab" />
            </div>
            <div className="form-group full">
              <label>Idle time before inactivity</label>
              <select><option>30 minutes</option></select>
            </div>
          </div>
          <div style={{marginTop:'32px', display:'flex', justifyContent:'space-between', alignItems:'center', borderTop:'1px solid #E2E8F0', paddingTop:'24px'}}>
            <div>
              <strong style={{display:'block', fontSize:'14px', color:'#0F172A'}}>Show school name on login screen</strong>
              <span style={{fontSize:'13px', color:'#64748B'}}>Display the school name prominently</span>
            </div>
            <label className="toggle-switch">
              <input type="checkbox" defaultChecked />
              <span className="slider"></span>
            </label>
          </div>
          <div className="form-actions">
            <button className="btn-primary">Save changes</button>
          </div>
        </div>
      </div>
    </>
  )
}
