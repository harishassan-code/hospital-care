import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { fail, mockApi, mockStaffApi, userFor } from '../../test/mockApi'
import { renderStaff } from '../../test/renderStaff'
import { sampleCases, sampleNewNeedsCase, sampleThreeNeedSources } from '../../test/fixtures/emergencies'
import { allocateReservation, type StatusChange } from '../../api/emergencies'

afterEach(() => vi.restoreAllMocks())

const CASE = '/staff/emergencies/EC-2026-0002'
const details = async () => screen.findByRole('region', { name: 'EC-2026-0002' })
const moves = async () => screen.findByRole('region', { name: 'Update status' })
const history = async () => screen.findByRole('region', { name: 'Status history' })
const entries = async () => within(await history()).getAllByRole('listitem')
const entryHeadings = async () => (await entries()).map((li) => li.querySelector('strong')?.textContent)

describe('EmergencyCasePage (story #34 status tracking)', () => {
  it('shows the case, its severity, status, patient reference and what it needs', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff(CASE)

    expect(await screen.findByRole('heading', { name: 'EC-2026-0002' })).toBeInTheDocument()
    const panel = await details()
    expect(within(panel).getByText('Critical')).toBeInTheDocument()
    expect(within(panel).getByText('Open')).toBeInTheDocument()
    expect(within(panel).getByText('Bay 4')).toBeInTheDocument()
    const needs = within(within(panel).getByRole('list')).getAllByRole('listitem')
    expect(needs.map((li) => li.querySelector('span')?.textContent)).toEqual(['4 × O− red cells', '1 × ICU bed'])
  })

  it('shows, for each need, what this hospital has and what is short, as text', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff(CASE)

    const [blood, bed] = within(within(await details()).getByRole('list')).getAllByRole('listitem')
    expect(within(blood!).getByText('Available here: 1 · Short: 3')).toBeInTheDocument()
    expect(within(bed!).getByText('Available here: 0 · Short: 1')).toBeInTheDocument()
    expect(within(await details()).getByText('4 units/beds needed from other hospitals')).toBeInTheDocument()
  })

  it('says everything is available, and covered locally, when no need is short', async () => {
    mockStaffApi({ role: 'doctor', cases: [sampleCases(new Date())[1]!] })
    renderStaff('/staff/emergencies/EC-2026-0001')

    const panel = await screen.findByRole('region', { name: 'EC-2026-0001' })
    expect(within(panel).getByText('Available here: 2 · Covered locally')).toBeInTheDocument()
    expect(within(panel).getByText('Everything is available here')).toBeInTheDocument()
  })

  it('offers only the moves the case’s status allows', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff(CASE)

    const region = await moves()
    expect(within(region).getAllByRole('button').map((b) => b.textContent)).toEqual(['Start matching', 'Escalate', 'Cancel case'])
  })

  it('moves the case with a note, then shows the new status and the timeline entry', async () => {
    const { fetchMock } = mockStaffApi({ role: 'nurse' })
    renderStaff(CASE)

    const region = await moves()
    await userEvent.type(within(region).getByLabelText(/Note/), 'Blood bank called back')
    await userEvent.click(within(region).getByRole('button', { name: 'Start matching' }))

    expect(await within(region).findByRole('button', { name: 'Mark fulfilled' })).toBeInTheDocument()
    expect(within(region).getByText('EC-2026-0002 is now matching.')).toBeInTheDocument()
    expect(within(await details()).getByText('Matching')).toBeInTheDocument()
    expect(within(region).getByLabelText(/Note/)).toHaveValue('')
    expect(await entryHeadings()).toEqual(['Case opened', 'Open → Matching'])
    expect(within(await history()).getByText('Blood bank called back')).toBeInTheDocument()

    const post = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')!
    expect(JSON.parse(String(post[1]!.body))).toEqual({ action: 'startMatching', note: 'Blood bank called back' })
  })

  it('shows the timeline oldest first, in the order the server keeps it', async () => {
    mockStaffApi({ role: 'doctor' })
    const { unmount } = renderStaff(CASE)

    const region = await moves()
    await userEvent.click(within(region).getByRole('button', { name: 'Start matching' }))
    await within(region).findByRole('button', { name: 'Mark partially fulfilled' })
    await userEvent.type(within(region).getByLabelText(/Note/), 'Two of four')
    await userEvent.click(within(region).getByRole('button', { name: 'Mark partially fulfilled' }))
    await within(region).findByRole('button', { name: 'Close case' })

    unmount()
    renderStaff(CASE)
    expect(await entryHeadings()).toEqual(['Case opened', 'Open → Matching', 'Matching → Partially fulfilled'])
    expect(within(await history()).getByText('Two of four')).toBeInTheDocument()
  })

  it('shows the server’s reason when it refuses a move', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff(CASE)

    const region = await moves()
    // Someone else moved the case since this page loaded, so the server now refuses the move the page offers.
    vi.restoreAllMocks()
    mockApi({
      'GET /auth/me/': { body: userFor('doctor') },
      'POST /emergencies/:reference/actions/': fail(409, { detail: "Can't startMatching a case that is matching." }),
    })
    await userEvent.click(within(region).getByRole('button', { name: 'Start matching' }))

    expect(await within(region).findByRole('alert')).toHaveTextContent("Can't startMatching a case that is matching.")
    expect(within(await details()).getByText('Open')).toBeInTheDocument()
    expect(await entryHeadings()).toEqual(['Case opened'])
  })

  it('lets view-only roles read the case and its timeline, but not move it', async () => {
    mockStaffApi({ role: 'bloodBank' })
    renderStaff(CASE)

    expect(await screen.findByRole('heading', { name: 'EC-2026-0002' })).toBeInTheDocument()
    expect(await entryHeadings()).toEqual(['Case opened'])
    expect(screen.queryByRole('region', { name: 'Update status' })).toBeNull()
    expect(screen.queryByRole('button', { name: /Start matching|Escalate|Cancel case/ })).toBeNull()
  })

  it('says so when a case has no moves left', async () => {
    const closed = { ...sampleCases(new Date())[0], status: 'closed' as const }
    mockStaffApi({ role: 'doctor', cases: [closed] })
    renderStaff(CASE)

    expect(await screen.findByText('No moves from closed.')).toBeInTheDocument()
    expect((await moves()).querySelectorAll('button')).toHaveLength(0)
  })

  it('says when there is no such case, with a way back to the list', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/emergencies/EC-2026-9999')
    expect(await screen.findByText('No emergency case with that id.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '← All emergency cases' })).toHaveAttribute('href', '/staff/emergencies')
  })
})

