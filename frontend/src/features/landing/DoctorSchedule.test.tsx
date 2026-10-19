import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'
import type { Doctor } from '../../api/publicStatus'
import { DoctorSchedule } from './DoctorSchedule'

const now = new Date(2026, 9, 5, 10, 0)
const doctors: Doctor[] = [
  { id: '1', name: 'Dr. Ayesha Khan', department: 'Cardiology', start: '09:00', end: '13:00' },
  { id: '2', name: 'Dr. Sana Malik', department: 'Paediatrics', start: '14:00', end: '18:00' },
  { id: '3', name: 'Dr. Usman Farooq', department: 'Emergency medicine', start: '20:00', end: '08:00' },
]

it('tags doctors who are in now and shows their hours', () => {
  render(<DoctorSchedule doctors={doctors} now={now} />)
  const ayesha = screen.getByRole('listitem', { name: /Ayesha Khan/ })
  expect(within(ayesha).getByText('In now')).toBeInTheDocument()
  expect(within(ayesha).getByText('09:00–13:00')).toBeInTheDocument()
  expect(within(screen.getByRole('listitem', { name: /Sana Malik/ })).queryByText('In now')).toBeNull()
})

it('filters by department', async () => {
  render(<DoctorSchedule doctors={doctors} now={now} />)
  await userEvent.click(screen.getByRole('button', { name: 'Paediatrics' }))
  expect(screen.getByRole('button', { name: 'Paediatrics' })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getAllByRole('listitem')).toHaveLength(1)
  await userEvent.click(screen.getByRole('button', { name: 'All' }))
  expect(screen.getAllByRole('listitem')).toHaveLength(3)
})

it('says so when nothing is published', () => {
  render(<DoctorSchedule doctors={[]} now={now} />)
  expect(screen.getByText('No doctor schedules are published for today.')).toBeInTheDocument()
})
