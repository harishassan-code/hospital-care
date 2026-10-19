import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockStaffApi } from '../../test/mockApi'
import { renderStaff } from '../../test/renderStaff'

afterEach(() => vi.restoreAllMocks())

const section = (name: string) => screen.findByRole('region', { name })

describe('HospitalDetailPage (stories 1.3 Hospital structure and capability profile)', () => {
  it('shows the hospital, its capabilities and its structure', async () => {
    mockStaffApi({ role: 'doctor' })
    renderStaff('/staff/hospitals/1')
    expect(await screen.findByRole('heading', { name: 'CityCare General Hospital' })).toBeInTheDocument()
    expect(screen.getByText('Coordinates: 24.8607, 67.0011')).toBeInTheDocument()
    const capabilities = screen.getByRole('list', { name: 'Capabilities' })
    expect(within(capabilities).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      'Trauma centre',
      'Intensive care unit',
      'Blood bank',
    ])
    expect(within(await section('Wards')).getByText('ICU · Intensive care · Emergency medicine · 10 beds')).toBeInTheDocument()
    expect(within(await section('Storage locations')).getByText('Blood fridge 1')).toBeInTheDocument()
  })

  it('gives view-only roles no way to change anything', async () => {
    mockStaffApi({ role: 'bloodBank' })
    renderStaff('/staff/hospitals/1')
    await screen.findByRole('heading', { name: 'CityCare General Hospital' })
    expect(screen.queryByRole('link', { name: 'Edit details' })).toBeNull()
    expect(screen.queryByRole('button', { name: /Add|Remove/ })).toBeNull()
  })

  it('says when a hospital has no capabilities', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/hospitals/3')
    expect(await screen.findByText('No capabilities recorded.')).toBeInTheDocument()
    expect(screen.getByText('No departments yet.')).toBeInTheDocument()
  })

  it('adds a department, then offers it for new wards', async () => {
    const { hospitals } = mockStaffApi({ role: 'admin' })
    renderStaff('/staff/hospitals/1')
    const departments = await section('Departments')
    await userEvent.type(within(departments).getByLabelText('Department name'), 'Cardiology')
    await userEvent.click(within(departments).getByRole('button', { name: 'Add department' }))
    expect(await within(departments).findByText('Added Cardiology.')).toBeInTheDocument()
    expect(within(departments).getByLabelText('Department name')).toHaveValue('')
    expect(hospitals[0].departments.map((d) => d.name)).toContain('Cardiology')
    const wards = await section('Wards')
    expect(within(wards).getByRole('option', { name: 'Cardiology' })).toBeInTheDocument()
  })

  it('asks for the required fields of a ward and focuses the first missing one', async () => {
    const { fetchMock } = mockStaffApi({ role: 'admin' })
    renderStaff('/staff/hospitals/1')
    const wards = await section('Wards')
    await userEvent.type(within(wards).getByLabelText('Ward name'), 'Burns unit')
    await userEvent.click(within(wards).getByRole('button', { name: 'Add ward' }))
    expect(within(wards).getByLabelText('Kind of care')).toHaveFocus()
    expect(within(wards).getByLabelText('Kind of care')).toHaveAccessibleDescription('Enter the kind of care')
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
  })

  it('sends the ward with its department and shows the server’s duplicate-name message on the field', async () => {
    const { fetchMock } = mockStaffApi({ role: 'admin' })
    renderStaff('/staff/hospitals/1')
    const wards = await section('Wards')
    await userEvent.type(within(wards).getByLabelText('Ward name'), 'icu')
    await userEvent.type(within(wards).getByLabelText('Kind of care'), 'Intensive care')
    await userEvent.selectOptions(within(wards).getByLabelText('Department'), 'Surgery')
    await userEvent.click(within(wards).getByRole('button', { name: 'Add ward' }))
    expect(await within(wards).findByText('This hospital already has one with that name.')).toBeInTheDocument()
    expect(within(wards).getByLabelText('Ward name')).toHaveFocus()
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ name: 'icu', kind: 'Intensive care', departmentId: 12 })
  })

  it('removes an empty ward but explains why a ward with beds stays', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/hospitals/1')
    const wards = await section('Wards')
    await userEvent.click(within(wards).getByRole('button', { name: 'Remove ICU' }))
    expect(await within(wards).findByRole('alert')).toHaveTextContent('This ward still has beds. Move or remove them first.')
    await userEvent.click(within(wards).getByRole('button', { name: 'Remove Step-down' }))
    expect(await within(wards).findByText('Removed Step-down.')).toBeInTheDocument()
    expect(within(wards).queryByText(/Step-down ·/)).toBeNull()
  })

  it('says when the hospital does not exist', async () => {
    mockStaffApi({ role: 'admin' })
    renderStaff('/staff/hospitals/999')
    expect(await screen.findByText('No hospital with that id.')).toBeInTheDocument()
  })
})