describe('EmergencyCasePage (story #35 escalation and closure)', () => {
  const fulfilled = () => ({ ...sampleCases(new Date())[0]!, status: 'fulfilled' as const })
  const opening: StatusChange = {
    fromStatus: '',
    toStatus: 'open',
    action: 'create',
    note: '',
    actor: 'Dr. Ayesha Khan',
    at: new Date().toISOString(),
  }
  const posted = (fetchMock: ReturnType<typeof mockStaffApi>['fetchMock']) => fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')

  it('asks for an outcome note when closing, and sends nothing without one', async () => {
    const { fetchMock } = mockStaffApi({ role: 'doctor', cases: [fulfilled()] })
    renderStaff(CASE)

    const region = await moves()
    await userEvent.click(within(region).getByRole('button', { name: 'Close case' }))
    const outcome = within(region).getByLabelText(/Outcome note/)
    expect(outcome).toBeRequired()

    await userEvent.type(outcome, '   ')
    await userEvent.click(within(region).getByRole('button', { name: 'Close case' }))

    expect(within(region).getByText('Add an outcome note to close the case.')).toBeInTheDocument()
    expect(outcome).toHaveAttribute('aria-invalid', 'true')
    expect(within(region).getByRole('button', { name: 'Close case' })).toBeInTheDocument()
    expect(posted(fetchMock)).toHaveLength(0)
  })

  it('closes with an outcome note, then shows the outcome and no moves', async () => {
    const { fetchMock } = mockStaffApi({ role: 'doctor', cases: [fulfilled()] })
    renderStaff(CASE)

    const region = await moves()
    await userEvent.click(within(region).getByRole('button', { name: 'Close case' }))
    await userEvent.type(within(region).getByLabelText(/Outcome note/), 'Two units to ward 3; stable')
    await userEvent.click(within(region).getByRole('button', { name: 'Close case' }))

    const outcome = await screen.findByRole('region', { name: 'Outcome' })
    expect(within(outcome).getByText('Two units to ward 3; stable')).toBeInTheDocument()
    expect(within(await details()).getByText('Closed')).toBeInTheDocument()
    expect(await within(region).findByText('No moves from closed.')).toBeInTheDocument()
    expect(await entryHeadings()).toEqual(['Case opened', 'Fulfilled → Closed'])
    expect(JSON.parse(String(posted(fetchMock)[0]![1]!.body))).toEqual({ action: 'close', note: 'Two units to ward 3; stable' })
  })

  it('shows the server’s refusal of a close without a note on the outcome field', async () => {
    mockStaffApi({ role: 'doctor', cases: [fulfilled()] })
    renderStaff(CASE)

    const region = await moves()
    await userEvent.click(within(region).getByRole('button', { name: 'Close case' }))
    await userEvent.type(within(region).getByLabelText(/Outcome note/), 'Done')

    vi.restoreAllMocks()
    mockApi({
      'GET /auth/me/': { body: userFor('doctor') },
      'POST /emergencies/:reference/actions/': fail(400, { note: ['Add an outcome note to close the case.'] }),
    })
    await userEvent.click(within(region).getByRole('button', { name: 'Close case' }))

    expect(await within(region).findByText('Add an outcome note to close the case.')).toBeInTheDocument()
    expect(within(region).getByLabelText(/Outcome note/)).toHaveAttribute('aria-invalid', 'true')
    expect(within(await details()).getByText('Fulfilled')).toBeInTheDocument()
  })

  it('shows a closed case’s outcome, above its timeline', async () => {
    const closed = { ...sampleCases(new Date())[0]!, status: 'closed' as const }
    const close: StatusChange = {
      fromStatus: 'fulfilled',
      toStatus: 'closed',
      action: 'close',
      note: 'Stable on the ward; blood issued',
      actor: 'Dr. Ayesha Khan',
      at: new Date().toISOString(),
    }
    mockStaffApi({ role: 'nurse', cases: [closed], histories: { [closed.id]: [opening, close] } })
    renderStaff(CASE)

    const outcome = await screen.findByRole('region', { name: 'Outcome' })
    expect(within(outcome).getByText('Stable on the ward; blood issued')).toBeInTheDocument()
    expect(screen.getByText('No moves from closed.')).toBeInTheDocument()
  })

  it('says System for a move the system made, and labels an escalated case in words', async () => {
    const escalated = { ...sampleCases(new Date())[0]!, status: 'escalated' as const }
    const automatic: StatusChange = {
      fromStatus: 'open',
      toStatus: 'escalated',
      action: 'escalate',
      note: 'Not fulfilled within 30 minutes (automatic)',
      actor: null,
      at: new Date().toISOString(),
    }
    mockStaffApi({ role: 'doctor', cases: [escalated], histories: { [escalated.id]: [opening, automatic] } })
    renderStaff(CASE)

    expect(within(await details()).getByText('Escalated')).toBeInTheDocument()
    const [, entry] = await entries()
    expect(entry).toHaveTextContent('Open → Escalated')
    expect(entry).toHaveTextContent('· System')
    expect(within(entry!).getByText('Not fulfilled within 30 minutes (automatic)')).toBeInTheDocument()
  })
})

