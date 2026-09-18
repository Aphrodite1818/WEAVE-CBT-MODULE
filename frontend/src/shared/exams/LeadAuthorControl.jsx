import { useEffect, useState } from 'react'
import { SelectControl } from '../ui'

export function LeadAuthorControl({ gateway, subjectId, termId, value, onChange, disabled = false }) {
  const [candidates, setCandidates] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!subjectId || !termId) {
      setCandidates([])
      setLoading(false)
      setError('')
      return undefined
    }

    let cancelled = false
    setLoading(true)
    setError('')
    setCandidates([])

    if (typeof gateway?.exams?.listLeadCandidates !== 'function') {
      setLoading(false)
      setError('Eligible teachers could not be loaded. Administrator coordination is still available.')
      return undefined
    }

    gateway.exams.listLeadCandidates({ curriculum_subject_id: subjectId, term_id: termId })
      .then((rows) => {
        if (!cancelled) setCandidates(Array.isArray(rows) ? rows : [])
      })
      .catch(() => {
        if (!cancelled) setError('Eligible teachers could not be loaded. Administrator coordination is still available.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [gateway, subjectId, termId])

  const options = [
    { value: '', label: 'Administrator coordinates' },
    ...candidates.map((teacher) => ({
      value: teacher.id,
      label: [teacher.first_name, teacher.last_name].filter(Boolean).join(' ') || teacher.staff_id || 'Teacher',
      description: teacher.staff_id || undefined,
    })),
  ]

  if (value && !candidates.some((teacher) => teacher.id === value)) {
    options.push({ value, label: 'Currently assigned teacher' })
  }

  return (
    <div className="teacher-exam-field">
      <span>Lead author <small>(optional)</small></span>
      <SelectControl
        label="Lead author"
        value={value}
        onChange={onChange}
        options={options}
        disabled={disabled || loading || !subjectId || !termId}
      />
      {loading && <small>Loading eligible teachers…</small>}
      {error && <small className="teacher-exam-field__error" role="status">{error}</small>}
    </div>
  )
}
