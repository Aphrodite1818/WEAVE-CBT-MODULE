import { useState } from 'react'
import { Icon } from '../lib/icons'

export function LeafLogo({ inverse = false, size = 'normal' }) {
  return (
    <div className={`leaf-logo ${inverse ? 'inverse' : ''} ${size === 'large' ? 'large' : ''}`} aria-label="Leaf">
      <svg className="leaf-mark" viewBox="0 0 64 64" role="img" aria-hidden="true" focusable="false">
        <path d="M31.55 31.45C22.45 31.7 15.35 29.35 10.7 24.65C5.1 18.95 5.85 9.2 6.45 6.35C9.3 5.75 19.05 5 24.75 10.6C29.45 15.25 31.8 22.35 31.55 31.45Z" />
        <path d="M32.45 32.55C41.55 32.3 48.65 34.65 53.3 39.35C58.9 45.05 58.15 54.8 57.55 57.65C54.7 58.25 44.95 59 39.25 53.4C34.55 48.75 32.2 41.65 32.45 32.55Z" />
      </svg>
      <strong>Leaf</strong>
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
