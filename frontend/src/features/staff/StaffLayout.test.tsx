import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { at } from '../../test/clock'
import StaffLayout from './StaffLayout'

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(at('15:00'))
})
afterEach(() => vi.useRealTimers())

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/staff" element={<StaffLayout />}>
          <Route index element={<p>overview content</p>} />
          <Route path="beds" element={<p>beds content</p>} />
          <Route path="blood" element={<p>blood content</p>} />
          <Route path="pharmacy" element={<p>pharmacy content</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

const navLinks = () =>
  within(screen.getByRole('navigation', { name: 'Staff' }))
    .getAllByRole('link')
    .map((a) => a.textContent)

describe('StaffLayout', () => {
  it('shows every module to an admin and marks the current page', async () => {
    renderAt('/staff/beds')
    expect(navLinks()).toEqual(['Overview', 'Beds', 'Blood bank', 'Pharmacy'])
    expect(screen.getByRole('link', { name: 'Beds' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('heading', { level: 1, name: 'Beds' })).toBeInTheDocument()
    expect(await screen.findByText('beds content')).toBeInTheDocument()
  })

  it('narrows the navigation when the preview role changes', async () => {
    renderAt('/staff')
    await userEvent.selectOptions(screen.getByLabelText('Viewing as'), 'Pharmacist')
    expect(navLinks()).toEqual(['Overview', 'Pharmacy'])
  })

  it('blocks a page the role cannot open', async () => {
    renderAt('/staff/beds')
    await userEvent.selectOptions(screen.getByLabelText('Viewing as'), 'Blood bank')
    expect(screen.getByRole('heading', { name: 'You don’t have access to this page' })).toBeInTheDocument()
    expect(screen.queryByText('beds content')).toBeNull()
  })

  it('shows the current shift and how many items need attention', async () => {
    renderAt('/staff')
    expect(screen.getByText(/Evening shift/)).toHaveTextContent('Evening shift · 14:00–20:00 · 5 h left')
    const bell = await screen.findByRole('link', { name: /items? need attention/ })
    expect(bell).toHaveAttribute('href', '/staff#attention')
  })
})
