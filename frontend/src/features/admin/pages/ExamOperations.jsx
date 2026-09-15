import { useState } from 'react'
import { Icon } from '../../../shared/icons/Icon'

export function ExamOperations() {
  const [view, setView] = useState('list')

  if (view === 'create') return <CreateExamView onCancel={() => setView('list')} />

  return (
    <>
      <header className="premium-header">
        <div className="premium-header-content">
          <p><Icon name="dashboard" size={16} style={{display:'inline', verticalAlign:'text-bottom', marginRight:'4px'}}/> Dashboard &gt; Exams</p>
          <h1>Exams</h1>
        </div>
        <button className="btn-primary" onClick={() => setView('create')}><Icon name="plus" size={18} /> Create new exam</button>
      </header>
      <div className="premium-content">
        <div className="premium-table-wrap">
          <div className="premium-table-header">
            <div className="premium-search"><Icon name="search" size={16} /><input type="text" placeholder="Search exams..." /></div>
            <button className="btn-secondary"><Icon name="filter" size={16} /> Filter</button>
          </div>
          <table className="premium-table">
            <thead><tr><th>Title</th><th>Subject</th><th>Class/Level</th><th>Status</th><th>Actions</th></tr></thead>
            <tbody><tr><td><strong>Mathematics First Term</strong><br/><small>5 Sep 2026</small></td><td>Mathematics</td><td>SS 2</td><td><span className="status-pill ongoing">Active</span></td><td><button className="btn-secondary" style={{padding: '6px 10px'}}>Manage</button></td></tr></tbody>
          </table>
        </div>
      </div>
    </>
  )
}

function CreateExamView({ onCancel }) {
  return (
    <>
      <header className="premium-header">
        <div className="premium-header-content"><p><Icon name="dashboard" size={16} style={{display:'inline', verticalAlign:'text-bottom', marginRight:'4px'}}/> Dashboard &gt; Exams</p><h1>Create new exam</h1><p>Set up an examination session for your students.</p></div>
      </header>
      <div className="premium-content">
        <div className="form-card">
          <div className="form-grid">
            <div className="form-group full"><label>Exam title</label><input type="text" placeholder="e.g. Mathematics First Term Examination" /></div>
            <div className="form-group"><label>Subject</label><select><option>Select subject</option></select></div>
            <div className="form-group"><label>Class / Level</label><select><option>Select class</option></select></div>
            <div className="form-group"><label>Term</label><select><option>Select term</option></select></div>
            <div className="form-group"><label>Start time</label><input type="time" /></div>
            <div className="form-group"><label>Start date</label><input type="date" /></div>
            <div className="form-group"><label>Duration (minutes)</label><input type="number" placeholder="e.g. 60" /></div>
            <div className="form-group"><label>Total questions</label><input type="number" placeholder="e.g. 30" /></div>
            <div className="form-group full"><label>Instructions for students (optional)</label><textarea placeholder="Enter any special instructions..."></textarea></div>
          </div>
          <div className="form-actions"><button className="btn-secondary" onClick={onCancel}>Save as draft</button><button className="btn-primary" onClick={onCancel}>Create exam</button></div>
        </div>
      </div>
    </>
  )
}
