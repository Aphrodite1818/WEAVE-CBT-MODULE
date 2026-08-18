import { useState } from 'react'
import { Brand } from '../components/Brand'
import { Icon } from '../lib/icons'

export function DashboardLayout({ role, nav, active, onNavigate, children }) {
  const [open, setOpen] = useState(false)
  return <div className="dashboard-shell">
    <aside className={`sidebar ${open ? 'sidebar--open' : ''}`}>
      <div className="sidebar__brand"><Brand inverse /><button className="icon-button mobile-only" onClick={() => setOpen(false)} aria-label="Close navigation"><Icon name="close" /></button></div>
      <div className="school-identity"><span className="school-identity__crest">BA</span><div><strong>Brightfield Academy</strong><small>2025/2026 Session</small></div></div>
      <nav className="sidebar__nav" aria-label={`${role} navigation`}>
        {nav.map(([label, icon]) => <button key={label} className={active === label ? 'active' : ''} onClick={() => { onNavigate(label); setOpen(false) }}><Icon name={icon} /><span>{label}</span></button>)}
      </nav>
      <button className="sidebar__logout" onClick={() => onNavigate('logout')}><Icon name="logout" /><span>Sign out</span></button>
    </aside>
    {open && <button className="sidebar-backdrop" onClick={() => setOpen(false)} aria-label="Close navigation" />}
    <section className="dashboard-main">
      <header className="dashboard-topbar"><button className="icon-button mobile-only" onClick={() => setOpen(true)} aria-label="Open navigation"><Icon name="menu" /></button><div className="topbar__context"><span>Brightfield Academy</span><small>{role} workspace</small></div><div className="topbar__tools"><button className="icon-button" aria-label="Notifications"><Icon name="clock" /></button><div className="topbar__user"><span className="avatar">{role === 'Admin' ? 'AO' : 'CA'}</span><div><strong>{role === 'Admin' ? 'Amara Okafor' : 'Chidi Adebayo'}</strong><small>{role}</small></div></div></div></header>
      {children}
    </section>
  </div>
}
