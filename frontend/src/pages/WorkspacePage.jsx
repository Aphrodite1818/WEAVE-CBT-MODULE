import { DashboardLayout } from '../layouts/DashboardLayout'
import { PageHeader, DataTable } from '../components/DashboardParts'
import { Button, EmptyState, StatusBadge } from '../components/Ui'
import { adminNav, teacherNav, sectionContent } from '../mocks/data'
import { Icon } from '../lib/icons'

export function WorkspacePage({ role, section, navigate, onLogout }) {
  const isAdmin = role === 'admin'
  const nav = isAdmin ? adminNav : teacherNav
  const label = nav.find(([item]) => item.toLowerCase().replaceAll(' ', '-').replace('/', '') === section)?.[0] || section
  const content = sectionContent[section] || sectionContent.exams
  const go = (target) => {
    if (target === 'logout') return onLogout()
    if (target === 'Dashboard') return navigate(`/${role}`)
    navigate(`/${role}/${target.toLowerCase().replaceAll(' ', '-').replace('/', '')}`)
  }
  return <DashboardLayout role={isAdmin ? 'Admin' : 'Teacher'} nav={nav} active={label} onNavigate={go}>
    <div className="dashboard-content">
      <PageHeader eyebrow={`${isAdmin ? 'School' : 'Teacher'} workspace`} title={content.title || label} description={content.description} action={content.action && <Button icon="plus">{content.action}</Button>} />
      {content.empty ? <section className="panel"><EmptyState title={content.empty.title} text={content.empty.text} /></section> : <>
        {content.summary && <section className="summary-row">{content.summary.map(([value, caption, tone]) => <article className="summary-cell" key={caption}><strong>{value}</strong><span>{caption}</span>{tone && <StatusBadge tone={tone}>Current</StatusBadge>}</article>)}</section>}
        <section className="panel workspace-panel">
          <div className="panel__head"><div><h2>{content.panelTitle}</h2><p>{content.panelText}</p></div><div className="panel-tools"><button className="search-control"><Icon name="search" /> Search</button><button className="filter-control"><Icon name="filter" /> Filter</button></div></div>
          <DataTable columns={content.columns} rows={content.rows} />
        </section>
      </>}
    </div>
  </DashboardLayout>
}
