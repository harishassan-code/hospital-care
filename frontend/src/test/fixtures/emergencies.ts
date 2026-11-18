import type { Candidate, CandidatesResponse, EmergencyCase, FeedEntry } from '../../api/emergencies'

/**
 * What CityCare General has free for each sample case's needs, in item order (story #33). EC-2026-0002 is short
 * (1 of 4 O− red cells, no ICU bed: 4 needed elsewhere); EC-2026-0001 is covered (2 of 2 general beds).
 */
export const sampleLocalAvailable: Record<string, number[]> = {
  'EC-2026-0002': [1, 0],
  'EC-2026-0001': [2],
  'EC-2026-0003': [1, 0],
}

/** Two cases at CityCare General, in the order the server lists them. Fresh copies every call. */
export function sampleCases(now: Date): EmergencyCase[] {
  const minutesAgo = (m: number) => new Date(now.getTime() - m * 60_000).toISOString()
  const hospital = { id: 1, name: 'CityCare General Hospital' }
  return [
    {
      id: 'EC-2026-0002',
      severity: 'critical',
      status: 'open',
      patientRef: 'Bay 4',
      hospital,
      createdBy: 'Dr. Ayesha Khan',
      createdAt: minutesAgo(12),
      items: [
        { type: 'blood', group: 'O-', component: 'redCells', quantity: 4 },
        { type: 'bed', bedType: 'icu', quantity: 1 },
      ],
    },
    {
      id: 'EC-2026-0001',
      severity: 'moderate',
      status: 'open',
      patientRef: '',
      hospital,
      createdBy: 'Hina Javed',
      createdAt: minutesAgo(180),
      items: [{ type: 'bed', bedType: 'general', quantity: 2 }],
    },
  ]
}

/**
 * Active requests at another hospital, Riverside Medical Centre, as the network feed lists them (story #36). Their
 * ids are not CityCare's, so the feed shows them without a link.
 */
export function sampleNetworkRequests(now: Date): FeedEntry[] {
  const minutesAgo = (m: number) => new Date(now.getTime() - m * 60_000).toISOString()
  const hospital = { id: 2, name: 'Riverside Medical Centre' }
  return [
    {
      reference: 'EC-2026-0007',
      hospital,
      severity: 'critical',
      status: 'matching',
      createdAt: minutesAgo(40),
      needs: [{ type: 'blood', group: 'O-', component: 'redCells', quantity: 6, fulfilled: 2 }],
    },
    {
      reference: 'EC-2026-0008',
      hospital,
      severity: 'high',
      status: 'escalated',
      createdAt: minutesAgo(200),
      needs: [
        { type: 'blood', group: 'AB+', component: 'platelets', quantity: 1, fulfilled: 0 },
        { type: 'bed', bedType: 'icu', quantity: 1, fulfilled: 0 },
      ],
    },
    {
      reference: 'EC-2026-0009',
      hospital,
      severity: 'moderate',
      status: 'open',
      createdAt: minutesAgo(15),
      needs: [{ type: 'bed', bedType: 'general', quantity: 2, fulfilled: 0 }],
    },
  ]
}

/**
 * A case with the newer kinds of need (#32, completed in #38): two ventilators, one of them here, and a cardiac
 * theatre, none here. Not in `sampleCases`, so the list tests keep their order; the case page tests use it directly.
 */
export function sampleNewNeedsCase(now: Date): EmergencyCase {
  return {
    id: 'EC-2026-0003',
    severity: 'high',
    status: 'open',
    patientRef: '',
    hospital: { id: 1, name: 'CityCare General Hospital' },
    createdBy: 'Dr. Usman Farooq',
    createdAt: new Date(now.getTime() - 30 * 60_000).toISOString(),
    items: [
      { type: 'equipment', equipmentType: 'ventilator', quantity: 2 },
      { type: 'operatingRoom', capability: 'cardiac', quantity: 1 },
    ],
  }
}

/**
 * The sources for the sample cases (stories #38 and #41), as the server returns them: only the short needs, ranked.
 * EC-2026-0002 is short of blood and an ICU bed. For the blood, Riverside has 5 O− red cells expiring in 9 days, which
 * covers it, and scores 87.6, so it is recommended; Northside has 1, expiring in 3 days, with no known distance, and
 * scores 69.7. No other hospital has an ICU bed. EC-2026-0003 is short of one ventilator and a cardiac theatre; Riverside
 * has a ventilator and scores 94.1 on nearest-first, and nobody has a cardiac theatre free. EC-2026-0001 is covered
 * locally, so it has no items.
 */
