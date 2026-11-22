import type { ReactNode } from 'react'
import { BLOOD_GROUPS, COMPONENTS, type BloodGroup } from '../../api/blood'
import type { BedType } from '../../api/beds'
import type { CommandCentre, ComponentFigure, Figures, ShortageLevel } from '../../api/commandCentre'
import { EQUIPMENT_TYPES } from '../../api/equipment'
import type { ResourceType } from '../../api/emergencies'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { formatClock } from '../../lib/time'
import { formatGroup } from '../blood/blood'
import { BED_TYPE_LABELS, levelWords, nearExpiryWords, shortageLines, shortageWords } from './rules'
import styles from './CommandCentre.module.css'

/** A red-cell figure: a hospital's has a level, the network total has only the count. */
type Red = { group: BloodGroup; available: number; minimum?: number; level?: ShortageLevel }
type Column = { key: string; name: string; total: boolean; figures: Figures<Red> }
type Row = { label: string; cell: (column: Column) => ReactNode }
type Section = { title: string; rows: Row[] }

const OPEN_NEED_LABELS: Record<ResourceType, string> = {
  blood: 'Blood',
  bed: 'Beds',
  equipment: 'Equipment',
  operatingRoom: 'Operating rooms',
}

const BED_TYPES = Object.keys(BED_TYPE_LABELS) as BedType[]

function redCell(redCells: Red[], group: BloodGroup): ReactNode {
  const cell = redCells.find((c) => c.group === group)
  if (!cell) return null
  if (cell.level === undefined || cell.minimum === undefined) return `${cell.available} units`
  const text = levelWords({ group, available: cell.available, minimum: cell.minimum, level: cell.level })
  if (cell.level === 'ok') return text
  return <StatusBadge tone={cell.level === 'critical' ? 'critical' : 'warning'}>{text}</StatusBadge>
}

function usableCell(figure: ComponentFigure, days: number): ReactNode {
  return (
    <>
      <span className={styles.count}>{figure.usable} usable</span>
      <span className={styles.note}>{nearExpiryWords(figure.nearExpiry, days)}</span>
    </>
  )
}

function sectionsFor(days: number): Section[] {
  return [
    {
      title: 'Blood: shortages',
      rows: [{ label: 'Shortages', cell: (column) => (column.total ? null : shortageWords(column.figures.redCells)) }],
    },
    {
      title: 'Blood: red cells, with minimum',
      rows: BLOOD_GROUPS.map((group) => ({
        label: `${formatGroup(group)} red cells`,
        cell: (column) => redCell(column.figures.redCells, group),
      })),
    },
    {
      title: 'Blood: usable units and near expiry',
      rows: COMPONENTS.map((component) => ({
        label: component.label,
        cell: (column) => usableCell(column.figures.components[component.id], days),
      })),
    },
    {
      title: 'Beds free',
      rows: BED_TYPES.map((type) => ({ label: BED_TYPE_LABELS[type], cell: (column) => column.figures.beds[type] })),
    },
    {
      title: 'Equipment available',
      rows: EQUIPMENT_TYPES.map(({ value, label }) => ({
        label,
        cell: (column) => column.figures.equipment[value],
      })),
    },
    {
      title: 'Operating rooms',
      rows: [{ label: 'Available', cell: (column) => column.figures.operatingRooms }],
    },
    {
      title: 'Emergencies',
      rows: [
        { label: 'Active cases', cell: (column) => column.figures.cases.active },
        { label: 'Of which escalated', cell: (column) => column.figures.cases.escalated },
        ...(Object.keys(OPEN_NEED_LABELS) as ResourceType[]).map((kind) => ({
          label: `Open needs: ${OPEN_NEED_LABELS[kind]}`,
          cell: (column: Column) => column.figures.open[kind],
        })),
      ],
    },
  ]
}

/**
 * The command centre's figures (story #55). A summary of the shortages in words, then one table with a column per
 * hospital and a column for the network. Hospitals with a critical shortage come first (the server sorts them).
 */
export function CommandCentreBoard({ figures, stale }: { figures: CommandCentre; stale: boolean }) {
  const { hospitals, totals, nearExpiryDays: days } = figures
  const clock = formatClock(new Date(figures.updatedAt))
  const lines = shortageLines(hospitals)
  const networkNearExpiry = COMPONENTS.reduce((sum, c) => sum + totals.components[c.id].nearExpiry, 0)

  return (
    <div className={styles.stack}>
      <p className={styles.meta}>
        Figures as of {clock}. They refresh every minute while this page is open.
      </p>
      {stale && (
        <p role="alert" className={styles.alert}>
          The figures may be out of date. The last refresh failed, so these are from {clock}. The page will try again in a
          minute.
        </p>
      )}

      <Panel title="Shortages" id="shortages">
        {lines.length === 0 ? (
          <p>No blood group is short at any hospital.</p>
        ) : (
          <ul className={styles.list}>
            {lines.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        )}
        <p className={styles.note}>{nearExpiryWords(networkNearExpiry, days)} across the network.</p>
      </Panel>

      <Panel title="Hospitals" id="network-figures">
        {hospitals.length === 0 ? (
          <p>There are no active hospitals in the network yet.</p>
        ) : (
          <Board
            columns={[
              ...hospitals.map((h) => ({ key: String(h.id), name: h.name, total: false, figures: h })),
              { key: 'network', name: 'All hospitals', total: true, figures: totals },
            ]}
            sections={sectionsFor(days)}
          />
        )}
      </Panel>
    </div>
  )
}

function Board({ columns, sections }: { columns: Column[]; sections: Section[] }) {
  return (
    <div className="table-scroll">
      <table className={styles.board}>
        <caption className="visually-hidden">Network figures, one column per hospital and one for the network</caption>
        <thead>
          <tr>
            <th scope="col">Measure</th>
            {columns.map((column) => (
              <th key={column.key} scope="col" className={column.total ? styles.total : undefined}>
                {column.name}
              </th>
            ))}
          </tr>
        </thead>
        {sections.map((section) => (
          <tbody key={section.title}>
            <tr className={styles.section}>
              <th scope="colgroup" colSpan={columns.length + 1}>
                {section.title}
              </th>
            </tr>
            {section.rows.map((row) => (
              <tr key={row.label}>
                <th scope="row">{row.label}</th>
                {columns.map((column) => (
                  <td key={column.key} className={column.total ? styles.total : undefined}>
                    {row.cell(column)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        ))}
      </table>
    </div>
  )
}
