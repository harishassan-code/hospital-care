import { describe, expect, it } from 'vitest'
import { samplePublicHospitals } from '../../test/fixtures/publicNetwork'
import { areaOf, distanceKm, formatDistance, sortHospitals } from './network'

const hospitals = samplePublicHospitals(new Date())

describe('the hospital directory order (B19)', () => {
  it('puts the shortest open wait first, then diverting, then unreported', () => {
    expect(sortHospitals(hospitals, null).map((h) => h.id)).toEqual([1, 2, 3, 4])
  })

  it('puts the nearest first when there is a location', () => {
    const northNazimabad = { latitude: 24.94, longitude: 67.03 }
    expect(sortHospitals(hospitals, northNazimabad)[0].name).toBe('Northside Children’s Hospital')
  })

  it('does not change the list it was given', () => {
    const copy = [...hospitals]
    sortHospitals(hospitals, { latitude: 0, longitude: 0 })
    expect(hospitals).toEqual(copy)
  })
})

describe('distances', () => {
  it('measures a straight line in km', () => {
    // Shahrah-e-Faisal to Clifton is about 6 km.
    expect(distanceKm({ latitude: 24.8607, longitude: 67.0011 }, { latitude: 24.8138, longitude: 67.0299 })).toBeCloseTo(5.9, 0)
  })

  it('reads well', () => {
    expect(formatDistance(2.345)).toBe('2.3 km')
    expect(formatDistance(14.6)).toBe('15 km')
  })
})

it('takes the area from an address', () => {
  expect(areaOf('Clifton Block 5, Karachi')).toBe('Clifton Block 5')
  expect(areaOf('Plot 3, Gulshan-e-Iqbal, Karachi')).toBe('Gulshan-e-Iqbal')
  expect(areaOf('Lahore')).toBe('Lahore')
})
