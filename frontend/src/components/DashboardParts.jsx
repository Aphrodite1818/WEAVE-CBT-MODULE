import { Icon } from '../lib/icons'
import { StatusBadge } from './Ui'

export function PageHeader({ eyebrow, title, description, action }) {
  return <header className="page-header"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{action}</header>
}

export function StatCard({ label, value, detail, icon, tone = '' }) {
  return <article className={`stat-card ${tone ? `stat-card--${tone}` : ''}`}><div className="stat-card__head"><span>{label}</span><span className="stat-card__icon"><Icon name={icon} /></span></div><strong>{value}</strong><small>{detail}</small></article>
}

export function DataTable({ columns, rows }) {
  return <div className="table-wrap"><table><thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index}>{row.map((cell, cellIndex) => <td key={cellIndex}>{cell?.badge ? <StatusBadge tone={cell.tone}>{cell.badge}</StatusBadge> : cell}</td>)}</tr>)}</tbody></table></div>
}
