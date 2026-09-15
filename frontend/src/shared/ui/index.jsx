import { useId, useState } from 'react'
import { Icon } from '../icons/Icon'

export function WeaveMark({ className = '' }) {
  const rawId = useId().replace(/:/g, '')
  const blueId = `${rawId}-weave-blue`
  const goldId = `${rawId}-weave-gold`

  return (
    <svg className={`weave-mark ${className}`.trim()} viewBox="0 0 512 512" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id={blueId} x1="64" y1="128" x2="448" y2="384" gradientUnits="userSpaceOnUse">
          <stop stopColor="var(--weave-thread-one-start, #60a5fa)" />
          <stop offset="0.45" stopColor="var(--weave-thread-one-mid, #1d4ed8)" />
          <stop offset="1" stopColor="var(--weave-thread-one-end, #1e3a8a)" />
        </linearGradient>
        <linearGradient id={goldId} x1="448" y1="128" x2="64" y2="384" gradientUnits="userSpaceOnUse">
          <stop stopColor="var(--weave-thread-two-start, #fde68a)" />
          <stop offset="0.46" stopColor="var(--weave-thread-two-mid, #f59e0b)" />
          <stop offset="1" stopColor="var(--weave-thread-two-end, #b45309)" />
        </linearGradient>
      </defs>
      <g fill="none" strokeLinecap="round">
        <path d="M72 174c76 0 82 164 184 164s108-164 184-164" stroke="var(--weave-thread-one-halo, #bfdbfe)" strokeWidth="84" opacity=".7" />
        <path d="M72 174c76 0 82 164 184 164s108-164 184-164" stroke={`url(#${blueId})`} strokeWidth="58" />
        <path d="M72 338c76 0 82-164 184-164s108 164 184 164" stroke="var(--weave-thread-two-halo, #fef3c7)" strokeWidth="84" opacity=".78" />
        <path d="M72 338c76 0 82-164 184-164s108 164 184 164" stroke={`url(#${goldId})`} strokeWidth="58" />
        <path d="M188 256h136" stroke="#fff" strokeWidth="18" opacity=".88" />
      </g>
    </svg>
  )
}

export function WeaveLogo({ inverse = false, size = 'normal' }) {
  return (
    <div className={`weave-logo ${inverse ? 'inverse' : ''} ${size === 'large' ? 'large' : ''}`} role="img" aria-label="Weave CBT">
      <WeaveMark />
      <strong className="weave-logo__word">Weave</strong>
      <i className="weave-logo__divider" aria-hidden="true" />
      <span className="weave-logo__cbt">CBT</span>
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
