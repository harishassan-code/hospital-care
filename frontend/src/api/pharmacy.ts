import { dateKey } from '../lib/time'

export interface Batch {
  number: string
  /** Local calendar date "YYYY-MM-DD". */
  expiresOn: string
  quantity: number
}

export interface Medicine {
  id: string
  /** Generic name. */
  name: string
  strength: string
  form: string
  category: string
  /** Counting unit, e.g. "tablets", "vials". */
  unit: string
  reorderLevel: number
  /** Average units used per day over the last 30 days. */
  dailyUse: number
  location: string
  /** On the ISMP list of high-alert medications: errors cause the most harm. */
  highAlert: boolean
  /** Controlled drug: kept in the CD cabinet, every movement double-signed. */
  controlled: boolean
  batches: Batch[]
}

/** [batch number, days until expiry, quantity] */
type BatchPlan = [string, number, number]
type MedicinePlan = Omit<Medicine, 'batches'> & { batches: BatchPlan[] }

const med = (
  id: string,
  name: string,
  strength: string,
  form: string,
  category: string,
  unit: string,
  stock: { reorderLevel: number; dailyUse: number; location: string },
  batches: BatchPlan[],
  flags: { highAlert?: boolean; controlled?: boolean } = {},
): MedicinePlan => ({
  id,
  name,
  strength,
  form,
  category,
  unit,
  ...stock,
  highAlert: flags.highAlert ?? false,
  controlled: flags.controlled ?? false,
  batches,
})