export function sampleCandidates(now: Date): Record<string, CandidatesResponse> {
  const expiresIn = (days: number) => new Date(now.getTime() + days * 86_400_000).toISOString()
  const riverside = { id: 2, name: 'Riverside Medical Centre' }
  const northside = { id: 3, name: "Northside Children's Hospital" }
  const earliestExpiry = { name: 'earliestExpiry', label: 'Earliest expiry first' }
  const nearest = { name: 'nearest', label: 'Nearest first' }
  return {
    'EC-2026-0002': {
      reference: 'EC-2026-0002',
      items: [
        {
          itemId: 1,
          need: 'O- red cells',
          shortfall: 3,
          strategy: earliestExpiry,
          candidates: [
            {
              hospital: riverside,
              available: 5,
              covers: true,
              distanceKm: 4.2,
              travelMinutes: 6,
              earliestExpiry: expiresIn(9),
              bestDonorRank: 0,
              rank: 1,
              recommended: true,
              score: {
                total: 87.6,
                strategy: 'earliestExpiry',
                factors: [
                  { name: 'expiry', label: 'Expiry', value: 0.79, weight: 0.5, points: 39.3, detail: 'expires in 9 days' },
                  { name: 'compatibility', label: 'Blood group match', value: 1, weight: 0.2, points: 20, detail: 'identical group' },
                  { name: 'distance', label: 'Distance', value: 0.92, weight: 0.2, points: 18.3, detail: '4.2 km, about 6 min' },
                  { name: 'quantity', label: 'Stock', value: 1, weight: 0.1, points: 10, detail: '5 available, 3 needed' },
                ],
              },
            },
            {
              hospital: northside,
              available: 1,
              covers: false,
              distanceKm: null,
              travelMinutes: null,
              earliestExpiry: expiresIn(3),
              bestDonorRank: 0,
              rank: 2,
              recommended: false,
              score: {
                total: 69.7,
                strategy: 'earliestExpiry',
                factors: [
                  { name: 'expiry', label: 'Expiry', value: 0.93, weight: 0.5, points: 46.4, detail: 'expires in 3 days' },
                  { name: 'compatibility', label: 'Blood group match', value: 1, weight: 0.2, points: 20, detail: 'identical group' },
                  { name: 'distance', label: 'Distance', value: 0, weight: 0.2, points: 0, detail: 'distance unknown' },
                  { name: 'quantity', label: 'Stock', value: 0.33, weight: 0.1, points: 3.3, detail: '1 available, 3 needed' },
                ],
              },
            },
          ],
        },
        { itemId: 2, need: 'ICU bed', shortfall: 1, strategy: nearest, candidates: [] },
      ],
      hospitals: [
        {
          rank: 1,
          hospital: riverside,
          complete: false,
          recommended: false,
          coverage: '1 of 2',
          coveredCount: 1,
          totalNeeds: 2,
          score: 87.6,
          distanceKm: 4.2,
          travelMinutes: 6,
          covered: [{ itemId: 1, need: 'O- red cells' }],
          unmet: [{ itemId: 2, need: 'ICU bed', missing: 1, available: 0 }],
        },
        {
          rank: 2,
          hospital: northside,
          complete: false,
          recommended: false,
          coverage: '0 of 2',
          coveredCount: 0,
          totalNeeds: 2,
          score: 69.7,
          distanceKm: null,
          travelMinutes: null,
          covered: [],
          unmet: [
            { itemId: 1, need: 'O- red cells', missing: 2, available: 1 },
            { itemId: 2, need: 'ICU bed', missing: 1, available: 0 },
          ],
        },
      ],
    },
    'EC-2026-0003': {
      reference: 'EC-2026-0003',
      items: [
        {
          itemId: 1,
          need: 'Ventilator',
          shortfall: 1,
          strategy: nearest,
          candidates: [
            {
              hospital: riverside,
              available: 2,
              covers: true,
              distanceKm: 4.2,
              travelMinutes: 6,
              rank: 1,
              recommended: true,
              score: {
                total: 94.1,
                strategy: 'nearest',
                factors: [
                  { name: 'distance', label: 'Distance', value: 0.92, weight: 0.7, points: 64.1, detail: '4.2 km, about 6 min' },
                  { name: 'quantity', label: 'Stock', value: 1, weight: 0.3, points: 30, detail: '2 available, 1 needed' },
                ],
              },
            },
          ],
        },
        { itemId: 2, need: 'Cardiac operating room', shortfall: 1, strategy: nearest, candidates: [] },
      ],
      hospitals: [
        {
          rank: 1,
          hospital: riverside,
          complete: false,
          recommended: false,
          coverage: '1 of 2',
          coveredCount: 1,
          totalNeeds: 2,
          score: 94.1,
          distanceKm: 4.2,
          travelMinutes: 6,
          covered: [{ itemId: 1, need: 'Ventilator' }],
          unmet: [{ itemId: 2, need: 'Cardiac operating room', missing: 1, available: 0 }],
        },
      ],
    },
    'EC-2026-0001': { reference: 'EC-2026-0001', items: [], hospitals: [] },
  }
}

