import { Link } from 'react-router-dom'
import { TRANSFER_STATUS_LABEL, type Transfer } from '../../api/transfers'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { withMinus } from '../emergencies/emergencies'
import { TRANSFER_TONE } from './transfers'
import styles from './Transfers.module.css'

/**
 * The transfers asked for this case (story #48), so staff see what is on its way: each need, the hospital supplying it, its
 * status in words, how many are approved, and a way to the Transfers page.
 */
export function CaseTransfers({ transfers }: { transfers: Transfer[] }) {
  return (
    <Panel title="Transfers" id="case-transfers">
      <ul className={styles.caseTransfers}>
        {transfers.map((transfer) => (
          <li key={transfer.id} className={styles.caseTransfer}>
            <div className={styles.caseTransferTop}>
              <strong>{withMinus(transfer.need)}</strong>
              <StatusBadge tone={TRANSFER_TONE[transfer.status]}>{TRANSFER_STATUS_LABEL[transfer.status]}</StatusBadge>
            </div>
            <div>
              <span>Transfer #{transfer.id}</span>
              {' · '}
              <span>From {transfer.supplier.name}</span>
              {' · '}
              <span>{`${transfer.approved} of ${transfer.quantity} approved`}</span>
            </div>
            <Link to={{ pathname: '/staff/transfers', search: '?direction=outgoing' }} className={styles.link}>
              Open in Transfers
            </Link>
          </li>
        ))}
      </ul>
    </Panel>
  )
}
