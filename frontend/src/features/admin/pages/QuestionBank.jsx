import { useState } from 'react'
import { Icon } from '../../../shared/icons/Icon'

export function QuestionBank() {
  const [view, setView] = useState('list')

  if (view === 'create') return <CreateQuestionView onCancel={() => setView('list')} />

  return (
    <>
      <header className="premium-header">
        <div className="premium-header-content"><p><Icon name="dashboard" size={16} style={{display:'inline', verticalAlign:'text-bottom', marginRight:'4px'}}/> Dashboard &gt; Question Bank</p><h1>Question Bank</h1></div>
        <button className="btn-primary" onClick={() => setView('create')}><Icon name="plus" size={18} /> Create question</button>
      </header>
      <div className="premium-content">
        <div className="premium-table-wrap">
          <div className="premium-table-header"><div className="premium-search"><Icon name="search" size={16} /><input type="text" placeholder="Search questions..." /></div></div>
          <table className="premium-table">
            <thead><tr><th>Question Stem</th><th>Subject</th><th>Type</th><th>Actions</th></tr></thead>
            <tbody><tr><td>What is the value of x in the equation 2x + 3 = 11?</td><td>Mathematics</td><td>Multiple Choice</td><td><button className="btn-secondary" style={{padding: '6px 10px'}}>Edit</button></td></tr></tbody>
          </table>
        </div>
      </div>
    </>
  )
}

function CreateQuestionView({ onCancel }) {
  return (
    <>
      <header className="premium-header"><div className="premium-header-content"><p><Icon name="dashboard" size={16} style={{display:'inline', verticalAlign:'text-bottom', marginRight:'4px'}}/> Dashboard &gt; Question Bank &gt; Create</p><h1>Create question</h1></div></header>
      <div className="premium-content">
        <div className="form-card" style={{maxWidth: '800px'}}>
          <div className="form-group full">
            <label style={{display:'flex', justifyContent:'space-between'}}><span>Question stem</span><span style={{display:'flex', alignItems:'center', gap:'8px', fontWeight:'normal'}}><input type="radio" name="qtype" defaultChecked /> Multiple choice</span></label>
            <div style={{border:'1px solid #E2E8F0', borderRadius:'8px', overflow:'hidden'}}><div style={{background:'#F8FAFC', padding:'8px 12px', borderBottom:'1px solid #E2E8F0', display:'flex', gap:'12px', color:'#64748B'}}><Icon name="math" size={18} /><Icon name="link" size={18} /></div><textarea placeholder="Type your question here..." style={{border:'none', borderRadius:'0', minHeight:'120px'}}></textarea></div>
          </div>
          <div className="form-group full" style={{marginTop:'24px'}}>
            <label>Answer options</label>
            <div style={{display:'flex', flexDirection:'column', gap:'12px'}}>
              {['A', 'B', 'C', 'D'].map((option) => <div key={option} style={{display:'flex', alignItems:'center', gap:'12px'}}><div style={{width:'32px', height:'32px', background:'#F1F5F9', borderRadius:'50%', display:'grid', placeItems:'center', color:'#64748B', fontWeight:'600'}}>{option}</div><input type="text" placeholder={`Enter option ${option}`} style={{flex:1}} /><button style={{background:'transparent', border:'none', color:'#EF4444', cursor:'pointer'}}><Icon name="trash" size={18} /></button></div>)}
            </div>
          </div>
          <div className="form-group full" style={{marginTop:'24px'}}><label>Correct answer</label><select><option>Select correct option</option><option>A</option><option>B</option></select></div>
          <div className="form-actions"><button className="btn-secondary" onClick={onCancel}>Cancel</button><button className="btn-primary" onClick={onCancel}>Save question</button></div>
        </div>
      </div>
    </>
  )
}
