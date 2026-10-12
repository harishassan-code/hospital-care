import type { Capability, HospitalDetail } from '../../api/hospitals'
import type { UserSummary } from '../../api/users'

export const sampleCapabilities: Capability[] = [
  { code: 'trauma', name: 'Trauma centre' },
  { code: 'icu', name: 'Intensive care unit' },
  { code: 'nicu', name: 'Neonatal ICU' },
  { code: 'bloodBank', name: 'Blood bank' },
]

/** Fresh copies every call, so a test that edits them can't leak into the next. */
export function sampleHospitals(): HospitalDetail[] {
  return [
    {
      id: 1,
      name: 'CityCare General Hospital',
      type: 'hospital',
      address: 'Shahrah-e-Faisal, Karachi',
      latitude: 24.8607,
      longitude: 67.0011,
      phone: '+92 21 111 000 111',
      isActive: true,
      capabilities: ['trauma', 'icu', 'bloodBank'],
      departments: [
        { id: 11, name: 'Emergency medicine' },
        { id: 12, name: 'Surgery' },
      ],
      wards: [
        { id: 21, code: 'icu', name: 'ICU', kind: 'Intensive care', departmentId: 11, bedCount: 10 },
        { id: 22, code: 'h1-step-down', name: 'Step-down', kind: 'High dependency', departmentId: null, bedCount: 0 },
      ],
      locations: [{ id: 31, name: 'Blood fridge 1' }],
    },
    {
      id: 2,
      name: 'Seaview Hospital',
      type: 'hospital',
      address: 'Clifton Block 5, Karachi',
      latitude: 24.8138,
      longitude: 67.0299,
      phone: '',
      isActive: true,
      capabilities: ['nicu'],
      departments: [],
      wards: [],
      locations: [],
    },
    {
      id: 3,
      name: 'Old Town Blood Centre',
      type: 'bloodBank',
      address: 'Saddar, Karachi',
      latitude: 24.8556,
      longitude: 67.0236,
      phone: '',
      isActive: false,
      capabilities: [],
      departments: [],
      wards: [],
      locations: [],
    },
  ]
}

export function sampleUsers(): UserSummary[] {
  const hospital = { id: 1, name: 'CityCare General Hospital' }
  return [
    { id: 1, email: 'admin@demo.test', fullName: 'Sadia Admin', role: 'admin', hospital, isActive: true, roleLocked: true },
    { id: 2, email: 'nurse@demo.test', fullName: 'Hina Javed', role: 'nurse', hospital, isActive: true, roleLocked: false },
    { id: 3, email: 'doctor@demo.test', fullName: 'Dr. Ayesha Khan', role: 'doctor', hospital, isActive: true, roleLocked: false },
    { id: 4, email: 'root@demo.test', fullName: 'Root Admin', role: 'admin', hospital: null, isActive: true, roleLocked: true },
    { id: 5, email: 'patient@demo.test', fullName: 'Sara Ahmed', role: 'patient', hospital: null, isActive: false, roleLocked: false },
  ]
}
