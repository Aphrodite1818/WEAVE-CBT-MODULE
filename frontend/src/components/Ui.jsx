import { useState } from 'react'
import { Icon } from '../lib/icons'

export function WeaveLogo({ inverse = false, size = 'normal' }) {
  return (
    <div className={`leaf-logo ${inverse ? 'inverse' : ''} ${size === 'large' ? 'large' : ''}`} aria-label="Weave">
      <strong><span style={{color: '#2563EB'}}>W</span> Weave</strong> CBT
    </div>
  )
}

export function TenantIdentity({ tenant, inverse = false }) {
  return (
    <div className={`tenant-identity ${inverse ? 'inverse' : ''}`}>
      <span>{tenant.initials}</span>
      <div>
        <strong>{tenant.schoolName}</strong>
        <small>{tenant.nodeName}</small>
      </div>
      {!inverse && <Icon name="chevronDown" size={18} />}
    </div>
  )
}

export function SegmentedControl({ label, value, options, onChange }) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map(([optionValue, optionLabel]) => (
        <button key={optionValue} type="button" className={value === optionValue ? 'active' : ''} onClick={() => onChange(optionValue)}>
          {optionLabel}
        </button>
      ))}
    </div>
  )
}

export function FormField({ label, value, onChange, type = 'text', icon, placeholder }) {
  const [visible, setVisible] = useState(false)
  const inputType = type === 'password' && visible ? 'text' : type

  return (
    <label className="form-field">
      <span>{label}</span>
      <span className="form-field__control">
        {icon && <Icon name={icon} size={20} />}
        <input type={inputType} value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} />
        {type === 'password' && (
          <button
            type="button"
            className="form-field__reveal"
            aria-label={visible ? 'Hide password' : 'Show password'}
            onClick={() => setVisible((current) => !current)}
          >
            <Icon name={visible ? 'eyeOff' : 'eye'} size={20} />
          </button>
        )}
      </span>
    </label>
  )
}

export function Notice({ tone = 'neutral', children }) {
  return <p className={`notice ${tone}`}>{children}</p>
}

export function StatusBadge({ children, tone = 'neutral' }) {
  return <span className={`status-badge ${tone}`}>{children}</span>
}

export function PageTitle({ title, subtitle }) {
  return <div className="page-title"><h1>{title}</h1>{subtitle && <p>{subtitle}</p>}</div>
}

export function Panel({ title, action, className = '', children }) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel__header">
        <h2>{title}</h2>
        {action}
      </div>
      {children}
    </section>
  )
}

export function Metric({ label, value, helper }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong>{helper && <small>{helper}</small>}</div>
}

export function FilterBar({ children }) {
  return <div className="filter-bar">{children}</div>
}

export function SearchField({ label, placeholder }) {
  return (
    <label className="search-field">
      <Icon name="search" size={17} />
      <input aria-label={label} placeholder={placeholder} />
    </label>
  )
}

export function DataTable({ columns, rows, onRowClick }) {
  return (
    <div className="table-wrap">
      <table>
        <thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.join('-')} onClick={() => onRowClick?.(row)}>
              {row.map((cell, index) => <td key={`${cell}-${index}`}>{cell}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
