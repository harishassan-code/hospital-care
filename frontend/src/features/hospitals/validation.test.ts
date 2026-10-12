import { describe, expect, it } from 'vitest'
import { EMPTY_HOSPITAL, toHospitalInput, validateHospital } from './validation'

const VALID = {
  ...EMPTY_HOSPITAL,
  name: ' CityCare General ',
  address: 'Shahrah-e-Faisal, Karachi',
  latitude: '24.8607',
  longitude: '67.0011',
}

describe('validateHospital', () => {
  it('accepts a complete hospital', () => {
    expect(validateHospital(VALID)).toEqual({})
  })

  it('asks for every required field in plain words', () => {
    expect(validateHospital(EMPTY_HOSPITAL)).toEqual({
      name: 'Enter the hospital’s name',
      address: 'Enter the street address',
      latitude: 'Enter the latitude',
      longitude: 'Enter the longitude',
    })
  })

  it.each([
    ['latitude', '91', 'The latitude must be between -90 and 90'],
    ['latitude', '-90.5', 'The latitude must be between -90 and 90'],
    ['longitude', '180.1', 'The longitude must be between -180 and 180'],
    ['latitude', 'north', 'Enter the latitude as a decimal number with up to 6 decimal places, e.g. 24.8607'],
    ['longitude', '67.0000001', 'Enter the longitude as a decimal number with up to 6 decimal places, e.g. 24.8607'],
  ])('refuses %s %s', (field, value, message) => {
    expect(validateHospital({ ...VALID, [field]: value })).toEqual({ [field]: message })
  })

  it('accepts the coordinate limits and negative values', () => {
    expect(validateHospital({ ...VALID, latitude: '-90', longitude: '180' })).toEqual({})
  })

  it('checks the optional phone only when given, and limits lengths', () => {
    expect(validateHospital({ ...VALID, phone: 'call us' }).phone).toBe('Enter a phone number using digits, spaces, + or -')
    expect(validateHospital({ ...VALID, phone: '+92 21 111 222 333' })).toEqual({})
    expect(validateHospital({ ...VALID, name: 'x'.repeat(151) }).name).toBe('Use at most 150 characters')
  })
})

it('trims text and turns coordinates into numbers for the API', () => {
  expect(toHospitalInput(VALID)).toMatchObject({ name: 'CityCare General', latitude: 24.8607, longitude: 67.0011 })
})
