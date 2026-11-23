/**
 * The site's name, branding and front-door contact details. CityCare is a network that hospitals join, so the brand is
 * the network's, not any one hospital's; each hospital's own name comes from the API. A deployment for another network
 * edits this file. The contact details below are the fictional demo front door that `seed_demo` creates.
 */
export const hospital = {
  name: 'CityCare',
  shortName: 'CityCare',
  emergencyNumber: '1122',
  mainPhone: '(021) 3400 0000',
  address: 'Plot 14, Shahrah-e-Faisal, Karachi',
  visitingHours: '11:00–13:00 and 17:00–20:00 daily',
  /** Wards and bed types at or above this occupancy (%) are flagged on the bed board and overview. */
  occupancyAlertPercent: 90,
  /** Brand colour: the logo, primary buttons and the active line. White text sits on it, so keep it dark enough
   * for 4.5:1 (the default teal is 5.96:1). */
  brandColor: '#0B6E79',
  /** Staff shifts; together they must cover all 24 hours. */
  shifts: [
    { name: 'Morning', start: '08:00', end: '14:00' },
    { name: 'Evening', start: '14:00', end: '20:00' },
    { name: 'Night', start: '20:00', end: '08:00' },
  ],
} as const
