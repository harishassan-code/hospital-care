import styles from './Charts.module.css'

/** A small line with no axes, for a figure's shape at a glance (B22). The figure itself is written beside it. */
export function Sparkline({ values, label, width = 96, height = 28, max }: { values: number[]; label: string; width?: number; height?: number; max?: number }) {
  if (values.length < 2) return null
  const top = max ?? Math.max(1, ...values)
  const step = width / (values.length - 1)
  const d = values.map((v, i) => `${i ? 'L' : 'M'}${(i * step).toFixed(1)},${(height - 2 - (v / top) * (height - 4)).toFixed(1)}`).join('')
  return (
    <svg width={width} height={height} className={styles.spark} role="img" aria-label={label}>
      <path d={d} className={styles.line} />
    </svg>
  )
}
