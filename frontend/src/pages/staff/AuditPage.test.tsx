import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { AuditEntry } from '../../api/audit'
import { mockStaffApi } from '../../test/mockApi'
import { renderStaff } from '../../test/renderStaff'

afterEach(() => {
  vi.restoreAllMocks()
  Reflect.deleteProperty(URL, 'createObjectURL')
  Reflect.deleteProperty(URL, 'revokeObjectURL')
})

const table = () => screen.getByRole('table', { name: 'Audit entries' })

/** The action column, top to bottom. */
const actions = () =>
  within(table())
    .getAllByRole('row')
    .slice(1)
    .map((row) => within(row).getAllByRole('cell')[2]!.textContent)

/** `count` entries, one a minute apart from 06:00 UTC on 18 November 2026, newest first. */
function manyEntries(count: number): AuditEntry[] {
  const start = Date.UTC(2026, 10, 18, 6)
  return Array.from({ length: count }, (_, i) => ({
    id: i + 1,
    at: new Date(start - i * 60_000).toISOString(),
    actorEmail: 'admin@demo.test',
    action: 'bed.reserved',
    targetType: 'beds.bed',
    targetId: String(i + 1),
    targetRepr: `Bed ${i + 1}`,
    reason: '',
    before: null,
    after: null,
  }))
}

const karachiToday = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Karachi' }).format(new Date())

/** Captures the file a download would save, and the link's name, instead of navigating. */
function captureDownloads() {
  const saved: { name: string; blob: Blob }[] = []
  const createObjectURL = vi.fn((blob: Blob) => {
    saved.push({ name: '', blob })
    return 'blob:audit'
  })
  URL.createObjectURL = createObjectURL
  URL.revokeObjectURL = vi.fn()
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
    saved[saved.length - 1]!.name = this.download
  })
  return saved
}

describe('AuditPage (B10 Audit search and export, #56)', () => {
  it('lists every entry newest first, with who, what, object and reason', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/audit')
    await screen.findByRole('table', { name: 'Audit entries' })
    expect(actions()).toEqual(['bed.status_changed', 'hospital.updated', 'user.role_changed', 'blood.expired'])
    const system = within(table()).getByText('System').closest('tr') as HTMLElement
    expect(within(system).getByText('O- red cells DN-0012')).toBeInTheDocument()
    const role = within(table()).getByText('Moved to the medical team').closest('tr') as HTMLElement
    expect(within(role).getByText('accounts.user · 4')).toBeInTheDocument()
  })

  it('searches by action and shows only the matches', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/audit')
    await screen.findByRole('table', { name: 'Audit entries' })
    await userEvent.type(screen.getByLabelText('Action'), 'bed.')
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => expect(actions()).toEqual(['bed.status_changed']))
  })

  it('combines who and text, and says when nothing matches', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/audit')
    await screen.findByRole('table', { name: 'Audit entries' })
    await userEvent.type(screen.getByLabelText('Who (email)'), 'NURSE@demo.test')
    await userEvent.type(screen.getByLabelText('Search text'), 'icu')
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => expect(actions()).toEqual(['bed.status_changed']))

    await userEvent.type(screen.getByLabelText('Search text'), 'nothing like this')
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))
    expect(await screen.findByText('No audit entries match these filters.')).toBeInTheDocument()
  })

  it('filters by whole days from and to', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/audit')
    await screen.findByRole('table', { name: 'Audit entries' })
    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2000-01-01' } })
    fireEvent.change(screen.getByLabelText('To'), { target: { value: '2000-01-01' } })
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))
    expect(await screen.findByText('No audit entries match these filters.')).toBeInTheDocument()

    // The sample entries were all written before now, so today's date includes every one of them.
    fireEvent.change(screen.getByLabelText('To'), { target: { value: karachiToday() } })
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => expect(actions()).toHaveLength(4))
  })

  it('pages through the results, with Previous and Next', async () => {
    mockStaffApi({ role: 'admin', audit: manyEntries(120) })
    renderStaff('/staff/audit')
    expect(await screen.findByText('1–50 of 120')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()

    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('51–100 of 120')).toBeInTheDocument()
    expect(within(table()).getAllByRole('row')).toHaveLength(51)

    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('101–120 of 120')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()

    await userEvent.click(screen.getByRole('button', { name: 'Previous' }))
    expect(await screen.findByText('51–100 of 120')).toBeInTheDocument()
  })

  it('opens an entry’s values as JSON text', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/audit')
    await screen.findByRole('table', { name: 'Audit entries' })
    await userEvent.click(screen.getByRole('button', { name: 'Show values of entry 2' }))
    expect(screen.getByText(/"status": "occupied"/)).toBeInTheDocument()
    expect(screen.getByText(/"status": "reserved"/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Hide values of entry 2' }))
    expect(screen.queryByText(/"status": "occupied"/)).toBeNull()
  })

  it('Export CSV downloads the file for the filters on screen', async () => {
    const { fetchMock } = mockStaffApi({ role: 'admin' })
    renderStaff('/staff/audit')
    await screen.findByRole('table', { name: 'Audit entries' })
    await userEvent.type(screen.getByLabelText('Action'), 'bed.')
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => expect(actions()).toHaveLength(1))

    const saved = captureDownloads()
    await userEvent.click(screen.getByRole('button', { name: 'Export CSV' }))

    expect(await screen.findByText(/Downloaded audit-/)).toBeInTheDocument()
    expect(saved).toHaveLength(1)
    expect(saved[0]!.name).toBe(`audit-${karachiToday()}.csv`)
    const text = await saved[0]!.blob.text()
    expect(text.split('\r\n')[0]).toBe('at,actorEmail,action,targetType,targetId,targetRepr,reason,before,after')
    expect(text).toContain('bed.status_changed')
    expect(text).not.toContain('hospital.updated')
    const exportUrl = String(fetchMock.mock.calls.map(([input]) => input).find((input) => String(input).includes('/export/')))
    expect(exportUrl).toContain('action=bed.')
  })

  it('an export over the cap shows the refusal and downloads nothing', async () => {
    mockStaffApi({ role: 'admin', audit: manyEntries(10_001) })
    renderStaff('/staff/audit')
    await screen.findByText('1–50 of 10,001')
    const saved = captureDownloads()
    await userEvent.click(screen.getByRole('button', { name: 'Export CSV' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('More than 10,000 entries match')
    expect(saved).toHaveLength(0)
  })

  it('a search the server refuses shows its message', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/audit')
    await screen.findByRole('table', { name: 'Audit entries' })
    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2026-11-18' } })
    fireEvent.change(screen.getByLabelText('To'), { target: { value: '2026-11-17' } })
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('to must be the same day as from, or later.')
  })

  it('Clear filters brings back every entry', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/audit')
    await screen.findByRole('table', { name: 'Audit entries' })
    await userEvent.type(screen.getByLabelText('Action'), 'bed.')
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => expect(actions()).toHaveLength(1))
    await userEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
    await waitFor(() => expect(actions()).toHaveLength(4))
    expect(screen.getByLabelText('Action')).toHaveValue('')
  })

  it('says so when the trail can’t be loaded', async () => {
    mockStaffApi({ role: 'admin', networkDown: true })
    renderStaff('/staff/audit')
    expect(await screen.findByRole('alert')).toHaveTextContent('The hospital’s system didn’t respond')
  })

  it('a nurse who opens the page by URL is refused', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff('/staff/audit')
    expect(await screen.findByRole('heading', { name: 'You don’t have access to this page' })).toBeInTheDocument()
  })
})
