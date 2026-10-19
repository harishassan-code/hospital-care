/**
 * The three floor lines, in the order their destinations appear on the page.
 * Line i sits at x = 72 − 24i px in the gutter: the first destination's line is innermost,
 * so when it turns right into its section it never crosses a line that is still running.
 */
export const LINES = [
  { id: 'emergency', label: 'Emergency', color: 'var(--line-emergency)' },
  { id: 'doctors', label: 'Doctors today', color: 'var(--line-clinics)' },
  { id: 'sign-in', label: 'Sign in', color: 'var(--line-portal)' },
] as const

export const ALL_LINES = LINES.map((_, i) => i)
