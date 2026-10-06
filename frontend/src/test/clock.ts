/** A fixed date (5 Oct 2026) at the given local "HH:MM", for clock-dependent tests. */
export function at(hhmm: string): Date {
  const date = new Date(2026, 9, 5)
  date.setHours(Number(hhmm.slice(0, 2)), Number(hhmm.slice(3)))
  return date
}

/** `now` shifted by a number of minutes (negative for the past), as an ISO string. */
export function minutesFrom(now: Date, minutes: number): string {
  return new Date(now.getTime() + minutes * 60_000).toISOString()
}
