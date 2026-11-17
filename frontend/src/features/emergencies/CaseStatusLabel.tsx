import type { CaseStatus } from '../../api/emergencies'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { STATUS_LABEL } from './emergencies'

/**
 * A case's status as text. An escalated case (story #35) gets a badge: its icon and its words flag it, not its colour.
 */
export function CaseStatusLabel({ status }: { status: CaseStatus }) {
  if (status === 'escalated') return <StatusBadge tone="critical">{STATUS_LABEL[status]}</StatusBadge>
  return <>{STATUS_LABEL[status]}</>
}