describe('EmergencyCasePage: the new kinds of need and sources in the network (#32, #38)', () => {
  it('shows an equipment and an operating-room need with what this hospital has, as text', async () => {
    mockStaffApi({ role: 'doctor', cases: [sampleNewNeedsCase(new Date())] })
    renderStaff('/staff/emergencies/EC-2026-0003')

    const panel = await screen.findByRole('region', { name: 'EC-2026-0003' })
    const [vents, room] = within(within(panel).getByRole('list')).getAllByRole('listitem')
    expect(within(vents!).getByText('2 × Ventilator')).toBeInTheDocument()
    expect(within(vents!).getByText('Available here: 1 · Short: 1')).toBeInTheDocument()
    expect(within(room!).getByText('1 × Operating room (cardiac)')).toBeInTheDocument()
    expect(within(room!).getByText('Available here: 0 · Short: 1')).toBeInTheDocument()
  })

  it('lists, for each short need, the hospitals that have it: the marker, distance and expiry', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff(CASE)

    const sources = await screen.findByRole('region', { name: 'Sources in the network' })
    const blood = (await within(sources).findByRole('heading', { name: 'O− red cells: short 3' })).closest('section')!
    const riverside = within(blood).getByText('Riverside Medical Centre').closest('li')!
    expect(within(riverside).getByText('5 available')).toBeInTheDocument()
    expect(within(riverside).getByText('covers it')).toBeInTheDocument()
    expect(within(riverside).getByText('4.2 km · ~6 min')).toBeInTheDocument()
    expect(within(riverside).getByText(/Earliest expiry/, { selector: 'span' })).toBeInTheDocument()
    const northside = within(blood).getByText("Northside Children's Hospital").closest('li')!
    expect(within(northside).getByText('1 available')).toBeInTheDocument()
    expect(within(northside).getByText('partial')).toBeInTheDocument()
    expect(within(northside).getByText('Distance unknown')).toBeInTheDocument()
  })

  it('says no other hospital has a need that none of them have', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff(CASE)

    const sources = await screen.findByRole('region', { name: 'Sources in the network' })
    const bed = (await within(sources).findByRole('heading', { name: 'ICU bed: short 1' })).closest('section')!
    expect(within(bed).getByText('No other hospital has this right now')).toBeInTheDocument()
  })

  it('lists the sources for the new kinds of need, and the empty state for an operating room', async () => {
    mockStaffApi({ role: 'doctor', cases: [sampleNewNeedsCase(new Date())] })
    renderStaff('/staff/emergencies/EC-2026-0003')

    const sources = await screen.findByRole('region', { name: 'Sources in the network' })
    const vents = (await within(sources).findByRole('heading', { name: 'Ventilator: short 1' })).closest('section')!
    expect(within(vents).getByText('covers it')).toBeInTheDocument()
    const cardiac = (await within(sources).findByRole('heading', { name: 'Cardiac operating room: short 1' })).closest('section')!
    expect(within(cardiac).getByText('No other hospital has this right now')).toBeInTheDocument()
  })

  it('does not ask for sources when the case is covered here', async () => {
    const { fetchMock } = mockStaffApi({ role: 'doctor', cases: [sampleCases(new Date())[1]!] })
    renderStaff('/staff/emergencies/EC-2026-0001')

    await screen.findByRole('region', { name: 'EC-2026-0001' })
    expect(screen.queryByRole('region', { name: 'Sources in the network' })).toBeNull()
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/candidates/'))).toBe(false)
  })
})

