import type { Report } from '../../api/reports'

/** Synthetic report figures (B18, #66) for a range and hospital, as `GET /api/reports/` shapes them. */
export function sampleReport(range: Report['range'], hospital: Report['hospital'] = null): Report {
  const severities = [
    ['critical', 'Critical'],
    ['high', 'High'],
    ['moderate', 'Moderate'],
    ['low', 'Low'],
  ] as const
  const cases = [3, 4, 1, 0]
  return {
    range,
    hospital,
    generatedAt: '2026-11-20T12:00:00+05:00',
    requests: {
      total: 8,
      allocations: 11,
      bySeverity: severities.map(([id, label], i) => ({ id, label, count: cases[i]! })),
      byStatus: [
        { id: 'open', label: 'Open', count: 2 },
        { id: 'fulfilled', label: 'Fulfilled', count: 5 },
        { id: 'escalated', label: 'Escalated', count: 1 },
        { id: 'cancelled', label: 'Cancelled', count: 0 },
      ],
      byResourceType: [
        { id: 'blood', label: 'Blood', needs: 6, unitsAsked: 14, unitsAllocated: 9 },
        { id: 'bed', label: 'Bed', needs: 1, unitsAsked: 1, unitsAllocated: 0 },
        { id: 'equipment', label: 'Equipment', needs: 2, unitsAsked: 3, unitsAllocated: 2 },
        { id: 'operatingRoom', label: 'Operating room', needs: 0, unitsAsked: 0, unitsAllocated: 0 },
      ],
    },
    fulfilment: {
      overall: { count: 5, medianMinutes: 42, averageMinutes: 55.4, p90Minutes: 118 },
      bySeverity: severities.map(([id, label], i) =>
        i < 2
          ? { id, label, count: [3, 2][i]!, medianMinutes: [30, 75][i]!, averageMinutes: [35.5, 85][i]!, p90Minutes: [60, 118][i]! }
          : { id, label, count: 0, medianMinutes: null, averageMinutes: null, p90Minutes: null },
      ),
      notFulfilled: [{ id: 'escalated', label: 'Escalated', count: 1 }],
    },
    wastage: {
      expired: 3,
      discarded: 1,
      rows: [
        { hospital: 'CityCare General Hospital', group: 'O-', component: 'redCells', expired: 2, discarded: 1 },
        { hospital: 'Seaview Hospital', group: 'A+', component: 'plasma', expired: 1, discarded: 0 },
      ],
    },
  }
}
