import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { SAMPLE_NOON, sampleSpecialists } from '../../test/fixtures/specialists'
import { mockStaffApi } from '../../test/mockApi'
import { renderStaff } from '../../test/renderStaff'

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(SAMPLE_NOON))
})
afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

const table = () => screen.getByRole('table', { name: 'Specialists' })
const names = () => within(table()).getAllByRole('rowheader').map((cell) => cell.textContent)
const rowOf = (name: string) => screen.getByRole('rowheader', { name }).closest('tr') as HTMLElement

describe('SpecialistsPage (stories #61 and #62)', () => {
  it('lists every specialist across the hospitals, with status and who is on call', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/specialists')
    await screen.findByRole('table', { name: 'Specialists' })
    expect(names()).toEqual(['Dr. Ayesha Khan', 'Dr. Usman Farooq', 'Dr. Omar Sheikh', 'Dr. Sana Malik'])
    expect(within(rowOf('Dr. Ayesha Khan')).getByText('On call until 20:00')).toBeInTheDocument()
    expect(within(rowOf('Dr. Usman Farooq')).getByText('Not on call')).toBeInTheDocument()
    expect(within(rowOf('Dr. Omar Sheikh')).getByText('Seaview Hospital')).toBeInTheDocument()
    expect(within(rowOf('Dr. Sana Malik')).getByText('Deactivated')).toBeInTheDocument()
    expect(within(rowOf('Dr. Sana Malik')).getByText('Not on call')).toBeInTheDocument()
  })

  it('links each name to the specialist’s page', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/specialists')
    await screen.findByRole('table', { name: 'Specialists' })
    expect(screen.getByRole('link', { name: 'Dr. Omar Sheikh' })).toHaveAttribute('href', '/staff/specialists/3')
  })

  it('"Available now" asks the server for those on call, and turning it off lists everyone again', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/specialists')
    await screen.findByRole('table', { name: 'Specialists' })
    await userEvent.click(screen.getByRole('checkbox', { name: 'Available now' }))
    await waitFor(() => expect(names()).toEqual(['Dr. Ayesha Khan', 'Dr. Omar Sheikh']))
    expect(fetchMock).toHaveBeenCalledWith(expect.stringMatching(/\/specialists\/\?availableNow=true$/), expect.anything())
    await userEvent.click(screen.getByRole('checkbox', { name: 'Available now' }))
    await waitFor(() => expect(names()).toHaveLength(4))
  })

  it('filters by hospital and by specialty in the browser, without asking the server again', async () => {
    const { fetchMock } = mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/specialists')
    await screen.findByRole('table', { name: 'Specialists' })
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Hospital' }), 'Seaview Hospital')
    expect(names()).toEqual(['Dr. Omar Sheikh', 'Dr. Sana Malik'])
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Specialty' }), 'Cardiology')
    expect(names()).toEqual(['Dr. Omar Sheikh'])
    const listCalls = fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/specialists/'))
    expect(listCalls).toHaveLength(1)
  })

  it('says when the filters hide everyone', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/specialists')
    await screen.findByRole('table', { name: 'Specialists' })
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Hospital' }), 'Old Town Blood Centre')
    expect(screen.getByText('No specialists match. Clear the filters or turn off Available now.')).toBeInTheDocument()
  })

  it('says so when no specialist is listed yet', async () => {
    mockStaffApi({ role: 'doctor', specialists: [] })
    renderStaff('/staff/specialists')
    expect(await screen.findByText('No specialists listed yet.')).toBeInTheDocument()
  })

  it('says nobody is on call when the "Available now" filter finds no one', async () => {
    mockStaffApi({ role: 'doctor', specialists: sampleSpecialists().map((s) => ({ ...s, windows: [] })) })
    renderStaff('/staff/specialists')
    await screen.findByRole('table', { name: 'Specialists' })
    await userEvent.click(screen.getByRole('checkbox', { name: 'Available now' }))
    expect(await screen.findByText('Nobody is on call right now.')).toBeInTheDocument()
  })

  it('offers adding a specialist to nurses and admins, but not to doctors', async () => {
    mockStaffApi({ role: 'doctor' })
    const { unmount } = renderStaff('/staff/specialists')
    await screen.findByRole('table', { name: 'Specialists' })
    expect(screen.queryByRole('link', { name: 'Add specialist' })).not.toBeInTheDocument()
    unmount()
    vi.restoreAllMocks()
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/specialists')
    expect(await screen.findByRole('link', { name: 'Add specialist' })).toHaveAttribute('href', '/staff/specialists/new')
  })

  it('shows the loading state until the list arrives', async () => {
    const { fetchMock } = mockStaffApi({ role: 'doctor' })
    const served = fetchMock.getMockImplementation()!
    fetchMock.mockImplementation((input, init) =>
      String(input).includes('/specialists/') ? new Promise<Response>(() => {}) : served(input, init),
    )
    renderStaff('/staff/specialists')
    expect(await screen.findByText('Loading…')).toBeInTheDocument()
    expect(screen.queryByRole('table', { name: 'Specialists' })).not.toBeInTheDocument()
  })

  it('says the hospital did not respond when the list fails to load', async () => {
    mockStaffApi({ role: 'nurse', networkDown: true })
    renderStaff('/staff/specialists')
    expect(await screen.findByText(/didn’t respond/)).toBeInTheDocument()
  })
})