/** The rows of one short need's list, in the order they are on the screen (not the nested factor lists). */
async function sourceRows(need: string): Promise<HTMLElement[]> {
  const sources = await screen.findByRole('region', { name: 'Sources in the network' })
  const section = (await within(sources).findByRole('heading', { name: need })).closest('section')!
  return Array.from(section.querySelector('ul')!.children) as HTMLElement[]
}

describe('EmergencyCasePage: ranked sources and their scores (#41)', () => {
  it('shows the sources in the order the server ranks them, each with its rank and score', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff(CASE)

    const [first, second] = await sourceRows('O− red cells: short 3')
    expect(within(first!).getByText('Riverside Medical Centre')).toBeInTheDocument()
    expect(within(first!).getByText('Rank 1')).toBeInTheDocument()
    expect(within(first!).getByText('87.6 / 100')).toBeInTheDocument()
    expect(within(second!).getByText("Northside Children's Hospital")).toBeInTheDocument()
    expect(within(second!).getByText('Rank 2')).toBeInTheDocument()
    expect(within(second!).getByText('69.7 / 100')).toBeInTheDocument()
  })

  it('labels only the top source as recommended, with a badge as well as its emphasis', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff(CASE)

    const [first, second] = await sourceRows('O− red cells: short 3')
    expect(within(first!).getByText('Recommended')).toBeInTheDocument()
    expect(within(second!).queryByText('Recommended')).toBeNull()
  })

  it('says how each list is ordered', async () => {
    mockStaffApi({ role: 'doctor', cases: [sampleNewNeedsCase(new Date())] })
    renderStaff('/staff/emergencies/EC-2026-0003')

    const sources = await screen.findByRole('region', { name: 'Sources in the network' })
    const vents = (await within(sources).findByRole('heading', { name: 'Ventilator: short 1' })).closest('section')!
    expect(within(vents).getByText('Ordered by nearest first')).toBeInTheDocument()
  })

  it('explains each score in a disclosure: every factor with its reason and points, then the total', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff(CASE)

    const [first] = await sourceRows('O− red cells: short 3')
    const why = within(first!).getByText('Why this score?').closest('details')!
    expect(why.open).toBe(false)
    expect(within(why).getByText('Strategy: Earliest expiry first')).toBeInTheDocument()

    const lines = Array.from(why.querySelectorAll('li')).map((li) => li.textContent?.replace(/\s+/g, ' ').trim())
    expect(lines).toEqual([
      'Expiry: expires in 9 days 39.3 points',
      'Blood group match: identical group 20.0 points',
      'Distance: 4.2 km, about 6 min 18.3 points',
      'Stock: 5 available, 3 needed 10.0 points',
      'Total 87.6 of 100',
    ])
    const points = Array.from(why.querySelectorAll('li'))
      .slice(0, -1)
      .map((li) => Number(li.querySelector('span')!.textContent!.replace(' points', '')))
    expect(points.reduce((sum, p) => sum + p, 0)).toBeCloseTo(87.6, 1)
  })

  it('shows the distance and travel time of each source, and "Distance unknown" when it is not known', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff(CASE)

    const [riverside, northside] = await sourceRows('O− red cells: short 3')
    expect(within(riverside!).getByText('4.2 km · ~6 min')).toBeInTheDocument()
    expect(within(northside!).getByText('Distance unknown')).toBeInTheDocument()
  })
})

