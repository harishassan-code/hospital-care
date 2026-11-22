import type { BedType } from '../../api/beds'
import { BLOOD_GROUPS } from '../../api/blood'
import type { HospitalFigures, RedCellFigure, ShortageLevel } from '../../api/commandCentre'
import { formatGroup } from '../blood/blood'

/** How often the figures reload while the page is open and visible (story #55). */
export const REFRESH_MS = 60_000

export const BED_TYPE_LABELS: Record<BedType, string> = {
  icu: 'ICU',
  emergency: 'Emergency',
  general: 'General',
  isolation: 'Isolation',
  nicu: 'NICU',
}

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

/** A short level, in words. Colour may go on top, never instead. */
const SHORT_WORD: Record<'low' | 'critical', string> = { critical: 'Critical', low: 'Low' }

/**
 * A red-cell count with its level in words: "Critical: 1 unit, minimum 4". A cell with no shortage gives the count
 * and the minimum only.
 */
export function levelWords(cell: RedCellFigure): string {
  const count = plural(cell.available, 'unit')
  if (cell.level === 'ok') return `${count}, minimum ${cell.minimum}`
  return `${SHORT_WORD[cell.level]}: ${count}, minimum ${cell.minimum}`
}

/** "2 units expire within 3 days", or "No units expire within 3 days". */
export function nearExpiryWords(count: number, days: number): string {
  const window = `within ${plural(days, 'day')}`
  return count === 0 ? `No units expire ${window}` : `${plural(count, 'unit')} ${count === 1 ? 'expires' : 'expire'} ${window}`
}

/** A hospital's short groups in words: "Short: O− critical, A− low". "No shortages" when there are none. */
export function shortageWords(redCells: { group: RedCellFigure['group']; level?: ShortageLevel }[]): string {
  const short = redCells.flatMap((cell) =>
    cell.level === undefined || cell.level === 'ok' ? [] : [`${formatGroup(cell.group)} ${SHORT_WORD[cell.level].toLowerCase()}`],
  )
  return short.length === 0 ? 'No shortages' : `Short: ${short.join(', ')}`
}

const hospitalsWord = (n: number) => `${n} hospital${n === 1 ? '' : 's'}`

/**
 * One line per blood group that is short at one or more hospitals, with how many are critical and how many low:
 * "O− red cells: 1 hospital critical, 2 hospitals low". Groups with no shortage anywhere are left out.
 */
export function shortageLines(hospitals: HospitalFigures[]): string[] {
  return BLOOD_GROUPS.flatMap((group) => {
    const levels = hospitals.map((hospital) => hospital.redCells.find((cell) => cell.group === group)?.level ?? 'ok')
    const critical = levels.filter((level) => level === 'critical').length
    const low = levels.filter((level) => level === 'low').length
    const parts: string[] = []
    if (critical > 0) parts.push(`${hospitalsWord(critical)} critical`)
    if (low > 0) parts.push(`${hospitalsWord(low)} low`)
    return parts.length === 0 ? [] : [`${formatGroup(group)} red cells: ${parts.join(', ')}`]
  })
}
