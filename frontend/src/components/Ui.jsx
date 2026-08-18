import { Icon } from '../lib/icons'

export function Button({ children, variant = 'primary', icon, className = '', ...props }) {
  return <button className={`button button--${variant} ${className}`} {...props}>{children}{icon && <Icon name={icon} size={18} />}</button>
}

export function Field({ label, hint, ...props }) {
  return <label className="field"><span>{label}</span><input {...props} />{hint && <small>{hint}</small>}</label>
}

export function StatusBadge({ children, tone = 'neutral' }) {
  return <span className={`status status--${tone}`}>{children}</span>
}

export function EmptyState({ title, text }) {
  return <div className="empty-state"><span className="empty-state__icon"><Icon name="book" /></span><h3>{title}</h3><p>{text}</p></div>
}