/** The rows of the best single destination list, in the order they are on the screen. */
async function destinationRows(): Promise<HTMLElement[]> {
  const sources = await screen.findByRole('region', { name: 'Sources in the network' })
  const best = await within(sources).findByRole('region', { name: 'Best single destination' })
  return Array.from(best.querySelector('ul')!.children) as HTMLElement[]
}

describe('EmergencyCasePage: the best single destination across the short needs (#42)', () => {
  it('lists the hospitals in the server’s order, labelling the one with everything and recommending it', async () => {
    mockStaffApi({ role: 'doctor', candidates: sampleThreeNeedSources() })
    renderStaff(CASE)

    const [full, partial, sea] = await destinationRows()
    expect(
      [full, partial, sea].map((row) => row!.querySelector('strong')?.textContent),
    ).toEqual(['Riverside Medical Centre', "Northside Children's Hospital", 'Seaview Hospital'])
    expect(within(full!).getByText('Has everything')).toBeInTheDocument()
    expect(within(full!).getByText('Recommended')).toBeInTheDocument()
    expect(within(partial!).queryByText('Has everything')).toBeNull()
    expect(within(partial!).queryByText('Recommended')).toBeNull()
    expect(within(sea!).queryByText('Recommended')).toBeNull()
  })

  it('shows each hospital’s coverage, score, and distance and travel time', async () => {
    mockStaffApi({ role: 'doctor', candidates: sampleThreeNeedSources() })
    renderStaff(CASE)

    const [full, partial] = await destinationRows()
    expect(within(full!).getByText('3 of 3 needs')).toBeInTheDocument()
    expect(within(full!).getByText('88.7 / 100')).toBeInTheDocument()
    expect(within(full!).getByText('4.2 km · ~6 min')).toBeInTheDocument()
    expect(within(partial!).getByText('1 of 3 needs')).toBeInTheDocument()
    expect(within(partial!).getByText('Distance unknown')).toBeInTheDocument()
  })

  it('lists what a partial hospital is missing, with only some of a partial quantity', async () => {
    mockStaffApi({ role: 'doctor', candidates: sampleThreeNeedSources() })
    renderStaff(CASE)

    const [, partial, sea] = await destinationRows()
    expect(within(partial!).getByText('Missing: 2 × Ventilator, 1 × O− red cells (only 1 of 2)')).toBeInTheDocument()
    expect(within(sea!).getByText('Missing: 1 × ICU bed, 1 × Ventilator (only 1 of 2), 2 × O− red cells')).toBeInTheDocument()
  })

  it('says no single hospital has everything when none does', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff(CASE)

    const sources = await screen.findByRole('region', { name: 'Sources in the network' })
    const best = await within(sources).findByRole('region', { name: 'Best single destination' })
    expect(
      within(best).getByText('No single hospital has everything; split the request or use the per-need sources below.'),
    ).toBeInTheDocument()
    expect(within(best).queryByText('Has everything')).toBeNull()
  })

  it('is hidden when there is only one short need, because that need’s own list already answers it', async () => {
    const full = sampleThreeNeedSources()
    mockStaffApi({ role: 'doctor', candidates: { ...full, items: [full.items[0]!] } })
    renderStaff(CASE)

    expect(await screen.findByRole('heading', { name: 'ICU bed: short 1' })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Best single destination' })).toBeNull()
    expect(screen.queryByRole('heading', { name: 'Best single destination' })).toBeNull()
  })
})

