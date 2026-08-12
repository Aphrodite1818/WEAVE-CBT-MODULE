export function Brand({ compact = false, inverse = false }) {
  return (
    <div className={`brand ${inverse ? 'brand--inverse' : ''}`}>
      <span className="brand__mark" aria-hidden="true">W</span>
      {!compact && <span><strong>WEAVE</strong><small>CBT</small></span>}
    </div>
  )
}
