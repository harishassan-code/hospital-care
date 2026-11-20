import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockStaffApi } from '../../test/mockApi'
import { renderStaff } from '../../test/renderStaff'

afterEach(() => {
  vi.restoreAllMocks()
  Reflect.deleteProperty(URL, 'createObjectURL')
  Reflect.deleteProperty(URL, 'revokeObjectURL')
})

const karachiToday = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Karachi' }).format(new Date())

/** Captures the file a download would save, and its name, instead of navigating. */
function captureDownloads() {
  const saved: { name: string; blob: Blob }[] = []
  URL.createObjectURL = vi.fn((blob: Blob) => {
    saved.push({ name: '', blob })
    return 'blob:report'
  })
  URL.revokeObjectURL = vi.fn()
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
    saved[saved.length - 1]!.name = this.download
  })
  return saved
}

const cells = (name: string) =>
  within(screen.getByRole('table', { name }))
    .getAllByRole('row')
    .slice(1)
    .map((row) => [...row.querySelectorAll('th, td')].map((cell) => cell.textContent))

const urls = (fetchMock: ReturnType<typeof mockStaffApi>['fetchMock']) => fetchMock.mock.calls.map(([input]) => String(input))

describe('ReportsPage (B18 Operational reports and export, #66, #67)', () => {
  it('opens on the last 30 days for the whole network and fills the dates in', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/reports')

    expect(await screen.findByRole('table', { name: 'Fulfilment time' })).toBeInTheDocument()
    expect(screen.getByLabelText('To')).toHaveValue(karachiToday())
    expect(screen.getByLabelText('From')).not.toHaveValue('')
    expect(screen.getByText(/\(30 days\) · All hospitals/)).toBeInTheDocument()
  })

  it('shows requests, fulfilment time in words, and blood wastage', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/reports')
    await screen.findByRole('table', { name: 'Fulfilment time' })

    expect(screen.getByText(/8 cases opened in the period · 11 resources allocated/)).toBeInTheDocument()
    expect(cells('Cases by severity')).toContainEqual(['Critical', '3'])
    // Statuses nobody is in are left out.
    expect(cells('Cases by current status').map(([status]) => status)).toEqual(['Open', 'Fulfilled', 'Escalated'])
    expect(cells('Requests by resource type')).toContainEqual(['Blood', '6', '14', '9'])
    expect(cells('Fulfilment time')[0]).toEqual(['All', '5', '42 min', '55 min', '1 h 58 min'])
    expect(cells('Fulfilment time')).toContainEqual(['Low', '0', '—', '—', '—'])
    expect(cells('Opened in the period and never fulfilled')).toEqual([['Escalated', '1']])
    expect(cells('Blood wastage')).toContainEqual(['CityCare General Hospital', 'O-', 'Red cells', '2', '1'])
  })

  it('Show report asks for the dates and hospital chosen', async () => {
    const { fetchMock } = mockStaffApi({ role: 'admin' })
    renderStaff('/staff/reports')
    await screen.findByRole('table', { name: 'Fulfilment time' })
    await screen.findByRole('option', { name: 'Seaview Hospital' })

    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2026-11-01' } })
    fireEvent.change(screen.getByLabelText('To'), { target: { value: '2026-11-10' } })
    await userEvent.selectOptions(screen.getByLabelText('Hospital'), 'Seaview Hospital')
    await userEvent.click(screen.getByRole('button', { name: 'Show report' }))

    expect(await screen.findByText(/1 Nov 2026 to 10 Nov 2026/)).toBeInTheDocument()
    expect(screen.getByText(/\(10 days\) · Seaview Hospital/)).toBeInTheDocument()
    const asked = urls(fetchMock).filter((url) => url.includes('/reports/?')).at(-1)!
    expect(asked).toContain('from=2026-11-01')
    expect(asked).toContain('to=2026-11-10')
    expect(asked).toMatch(/hospital=\d+/)
  })

  it('a range the server refuses shows its message', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/reports')
    await screen.findByRole('table', { name: 'Fulfilment time' })
    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2026-11-10' } })
    fireEvent.change(screen.getByLabelText('To'), { target: { value: '2026-11-01' } })
    await userEvent.click(screen.getByRole('button', { name: 'Show report' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('to must be the same day as from, or later.')
  })

  it.each([
    ['CSV', 'csv', 'CityCare operational reports'],
    ['PDF', 'pdf', '%PDF-'],
  ])('Export %s downloads the report on screen', async (label, format, start) => {
    const { fetchMock } = mockStaffApi({ role: 'admin' })
    renderStaff('/staff/reports')
    await screen.findByRole('table', { name: 'Fulfilment time' })
    const from = (screen.getByLabelText('From') as HTMLInputElement).value
    const saved = captureDownloads()

    await userEvent.click(screen.getByRole('button', { name: `Export ${label}` }))

    expect(await screen.findByText(new RegExp(`Downloaded reports-${from}-to-${karachiToday()}\\.${format}`))).toBeInTheDocument()
    expect(saved).toHaveLength(1)
    expect(saved[0]!.name).toBe(`reports-${from}-to-${karachiToday()}.${format}`)
    expect((await saved[0]!.blob.text()).startsWith(start)).toBe(true)
    const exportUrl = urls(fetchMock).find((url) => url.includes('/reports/export/'))!
    expect(exportUrl).toContain(`format=${format}`)
    expect(exportUrl).toContain(`from=${from}`)
  })

  it('a report that fails to load says so, without figures', async () => {
    mockStaffApi({ role: 'admin', reportsStatus: 500 })
    renderStaff('/staff/reports')
    expect(await screen.findByRole('alert')).toHaveTextContent('didn’t respond')
    expect(screen.queryByRole('table', { name: 'Fulfilment time' })).toBeNull()
    await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull())
  })
})
