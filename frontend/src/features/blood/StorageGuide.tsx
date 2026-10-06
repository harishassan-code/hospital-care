import { COMPONENTS, type Component } from '../../api/blood'
import { Panel } from '../../components/ui/Panel'
import styles from './Blood.module.css'

/** The one handling rule per component that most often goes wrong on the floor. */
const HANDLING: Record<Component, string> = {
  redCells: 'Start transfusion within 30 minutes of leaving the fridge.',
  plasma: 'Thaw at 37 °C; use within 24 hours once thawed.',
  platelets: 'Keep at room temperature on the agitator. Never refrigerate.',
  cryo: 'Thaw at 37 °C and use within 4 hours.',
}

export function StorageGuide() {
  return (
    <Panel title="Storage and shelf life">
      <dl className={styles.guide}>
        {COMPONENTS.map((c) => (
          <div key={c.id} className={styles.guideRow}>
            <dt>{c.label}</dt>
            <dd>
              <span className={styles.mono}>
                {c.shelfLifeDays === 365 ? '1 year' : `${c.shelfLifeDays} days`} · {c.storage}
              </span>
              <span>{c.location.join(', ')}</span>
              <span className={styles.handling}>{HANDLING[c.id]}</span>
            </dd>
          </div>
        ))}
      </dl>
    </Panel>
  )
}
