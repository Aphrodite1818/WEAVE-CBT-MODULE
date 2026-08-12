import { PublicLayout } from '../layouts/PublicLayout'
import { Button, StatusBadge } from '../components/Ui'
import { Icon } from '../lib/icons'

export function SubmissionPage({ navigate }) {
  return <PublicLayout minimal>
    <section className="result-page">
      <div className="result-card result-card--success">
        <span className="success-seal"><Icon name="check" size={32} /></span>
        <span className="eyebrow">Submission received</span>
        <h1>Your exam has been submitted.</h1>
        <p>SS2 Biology Mock Examination · Wednesday, 12 August 2026</p>
        <div className="score-display">
          <div><span>Raw score</span><strong>7 <small>/ 10</small></strong></div>
          <i />
          <div><span>Normalized</span><strong>70 <small>/ 100</small></strong></div>
        </div>
        <div className="component-note"><Icon name="info" /><p><strong>This is your CBT component result.</strong> Your final academic grade is calculated in Weave using all configured assessment components.</p></div>
        <div className="result-actions"><Button onClick={() => navigate('/result-details')} icon="arrow">View result details</Button><Button variant="secondary" onClick={() => navigate('/welcome')}>Return to portal</Button></div>
        <StatusBadge tone="success">Saved on this device</StatusBadge>
      </div>
    </section>
  </PublicLayout>
}