describe('EmergencyCasePage stock holds (story #43)', () => {
  const holds = async () => screen.findByRole('region', { name: 'Reservations' })
  /** The first need of the case: "4 × O− red cells", 1 free here, nothing held yet. */
  const firstNeed = async () => within(await details()).getAllByRole('listitem')[0]!
  const postsTo = (fetchMock: ReturnType<typeof mockStaffApi>['fetchMock'], path: string) =>
    fetchMock.mock.calls.filter(([url, init]) => String(url).includes(path) && init?.method === 'POST')

  it('holds what is free here for a need, shows the hold with the time it lasts until, and updates the figures', async () => {
    const { fetchMock } = mockStaffApi({ role: 'doctor' })
    renderStaff(CASE)

    const need = await firstNeed()
    expect(within(need).getByLabelText('How many')).toHaveValue(1)
    await userEvent.click(within(need).getByRole('button', { name: 'Reserve 1 here' }))

    const panel = await holds()
    expect(await within(panel).findByText('O− red cells DN-0001')).toBeInTheDocument()
    expect(within(panel).getByText('Held')).toBeInTheDocument()
    expect(within(panel).getByText(/Holds until/)).toBeInTheDocument()
    expect(within(panel).getByText(/reserved by Dr\. Ayesha Khan/)).toBeInTheDocument()
    expect(within(await details()).getByText('Available here: 0 · Short: 3')).toBeInTheDocument()
    const [call] = postsTo(fetchMock, '/reservations/')
    expect(JSON.parse(String(call![1]!.body))).toEqual({ itemId: 1, quantity: 1 })
  })

  it('won’t ask for more than the need still lacks, and says so on the page without asking the server', async () => {
    const { fetchMock } = mockStaffApi({ role: 'doctor' })
    renderStaff(CASE)

    const need = await firstNeed()
    await userEvent.clear(within(need).getByLabelText('How many'))
    await userEvent.type(within(need).getByLabelText('How many'), '5')
    await userEvent.click(within(need).getByRole('button', { name: 'Reserve here' }))

    expect(within(need).getByRole('alert')).toHaveTextContent('Enter a whole number from 1 to 4.')
    expect(postsTo(fetchMock, '/reservations/')).toHaveLength(0)
  })

  it('releases a hold, which gives the stock back here', async () => {
    mockStaffApi({ role: 'nurse' })
    renderStaff(CASE)

    await userEvent.click(within(await firstNeed()).getByRole('button', { name: 'Reserve 1 here' }))
    const panel = await holds()
    await userEvent.click(await within(panel).findByRole('button', { name: 'Release O− red cells DN-0001' }))

    expect(await within(panel).findByText('Nothing is held for this case.')).toBeInTheDocument()
    expect(within(await details()).getByText('Available here: 1 · Short: 3')).toBeInTheDocument()
    expect(await within(panel).findByText('Released O− red cells DN-0001.')).toBeInTheDocument()
  })

  it('shows a blood bank the holds without the reserve or release controls (view only)', async () => {
    mockStaffApi({ role: 'bloodBank' })
    renderStaff(CASE)

    await details()
    expect(screen.queryByRole('button', { name: /Reserve/ })).toBeNull()
    expect(screen.queryByRole('region', { name: 'Reservations' })).toBeNull()
  })
})

