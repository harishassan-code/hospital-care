import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { Trip } from '../../api/trips'
import { TripPanel } from './TripPanel'

const trip = (overrides: Partial<Trip> = {}): Trip => ({
  id: 7,
  transferId: 2,
  status: 'dispatched',
  ambulance: { id: 3, identifier: 'AMB-03', type: 'patientTransport' },
  etaMinutes: 25,
  dispatchedBy: 'Sadia Admin',
  dispatchedAt: '2026-11-18T09:40:00+05:00',
  departedAt: null,
  arrivedAt: null,
  completedAt: null,
  actions: ['depart'],
  ...overrides,
})

describe('TripPanel (story #51)', () => {
  it('shows the ambulance, its type, the estimate and who sent it, and the step buttons it is given', () => {
    render(<TripPanel trip={trip()} busy={false} onStep={() => undefined} />)
    const panel = screen.getByRole('region', { name: 'Trip for transfer #2' })
    expect(within(panel).getByRole('heading', { name: 'Ambulance AMB-03' })).toBeInTheDocument()
    expect(within(panel).getByText('Patient transport')).toBeInTheDocument()
    expect(within(panel).getByText('about 25 min')).toBeInTheDocument()
    expect(within(panel).getByText('Sadia Admin')).toBeInTheDocument()
    expect(within(panel).getByText('Departed: not yet')).toBeInTheDocument()
    expect(within(panel).getByRole('button', { name: 'Mark departed (transfer #2)' })).toBeInTheDocument()
    expect(within(panel).queryByRole('button', { name: /Mark arrived/ })).toBeNull()
  })

  it('shows the time of each step that has happened', () => {
    render(
      <TripPanel
        trip={trip({ status: 'enRoute', departedAt: '2026-11-18T09:50:00+05:00', actions: ['arrive'] })}
        busy={false}
        onStep={() => undefined}
      />,
    )
    const panel = screen.getByRole('region', { name: 'Trip for transfer #2' })
    expect(within(panel).getByText('En route')).toBeInTheDocument()
    expect(within(panel).getByText('Departed').closest('li')).toHaveTextContent('Departed · ')
    expect(within(panel).getByText('Arrived: not yet')).toBeInTheDocument()
  })

  it('gives the step to the page, and waits while a save is running', async () => {
    const onStep = vi.fn()
    const { rerender } = render(<TripPanel trip={trip()} busy={false} onStep={onStep} />)
    await userEvent.click(screen.getByRole('button', { name: 'Mark departed (transfer #2)' }))
    expect(onStep).toHaveBeenCalledWith('depart')

    rerender(<TripPanel trip={trip()} busy onStep={onStep} />)
    expect(screen.getByRole('button', { name: 'Mark departed (transfer #2)' })).toBeDisabled()
  })

  it('shows no buttons to someone who may not step the trip (the receiving hospital)', () => {
    render(<TripPanel trip={trip({ actions: [] })} busy={false} onStep={() => undefined} />)
    const panel = screen.getByRole('region', { name: 'Trip for transfer #2' })
    expect(within(panel).queryByRole('button')).toBeNull()
    expect(within(panel).getByRole('heading', { name: 'Ambulance AMB-03' })).toBeInTheDocument()
  })
})
