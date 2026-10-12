import { StatusBadge } from '../../components/ui/StatusBadge'

/** Whether a hospital takes part in the network. Deactivated hospitals are kept, never deleted. */
export function ActiveBadge({ active }: { active: boolean }) {
  return active ? <StatusBadge tone="ok">Active</StatusBadge> : <StatusBadge tone="neutral">Deactivated</StatusBadge>
}