describe('EmergencyCasePage allocation (stories #45, #46)', () => {
  const holds = async () => screen.findByRole('region', { name: 'Reservations' })
  const oneBloodHold = [{ reference: 'EC-2026-0002', itemId: 1, count: 1 }]
  const postsTo = (fetchMock: ReturnType<typeof mockStaffApi>['fetchMock'], path: string) =>
    fetchMock.mock.calls.filter(([url, init]) => String(url).includes(path) && init?.method === 'POST')

  it('allocates a held reservation: the status, the remaining quantity and the timeline all update', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const { fetchMock } = mockStaffApi({ role: 'admin', held: oneBloodHold })
    renderStaff(CASE)

    const panel = await holds()
    expect(within(await details()).getByText('0 of 4 allocated · 4 remaining')).toBeInTheDocument()
    await userEvent.click(within(panel).getByRole('button', { name: 'Allocate O− red cells DN-0001' }))

    expect(await within(panel).findByText('Allocated O− red cells DN-0001.')).toBeInTheDocument()
    expect(within(panel).queryByRole('button', { name: /^Allocate/ })).toBeNull()
    expect(within(panel).getByText('Allocated')).toBeInTheDocument()
    expect(within(await details()).getByText('Partially fulfilled')).toBeInTheDocument()
    expect(within(await details()).getByText('1 of 4 allocated · 3 remaining')).toBeInTheDocument()
    expect(await entryHeadings()).toEqual([
      'Case opened',
      'Open → Matching',
      'Allocated O− red cells DN-0001 from CityCare General Hospital by Sadia Admin',
      'Matching → Partially fulfilled',
    ])
    const [call] = postsTo(fetchMock, '/reservations/1/allocate/')
    expect(JSON.parse(String(call![1]!.body))).toEqual({ note: '' })
  })

  it('says a need is fully allocated, and the case fulfilled, once every unit is allocated', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    mockStaffApi({ role: 'nurse', held: [{ reference: 'EC-2026-0001', itemId: 1, count: 2 }] })
    renderStaff('/staff/emergencies/EC-2026-0001')

    const panel = await holds()
    await userEvent.click(within(panel).getByRole('button', { name: 'Allocate Bed GENERAL-01' }))
    await within(panel).findByText('Allocated Bed GENERAL-01.')
    await userEvent.click(within(panel).getByRole('button', { name: 'Allocate Bed GENERAL-02' }))
    await within(panel).findByText('Allocated Bed GENERAL-02.')

    const facts = await screen.findByRole('region', { name: 'EC-2026-0001' })
    expect(within(facts).getByText('Fully allocated')).toBeInTheDocument()
    expect(within(facts).getByText('Fulfilled')).toBeInTheDocument()
  })

  it('does nothing when the confirm is declined', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const { fetchMock } = mockStaffApi({ role: 'admin', held: oneBloodHold })
    renderStaff(CASE)

    await userEvent.click(within(await holds()).getByRole('button', { name: 'Allocate O− red cells DN-0001' }))
    expect(postsTo(fetchMock, '/allocate/')).toHaveLength(0)
  })

  it('offers no Allocate button where the role can’t allocate the type (a doctor can only view blood)', async () => {
    mockStaffApi({ role: 'doctor', held: oneBloodHold })
    renderStaff(CASE)

    const panel = await holds()
    expect(within(panel).getByRole('button', { name: 'Release O− red cells DN-0001' })).toBeInTheDocument()
    expect(within(panel).queryByRole('button', { name: /^Allocate/ })).toBeNull()
  })

  it('shows the server’s reason when the allocation is refused (409), and changes nothing', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    mockStaffApi({ role: 'admin', held: oneBloodHold })
    renderStaff(CASE)

    const panel = await holds()
    await allocateReservation(1) // someone else allocates it first; this page still shows it as held
    await userEvent.click(within(panel).getByRole('button', { name: 'Allocate O− red cells DN-0001' }))

    expect(await within(panel).findByRole('alert')).toHaveTextContent('This reservation is already allocated.')
    expect(within(await details()).getByText('0 of 4 allocated · 4 remaining')).toBeInTheDocument()
  })
})
