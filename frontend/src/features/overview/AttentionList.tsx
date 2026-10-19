import { Link } from 'react-router-dom'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { useStaff } from '../staff/staffContext'
import styles from './Overview.module.css'

export function AttentionList() {
  const { attention } = useStaff()
  return (
    <Panel
      id="attention"
      title="Needs attention"
      aside={<span className={styles.count}>{attention.length} items</span>}
    >
      {attention.length === 0 ? (
        <p>Nothing needs attention right now.</p>
      ) : (
        <ul className={styles.attention}>
          {attention.map((item) => (
            <li key={item.id} className={styles.attentionItem}>
              <StatusBadge tone={item.severity}>{item.severity === 'critical' ? 'Critical' : 'Warning'}</StatusBadge>
              <Link to={item.href} className={styles.attentionTitle}>
                {item.title}
              </Link>
              <span className={styles.attentionDetail}>{item.detail}</span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}
