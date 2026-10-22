/**
 * MVP modules that have a route but no page yet (issue #5: route placeholders for every MVP module).
 * Each gets its real page, nav entry and access rule in the sprint shown; remove it from here then.
 */
export const PLANNED: readonly { path: string; label: string; sprint: number; issues: string }[] = [
  { path: '/staff/donors', label: 'Donors', sprint: 3, issues: '#20–#22' },
  { path: '/staff/operating-rooms', label: 'Operating rooms', sprint: 4, issues: '#28–#29' },
  { path: '/staff/emergencies', label: 'Emergency requests', sprint: 5, issues: '#30–#36' },
  { path: '/staff/matching', label: 'Matching', sprint: 6, issues: '#37–#42' },
  { path: '/staff/transfers', label: 'Transfers', sprint: 7, issues: '#47–#49' },
  { path: '/staff/ambulances', label: 'Ambulances', sprint: 8, issues: '#50–#51' },
  { path: '/staff/alerts', label: 'Alerts', sprint: 8, issues: '#52–#53' },
  { path: '/staff/command-centre', label: 'City command centre', sprint: 8, issues: '#55' },
  { path: '/staff/audit', label: 'Audit log', sprint: 8, issues: '#56' },
]
