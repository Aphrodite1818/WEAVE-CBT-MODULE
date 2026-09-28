const CURRENT_ROSTER_EXAM_STATES = new Set([
  'sealed',
  'active',
  'suspended',
  'closing',
  'cancelling',
])

const TERMINAL_EXAM_STATES = new Set(['closed', 'cancelled'])

function hasPreparedRoster(exam) {
  return exam?.rosterStatus && exam.rosterStatus !== 'not_prepared'
}

function revisionNumber(exam) {
  return Number(exam?.revisionNumber || 1)
}

function timeValue(value) {
  const parsed = value ? new Date(value).getTime() : 0
  return Number.isFinite(parsed) ? parsed : 0
}

function compareRevisionDesc(left, right) {
  const revisionDelta = revisionNumber(right) - revisionNumber(left)
  if (revisionDelta) return revisionDelta
  return timeValue(right.createdAt) - timeValue(left.createdAt)
}

export function buildRosterLineageIndex(exams = []) {
  const rows = Array.isArray(exams) ? exams : []
  const byId = new Map(rows.map((exam) => [exam.id, exam]))
  const parentIds = new Set(
    rows.map((exam) => exam.revisionOfExamId).filter(Boolean),
  )

  const rootIdFor = (exam) => {
    let current = exam
    const visited = new Set()
    while (
      current?.revisionOfExamId &&
      byId.has(current.revisionOfExamId) &&
      !visited.has(current.revisionOfExamId)
    ) {
      visited.add(current.id)
      current = byId.get(current.revisionOfExamId)
    }
    return current?.id || exam.id
  }

  const lineageByRoot = new Map()
  for (const exam of rows) {
    const rootId = rootIdFor(exam)
    const lineage = lineageByRoot.get(rootId) || []
    lineage.push(exam)
    lineageByRoot.set(rootId, lineage)
  }
  for (const lineage of lineageByRoot.values()) {
    lineage.sort(compareRevisionDesc)
  }

  return { byId, parentIds, lineageByRoot, rootIdFor }
}

export function isSupersededRevision(exam, exams = []) {
  if (!exam) return false
  return buildRosterLineageIndex(exams).parentIds.has(exam.id)
}

export function rosterHistoryKind(exam, exams = []) {
  if (!exam || !hasPreparedRoster(exam)) return null
  if (isSupersededRevision(exam, exams)) return 'superseded'
  if (TERMINAL_EXAM_STATES.has(exam.status)) return exam.status
  return null
}

export function isHistoricalRoster(exam, exams = []) {
  return Boolean(rosterHistoryKind(exam, exams))
}

export function partitionRosterExams(exams = []) {
  const rows = Array.isArray(exams) ? exams : []
  const index = buildRosterLineageIndex(rows)
  const prepared = rows.filter(hasPreparedRoster)

  const current = prepared
    .filter(
      (exam) =>
        !index.parentIds.has(exam.id) &&
        CURRENT_ROSTER_EXAM_STATES.has(exam.status),
    )
    .sort((left, right) => {
      const leftTime = timeValue(left.scheduledStartAt) || timeValue(left.createdAt)
      const rightTime = timeValue(right.scheduledStartAt) || timeValue(right.createdAt)
      return rightTime - leftTime
    })

  const historyByRoot = new Map()
  for (const exam of prepared) {
    const historical =
      index.parentIds.has(exam.id) || TERMINAL_EXAM_STATES.has(exam.status)
    if (!historical) continue

    const rootId = index.rootIdFor(exam)
    const group = historyByRoot.get(rootId) || []
    group.push(exam)
    historyByRoot.set(rootId, group)
  }

  const historyGroups = [...historyByRoot.entries()]
    .map(([rootId, entries]) => {
      entries.sort(compareRevisionDesc)
      const lineage = index.lineageByRoot.get(rootId) || entries
      const representative = lineage[0] || entries[0]
      return {
        id: rootId,
        title: representative?.title || 'Examination roster',
        academicLevelName: representative?.academicLevelName || '',
        subjectName: representative?.subjectName || '',
        assessmentName: representative?.assessmentName || '',
        latestRevisionNumber: revisionNumber(representative),
        entries,
      }
    })
    .sort((left, right) => {
      const leftExam = left.entries[0]
      const rightExam = right.entries[0]
      const leftTime = timeValue(leftExam?.updatedAt) || timeValue(leftExam?.createdAt)
      const rightTime = timeValue(rightExam?.updatedAt) || timeValue(rightExam?.createdAt)
      return rightTime - leftTime
    })

  return { current, historyGroups }
}

export function rosterHistoryLabel(kind) {
  if (kind === 'superseded') return 'Superseded'
  if (kind === 'closed') return 'Closed'
  if (kind === 'cancelled') return 'Cancelled'
  return 'Historical'
}

export function rosterHistoryDescription(exam, exams = []) {
  const kind = rosterHistoryKind(exam, exams)
  if (kind === 'superseded') {
    return `Revision ${revisionNumber(exam)} was replaced by a later exam revision. Its roster is preserved for audit and is read-only.`
  }
  if (kind === 'closed') {
    return 'This examination is closed. Its final candidate roster is preserved for audit and remains available to review.'
  }
  if (kind === 'cancelled') {
    return 'This examination was cancelled. Its candidate roster is preserved as historical scheduling evidence.'
  }
  return ''
}
