import styles from './CityNetwork.module.css'

// Hospitals on a city grid, joined by routes: what CityCare does, as a picture. Decorative (aria-hidden): the page
// says it in words. Colours come from the theme tokens, so it follows dark mode; motion stops under reduced motion.
const NODES: readonly { x: number; y: number; main?: boolean; target?: boolean }[] = [
  { x: 110, y: 94, main: true },
  { x: 320, y: 158 },
  { x: 460, y: 94 },
  { x: 180, y: 286 },
  { x: 420, y: 318, target: true },
]
const ROUTES: readonly { from: number; to: number; live?: boolean }[] = [
  { from: 0, to: 1 },
  { from: 1, to: 2 },
  { from: 1, to: 4, live: true },
  { from: 0, to: 3 },
  { from: 3, to: 4 },
]
const COLUMNS = [40, 110, 180, 250, 320, 390, 460, 530]
const ROWS = [30, 94, 158, 222, 286, 350, 414]

function routePath(a: (typeof NODES)[number], b: (typeof NODES)[number]) {
  const mid = (a.y + b.y) / 2
  return `M${a.x} ${a.y} L${a.x} ${mid} L${b.x} ${mid} L${b.x} ${b.y}`
}

export function CityNetwork({ className }: { className?: string }) {
  return (
    <svg className={`${styles.art} ${className ?? ''}`} viewBox="0 0 560 420" aria-hidden="true" focusable="false">
      <rect className={styles.ground} width="560" height="420" rx="28" />
      {COLUMNS.map((x, i) => (
        <path key={`c${x}`} className={styles.street} d={`M${x} 0V420`} strokeWidth={i % 2 === 0 ? 10 : 4} />
      ))}
      {ROWS.map((y, i) => (
        <path key={`r${y}`} className={styles.street} d={`M0 ${y}H560`} strokeWidth={i % 2 === 0 ? 10 : 4} />
      ))}
      <path className={styles.river} d="M-20 360 C 120 300, 220 380, 360 250 S 520 120, 600 90" />
      {ROUTES.map((r, i) => (
        <path
          key={`${r.from}-${r.to}`}
          className={r.live ? styles.liveRoute : styles.route}
          d={routePath(NODES[r.from], NODES[r.to])}
          style={{ animationDelay: `${150 + i * 120}ms` }}
        />
      ))}
      {NODES.map((n) => {
        const r = n.main ? 30 : 22
        return (
          <g key={`${n.x}-${n.y}`}>
            {n.target && <circle className={styles.pulse} cx={n.x} cy={n.y} r={r + 10} />}
            <rect
              className={n.main ? styles.mainNode : styles.node}
              x={n.x - r}
              y={n.y - r}
              width={2 * r}
              height={2 * r}
              rx={r / 2.6}
            />
            <path
              className={n.main ? styles.mainCross : styles.cross}
              d={`M${n.x} ${n.y - r * 0.45}V${n.y + r * 0.45}M${n.x - r * 0.45} ${n.y}H${n.x + r * 0.45}`}
              strokeWidth={n.main ? 7 : 5}
            />
          </g>
        )
      })}
      <g className={styles.ambulance}>
        <rect x="378" y="226" width="34" height="20" rx="6" />
        <path d="M389 236h12M395 230v12" />
      </g>
    </svg>
  )
}
