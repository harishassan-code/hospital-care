/**
 * Per-hospital branding and contact details. This is the file a hospital edits when it installs
 * Hospital Care. The values below are a fictional placeholder hospital.
 */
export const hospital = {
  name: 'Northgate General Hospital',
  shortName: 'Northgate General',
  monogram: 'NG',
  emergencyNumber: '1122',
  mainPhone: '(021) 3400 0000',
  address: 'Plot 14, Shahrah-e-Faisal, Karachi',
  visitingHours: '11:00–13:00 and 17:00–20:00 daily',
  /** Overhead sign and header colour. Keep it dark: white text sits on it. */
  brandColor: '#0F2A26',
  /** Staff shifts; together they must cover all 24 hours. */
  shifts: [
    { name: 'Morning', start: '08:00', end: '14:00' },
    { name: 'Evening', start: '14:00', end: '20:00' },
    { name: 'Night', start: '20:00', end: '08:00' },
  ],
} as const
