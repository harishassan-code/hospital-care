import type { ErQueue, ErVisit } from '../../api/emergencies'
import type { Staffing } from '../../api/staffing'

/** Our emergency department now (B22): three waiting (one urgent), one being treated, one waiting for a ward bed. */
export function sampleQueue(now: Date): ErQueue {
  const ago = (min: number) => new Date(now.getTime() - min * 60_000).toISOString()
  const visit = (id: number, tag: string, triage: ErVisit['triage'], status: ErVisit['status'], extra: Partial<ErVisit> = {}): ErVisit => ({
    id,
    tag,
    triage,
    ageBand: '40-64',
    sex: 'M',
    complaint: 'cardiac',
    complaintLabel: 'Chest pain',
    status,
    arrivedAt: ago(40 + id),
    seenAt: status === 'waiting' ? null : ago(20),
    dueAt: null,
    waitedMinutes: status === 'waiting' ? 40 + id : 20,
    bed: status === 'waiting' ? null : `ED-0${id}`,
    handledByStaff: false,
    actions: status === 'waiting' ? ['startTreatment', 'leaveUnseen'] : status === 'treating' ? ['discharge', 'admit', 'transfer'] : ['admit'],
    ...extra,
  })
  return {
    visits: [
      visit(1, 'ED-1001A', 4, 'waiting', { complaint: 'minor', complaintLabel: 'Minor complaint', ageBand: '18-39', sex: 'F' }),
      visit(2, 'ED-1002B', 2, 'waiting'),
      visit(3, 'ED-1003C', 5, 'waiting', { complaint: 'minor', complaintLabel: 'Minor complaint' }),
      visit(4, 'ED-1004D', 3, 'treating'),
      visit(5, 'ED-1005E', 1, 'boarding'),
    ],
    department: { status: 'busy', waitMinutes: 65, waitingCount: 3, updatedAt: now.toISOString(), factors: [], setBySimulation: true },
    beds: { total: 24, free: 6 },
    seenLastHour: 9,
    now: now.toISOString(),
  }
}

/** Staff on duty now (B22): one nurse missing, a department short of nurses. */
export function sampleStaffing(now: Date): Staffing {
  const at = (h: number) => new Date(now.getTime() + h * 3_600_000).toISOString()
  return {
    now: now.toISOString(),
    summary: { doctor: { planned: 2, onDuty: 2, missing: 0 }, nurse: { planned: 3, onDuty: 2, missing: 1 } },
    people: [
      { id: 1, name: 'Dr. Ayesha Khan', role: 'doctor', department: 'Emergency medicine', startsAt: at(-4), endsAt: at(8), clockedInAt: at(-4), clockedOutAt: null, status: 'onDuty', actions: [] },
      { id: 2, name: 'Hira Siddiqui', role: 'nurse', department: 'General medicine', startsAt: at(-2), endsAt: at(4), clockedInAt: null, clockedOutAt: null, status: 'missing', actions: ['clockIn', 'markAbsent'] },
      { id: 3, name: 'Sana Raza', role: 'nurse', department: 'General medicine', startsAt: at(-2), endsAt: at(4), clockedInAt: at(-2), clockedOutAt: null, status: 'onDuty', actions: [] },
    ],
    day: Array.from({ length: 24 }, (_, hour) => ({ hour, plannedDoctors: 2, plannedNurses: 3, ...(hour < 12 ? { doctors: 2, nurses: 2 } : {}) })),
    ratios: [
      { department: 'Emergency medicine', patients: 8, nurses: 3, patientsPerNurse: 2.7, target: 4, short: false },
      { department: 'General medicine', patients: 20, nurses: 1, patientsPerNurse: 20, target: 8, short: true },
    ],
  }
}
