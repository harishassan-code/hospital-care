export type ErStatus = 'accepting' | 'busy' | 'diverting'

export interface Doctor {
  id: string
  name: string
  department: string
  /** "HH:MM", 24-hour clock */
  start: string
  /** "HH:MM"; earlier than start means the shift runs past midnight */
  end: string
}

export interface PublicStatus {
  /** ISO timestamp of when the hospital last updated these numbers */
  updatedAt: string
  emergency: {
    status: ErStatus
    waitMinutes: number
    waitingCount: number
  }
  doctors: Doctor[]
}

export const ER_STATUS_LABEL: Record<ErStatus, string> = {
  accepting: 'Accepting patients',
  busy: 'Very busy',
  diverting: 'Not accepting ambulances',
}

const SAMPLE_DOCTORS: Doctor[] = [
  { id: 'd01', name: 'Dr. Kamran Shah', department: 'Emergency medicine', start: '08:00', end: '20:00' },
  { id: 'd02', name: 'Dr. Usman Farooq', department: 'Emergency medicine', start: '20:00', end: '08:00' },
  { id: 'd03', name: 'Dr. Nadia Rehman', department: 'Emergency medicine', start: '14:00', end: '02:00' },
  { id: 'd04', name: 'Dr. Bilal Ahmed', department: 'General medicine', start: '08:00', end: '16:00' },
  { id: 'd05', name: 'Dr. Zainab Hussain', department: 'General medicine', start: '16:00', end: '00:00' },
  { id: 'd06', name: 'Dr. Faisal Mirza', department: 'General medicine', start: '00:00', end: '08:00' },
  { id: 'd07', name: 'Dr. Ayesha Khan', department: 'Cardiology', start: '09:00', end: '13:00' },
  { id: 'd08', name: 'Dr. Omar Sheikh', department: 'Cardiology', start: '16:00', end: '22:00' },
  { id: 'd09', name: 'Dr. Sana Malik', department: 'Paediatrics', start: '10:00', end: '16:00' },
  { id: 'd10', name: 'Dr. Mariam Iqbal', department: 'Paediatrics', start: '18:00', end: '23:00' },
  { id: 'd11', name: 'Dr. Imran Qureshi', department: 'Orthopaedics', start: '09:00', end: '15:00' },
  { id: 'd12', name: 'Dr. Hamza Butt', department: 'Orthopaedics', start: '15:00', end: '21:00' },
  { id: 'd13', name: 'Dr. Fatima Zaidi', department: 'Gynaecology', start: '08:00', end: '14:00' },
  { id: 'd14', name: 'Dr. Rabia Anwar', department: 'Gynaecology', start: '20:00', end: '08:00' },
]

/**
 * Live public status for the landing page.
 * Returns sample data until the backend provides GET /api/public/status/ with this same shape;
 * then this becomes `return apiGet<PublicStatus>('/public/status/')`.
 */
export async function getPublicStatus(): Promise<PublicStatus> {
  return {
    updatedAt: new Date().toISOString(),
    emergency: { status: 'accepting', waitMinutes: 24, waitingCount: 7 },
    doctors: SAMPLE_DOCTORS,
  }
}
