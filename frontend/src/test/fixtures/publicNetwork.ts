import type { DepartmentStatus } from '../../api/emergencies'
import type { NetworkSnapshot, PublicHospital, PublicHospitalDetail } from '../../api/public'

/** Three member hospitals and a blood bank, as GET /api/public/hospitals/ returns them (B19). */
export function samplePublicHospitals(now: Date): PublicHospital[] {
  const at = now.toISOString()
  return [
    {
      id: 1,
      name: 'CityCare General Hospital',
      type: 'hospital',
      address: 'Shahrah-e-Faisal, Karachi',
      latitude: 24.8607,
      longitude: 67.0011,
      phone: '+92 21 111 000 111',
      services: ['Trauma centre', 'ICU', 'Blood bank', 'Maternity', 'CT scanner', 'Paediatrics'],
      emergency: { status: 'accepting', waitMinutes: 24, waitingCount: 7, updatedAt: at },
    },
    {
      id: 2,
      name: 'Seaview Hospital',
      type: 'hospital',
      address: 'Clifton Block 5, Karachi',
      latitude: 24.8138,
      longitude: 67.0299,
      phone: '+92 21 111 000 222',
      services: ['ICU', 'Cath lab'],
      emergency: { status: 'busy', waitMinutes: 75, waitingCount: 16, updatedAt: at },
    },
    {
      id: 3,
      name: 'Northside Children’s Hospital',
      type: 'hospital',
      address: 'North Nazimabad, Karachi',
      latitude: 24.942,
      longitude: 67.0347,
      phone: '+92 21 111 000 333',
      services: ['NICU', 'Paediatrics'],
      emergency: { status: 'diverting', waitMinutes: 10, waitingCount: 3, updatedAt: at },
    },
    {
      id: 4,
      name: 'Karachi Regional Blood Centre',
      type: 'bloodBank',
      address: 'Jamshed Road, Karachi',
      latitude: 24.877,
      longitude: 67.041,
      phone: '',
      services: [],
      emergency: null,
    },
  ]
}

export function sampleNetwork(now: Date): NetworkSnapshot {
  return {
    updatedAt: now.toISOString(),
    hospitals: 4,
    emergency: {
      accepting: 1,
      busy: 1,
      diverting: 1,
      notReported: 1,
      shortestWait: { hospitalId: 1, name: 'CityCare General Hospital', waitMinutes: 24 },
    },
    beds: [
      { bedType: 'icu', level: 'limited' },
      { bedType: 'emergency', level: 'available' },
      { bedType: 'general', level: 'available' },
      { bedType: 'nicu', level: 'full' },
    ],
    blood: [
      { group: 'O-', level: 'low' },
      { group: 'O+', level: 'ok' },
      { group: 'A-', level: 'critical' },
      { group: 'A+', level: 'ok' },
      { group: 'B-', level: 'ok' },
      { group: 'B+', level: 'ok' },
      { group: 'AB-', level: 'low' },
      { group: 'AB+', level: 'ok' },
    ],
    ambulances: { available: 5, total: 8 },
  }
}

/** One hospital's page; names only when `namesShown`, as for signed-in staff. */
export function samplePublicHospitalDetail(now: Date, id = 2, namesShown = false): PublicHospitalDetail {
  const base = samplePublicHospitals(now).find((h) => h.id === id) ?? samplePublicHospitals(now)[1]
  return {
    ...base,
    departments: ['Cardiology', 'Emergency medicine', 'General medicine'],
    beds: [
      { bedType: 'icu', level: 'limited' },
      { bedType: 'emergency', level: 'available' },
    ],
    onDuty: [
      { specialty: 'Cardiology', count: 2, names: namesShown ? ['Dr. Ayesha Khan', 'Dr. Omar Sheikh'] : null },
      { specialty: 'Emergency medicine', count: 1, names: namesShown ? ['Dr. Usman Farooq'] : null },
    ],
    namesShown,
  }
}

/** Our emergency department, as GET /api/emergencies/department/ returns it for staff at hospital 1. */
export function sampleDepartment(now: Date): DepartmentStatus {
  return { status: 'accepting', waitMinutes: 24, waitingCount: 7, updatedAt: now.toISOString() }
}
