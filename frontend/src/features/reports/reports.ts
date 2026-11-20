/**
 * Display rules for the operational reports (B18, #66). The figures come from the server as they are; this only
 * words them.
 */

/** Minutes as people say them: "45 min", "1 h 58 min", "26 h". No value (no cases) shows as a dash. */
export function formatMinutes(minutes: number | null): string {
  if (minutes === null) return '—'
  const whole = Math.round(minutes)
  if (whole < 60) return `${whole} min`
  const hours = Math.floor(whole / 60)
  const rest = whole % 60
  return rest === 0 ? `${hours} h` : `${hours} h ${rest} min`
}

/** "2026-11-01" → "1 Nov 2026". The date is read as a calendar day, so no time zone can move it. */
export function formatDay(day: string): string {
  const [year, month, date] = day.split('-').map(Number)
  return new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(
    new Date(Date.UTC(year, month - 1, date)),
  )
}

/** The component codes the API sends, as the blood bank page names them. */
const COMPONENT_LABEL: Record<string, string> = {
  redCells: 'Red cells',
  plasma: 'Plasma',
  platelets: 'Platelets',
  cryo: 'Cryo',
}

export const componentLabel = (code: string) => COMPONENT_LABEL[code] ?? code