const FORMULARY: MedicinePlan[] = [
  med('pcm-tab', 'Paracetamol', '500 mg', 'Tablet', 'Analgesic', 'tablets',
    { reorderLevel: 2000, dailyUse: 450, location: 'Main store A1' },
    [['PCM-2405', 420, 6000], ['PCM-2311', 150, 2400]]),
  med('pcm-iv', 'Paracetamol', '1 g / 100 mL', 'Infusion', 'Analgesic', 'bags',
    { reorderLevel: 120, dailyUse: 35, location: 'Main store A2' },
    [['PIV-2402', 60, 180], ['PIV-2408', 300, 220]]),
  med('coamox', 'Amoxicillin–clavulanate', '625 mg', 'Tablet', 'Antibiotic', 'tablets',
    { reorderLevel: 600, dailyUse: 140, location: 'Main store B1' },
    [['AMC-2404', 280, 1900]]),
  med('ceftriaxone', 'Ceftriaxone', '1 g', 'Injection', 'Antibiotic', 'vials',
    { reorderLevel: 300, dailyUse: 85, location: 'Main store B2' },
    [['CTX-2406', 510, 260]]),
  med('metronidazole', 'Metronidazole', '500 mg / 100 mL', 'Infusion', 'Antibiotic', 'bags',
    { reorderLevel: 150, dailyUse: 40, location: 'Main store B3' },
    [['MTZ-2403', 200, 420]]),
  med('insulin-glargine', 'Insulin glargine', '100 units/mL', 'Pen', 'Antidiabetic', 'pens',
    { reorderLevel: 60, dailyUse: 14, location: 'Pharmacy fridge 1 (2–8 °C)' },
    [['GLA-2407', 190, 21]], { highAlert: true }),
  med('insulin-regular', 'Insulin regular (soluble)', '100 units/mL', 'Vial', 'Antidiabetic', 'vials',
    { reorderLevel: 40, dailyUse: 9, location: 'Pharmacy fridge 1 (2–8 °C)' },
    [['INS-2405', 150, 95]], { highAlert: true }),
  med('heparin', 'Heparin', '5,000 units/mL', 'Injection', 'Anticoagulant', 'vials',
    { reorderLevel: 150, dailyUse: 30, location: 'High-alert cabinet' },
    [['HEP-2402', 330, 410]], { highAlert: true }),
  med('enoxaparin', 'Enoxaparin', '40 mg / 0.4 mL', 'Prefilled syringe', 'Anticoagulant', 'syringes',
    { reorderLevel: 200, dailyUse: 48, location: 'High-alert cabinet' },
    [['ENX-2406', 400, 640]], { highAlert: true }),
  med('kcl', 'Potassium chloride', '15% (2 mmol/mL), 10 mL', 'Concentrate', 'Electrolyte', 'ampoules',
    { reorderLevel: 80, dailyUse: 12, location: 'High-alert cabinet (pharmacy only)' },
    [['KCL-2309', 25, 40], ['KCL-2404', 380, 160]], { highAlert: true }),
  med('magnesium', 'Magnesium sulfate', '50%', 'Injection', 'Electrolyte', 'ampoules',
    { reorderLevel: 60, dailyUse: 10, location: 'High-alert cabinet' },
    [['MGS-2405', 260, 140]], { highAlert: true }),
  med('morphine', 'Morphine', '10 mg/mL', 'Injection', 'Opioid analgesic', 'ampoules',
    { reorderLevel: 100, dailyUse: 22, location: 'CD cabinet' },
    [['MOR-2403', 230, 84]], { highAlert: true, controlled: true }),
  med('pethidine', 'Pethidine', '50 mg/mL', 'Injection', 'Opioid analgesic', 'ampoules',
    { reorderLevel: 40, dailyUse: 6, location: 'CD cabinet' },
    [['PTH-2401', 140, 72]], { highAlert: true, controlled: true }),
  med('midazolam', 'Midazolam', '5 mg/mL', 'Injection', 'Sedative', 'ampoules',
    { reorderLevel: 60, dailyUse: 9, location: 'CD cabinet' },
    [['MDZ-2404', 310, 150]], { highAlert: true, controlled: true }),
  med('oxytocin', 'Oxytocin', '10 IU/mL', 'Injection', 'Uterotonic', 'ampoules',
    { reorderLevel: 100, dailyUse: 25, location: 'Pharmacy fridge 2 (2–8 °C)' },
    [['OXY-2406', 40, 130], ['OXY-2408', 210, 200]], { highAlert: true }),
  med('adrenaline', 'Adrenaline (epinephrine)', '1 mg/mL', 'Injection', 'Emergency', 'ampoules',
    { reorderLevel: 80, dailyUse: 6, location: 'Main store E1 + crash carts' },
    [['ADR-2405', 330, 190]], { highAlert: true }),
  med('omeprazole', 'Omeprazole', '40 mg', 'Injection', 'Gastrointestinal', 'vials',
    { reorderLevel: 120, dailyUse: 30, location: 'Main store C1' },
    [['OMP-2404', 450, 380]]),
  med('ondansetron', 'Ondansetron', '4 mg / 2 mL', 'Injection', 'Antiemetic', 'ampoules',
    { reorderLevel: 150, dailyUse: 35, location: 'Main store C2' },
    [['OND-2402', 75, 120], ['OND-2407', 400, 300]]),
  med('salbutamol', 'Salbutamol', '2.5 mg / 2.5 mL', 'Nebule', 'Respiratory', 'nebules',
    { reorderLevel: 300, dailyUse: 70, location: 'Main store D1' },
    [['SAL-2405', 280, 900]]),
  med('saline', 'Sodium chloride', '0.9%, 1 L', 'Infusion', 'Fluids', 'bags',
    { reorderLevel: 400, dailyUse: 110, location: 'Fluids store' },
    [['NS-2406', 600, 1300]]),
  med('ringer', "Ringer's lactate", '1 L', 'Infusion', 'Fluids', 'bags',
    { reorderLevel: 300, dailyUse: 70, location: 'Fluids store' },
    [['RL-2405', 560, 640]]),
  med('txa', 'Tranexamic acid', '500 mg / 5 mL', 'Injection', 'Haemostatic', 'ampoules',
    { reorderLevel: 100, dailyUse: 18, location: 'Main store E2' },
    [['TXA-2403', 85, 95]]),
  med('metformin', 'Metformin', '500 mg', 'Tablet', 'Antidiabetic', 'tablets',
    { reorderLevel: 1500, dailyUse: 320, location: 'Main store A3' },
    [['MET-2404', 380, 4100]]),
]

/** Sample formulary: fixed stock levels, expiry dates relative to `now`. */
export function sampleMedicines(now: Date): Medicine[] {
  return FORMULARY.map(({ batches, ...medicine }) => ({
    ...medicine,
    batches: batches.map(([number, days, quantity]) => {
      const expiry = new Date(now)
      expiry.setDate(expiry.getDate() + days)
      return { number, expiresOn: dateKey(expiry), quantity }
    }),
  }))
}

/** Pharmacy stock. Returns sample data until the backend provides GET /api/pharmacy/stock/. */
export async function getMedicines(now = new Date()): Promise<Medicine[]> {
  return sampleMedicines(now)
}