/**
 * Three short needs at once (story #42): an ICU bed, two ventilators and two O− red cells. The first hospital has all
 * of them, so it is complete and recommended. The second has the bed and one unit of blood. The third has one
 * ventilator. The server lists them in that order, which is not alphabetical, so a screen that re-sorted would show it.
 * The per-need lists carry the same stock.
 */
export function sampleThreeNeedSources(): CandidatesResponse {
  const full = { id: 2, name: 'Riverside Medical Centre' }
  const partial = { id: 3, name: "Northside Children's Hospital" }
  const sea = { id: 4, name: 'Seaview Hospital' }
  const nearest = { name: 'nearest', label: 'Nearest first' }
  const offer = (hospital: { id: number; name: string }, available: number, shortfall: number, rank: number, total: number): Candidate => ({
    hospital,
    available,
    covers: available >= shortfall,
    distanceKm: hospital === full ? 4.2 : null,
    travelMinutes: hospital === full ? 6 : null,
    rank,
    recommended: rank === 1 && total > 0,
    score: { total, strategy: 'nearest', factors: [] },
  })
  return {
    reference: 'EC-2026-0002',
    items: [
      {
        itemId: 2,
        need: 'ICU bed',
        shortfall: 1,
        strategy: nearest,
        candidates: [offer(full, 1, 1, 1, 92), offer(partial, 1, 1, 2, 60)],
      },
      {
        itemId: 3,
        need: 'Ventilator',
        shortfall: 2,
        strategy: nearest,
        candidates: [offer(full, 2, 2, 1, 94), offer(sea, 1, 2, 2, 30)],
      },
      {
        itemId: 1,
        need: 'O- red cells',
        shortfall: 2,
        strategy: nearest,
        candidates: [offer(full, 5, 2, 1, 80), offer(partial, 1, 2, 2, 40)],
      },
    ],
    hospitals: [
      {
        rank: 1,
        hospital: full,
        complete: true,
        recommended: true,
        coverage: '3 of 3',
        coveredCount: 3,
        totalNeeds: 3,
        score: 88.7,
        distanceKm: 4.2,
        travelMinutes: 6,
        covered: [
          { itemId: 2, need: 'ICU bed' },
          { itemId: 3, need: 'Ventilator' },
          { itemId: 1, need: 'O- red cells' },
        ],
        unmet: [],
      },
      {
        rank: 2,
        hospital: partial,
        complete: false,
        recommended: false,
        coverage: '1 of 3',
        coveredCount: 1,
        totalNeeds: 3,
        score: 50,
        distanceKm: null,
        travelMinutes: null,
        covered: [{ itemId: 2, need: 'ICU bed' }],
        unmet: [
          { itemId: 3, need: 'Ventilator', missing: 2, available: 0 },
          { itemId: 1, need: 'O- red cells', missing: 1, available: 1 },
        ],
      },
      {
        rank: 3,
        hospital: sea,
        complete: false,
        recommended: false,
        coverage: '0 of 3',
        coveredCount: 0,
        totalNeeds: 3,
        score: 30,
        distanceKm: null,
        travelMinutes: null,
        covered: [],
        unmet: [
          { itemId: 2, need: 'ICU bed', missing: 1, available: 0 },
          { itemId: 3, need: 'Ventilator', missing: 1, available: 1 },
          { itemId: 1, need: 'O- red cells', missing: 2, available: 0 },
        ],
      },
    ],
  }
}
