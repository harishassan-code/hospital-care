import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { BarChart, ChartFrame, Sparkline, Timeline, TimeSeriesChart } from '.'

const H = 3_600_000
const T0 = Date.parse('2026-11-24T03:00:00Z') // 08:00 in Karachi

describe('chart kit (B22)', () => {
  it('shows a chart, and the same figures as a table on request', async () => {
    render(
      <ChartFrame
        title="Arrivals"
        summary="Patients arriving each hour."
        legend={[{ label: 'Today', color: 'red' }]}
        table={{ columns: ['Hour', 'Today'], rows: [['08:00', 4], ['09:00', 7]] }}
      >
        <TimeSeriesChart label="Arrivals today" unit="hour" series={[{ key: 'a', label: 'Today', color: 'red', points: [{ t: T0, value: 4 }, { t: T0 + H, value: 7 }] }]} />
      </ChartFrame>,
    )
    expect(screen.getByRole('img', { name: 'Arrivals today' })).toBeInTheDocument()
    expect(screen.getByRole('list', { name: 'Legend' })).toHaveTextContent('Today')
    await userEvent.click(screen.getByRole('button', { name: 'Show as table' }))
    const table = screen.getByRole('table', { name: 'Arrivals' })
    expect(within(table).getAllByRole('row').map((r) => r.textContent)).toEqual(['HourToday', '08:004', '09:007'])
    expect(screen.getByRole('button', { name: 'Show as chart' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('says when the figures are loading, missing or empty', () => {
    const { rerender } = render(
      <ChartFrame title="X" summary="Y" table={{ columns: [], rows: [] }} state="loading">
        <span>chart</span>
      </ChartFrame>,
    )
    expect(screen.getByText('Loading the figures…')).toBeInTheDocument()
    rerender(
      <ChartFrame title="X" summary="Y" table={{ columns: [], rows: [] }} state="empty" empty="Nothing yet.">
        <span>chart</span>
      </ChartFrame>,
    )
    expect(screen.getByText('Nothing yet.')).toBeInTheDocument()
    expect(screen.queryByText('chart')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Show as table' })).not.toBeInTheDocument()
  })

  it('reads each point from the keyboard: every series at that time, and the typical band', () => {
    render(
      <TimeSeriesChart
        label="Arrivals"
        unit="hour"
        valueSuffix="patients"
        series={[
          { key: 'a', label: 'Arrivals', color: 'red', points: [{ t: T0, value: 4 }, { t: T0 + H, value: 7 }] },
          { key: 'd', label: 'Departures', color: 'blue', points: [{ t: T0, value: 3 }, { t: T0 + H, value: 5 }] },
        ]}
        band={{ label: 'Typical', points: [{ t: T0, value: 5 }, { t: T0 + H, value: 6 }] }}
      />,
    )
    const chart = screen.getByRole('img', { name: 'Arrivals' })
    chart.focus()
    fireEvent.keyDown(chart, { key: 'ArrowRight' })
    expect(screen.getByRole('status')).toHaveTextContent('08:00 · Arrivals: 4 patients · Departures: 3 patients · Typical: 5')
    fireEvent.keyDown(chart, { key: 'ArrowRight' })
    expect(screen.getByRole('status')).toHaveTextContent('09:00 · Arrivals: 7 patients')
    fireEvent.keyDown(chart, { key: 'Escape' })
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('writes every bar’s figure and flags with a word, never colour alone', () => {
    render(
      <BarChart
        label="Red cells"
        thresholds={[6, 30]}
        bars={[
          { label: 'O−', segments: [{ key: 'n', label: 'Usable', value: 2, color: 'red' }], note: '2 / min 6', flag: 'Critical' },
          { label: 'O+', segments: [{ key: 'n', label: 'Usable', value: 40, color: 'red' }] },
        ]}
      />,
    )
    const rows = within(screen.getByRole('list', { name: 'Red cells' })).getAllByRole('listitem')
    expect(rows[0]).toHaveTextContent('O−2 / min 6Critical')
    expect(rows[1]).toHaveTextContent('O+40')
  })

  it('draws a timeline with each booking named, and a sparkline with its name', () => {
    render(
      <>
        <Timeline
          label="Theatres"
          from={T0}
          to={T0 + 12 * H}
          now={T0 + 3 * H}
          rows={[{ label: 'OR 1', items: [{ start: T0, end: T0 + 2 * H, label: 'Hernia repair', tone: 'done' }] }]}
        />
        <Sparkline values={[50, 60, 70]} label="Occupancy over 24 hours" />
      </>,
    )
    expect(within(screen.getByRole('group', { name: 'Theatres' })).getByText('Hernia repair')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Occupancy over 24 hours' })).toBeInTheDocument()
  })
})
