import type { Module } from './roles'

/**
 * The question each page answers (B22), shown under its title. docs/product/page-purposes.md keeps the same table
 * with each page's actions and charts. Pages that are a list or a form have none.
 */
export const PURPOSE: Partial<Record<Module, string>> = {
  overview: 'What needs me now?',
  commandCentre: 'Which hospitals are under strain, and what is moving between them?',
  emergencyDepartment: 'Who is waiting, who is next, and why is the wait what it is?',
  emergencies: 'Which cases still lack something, and since when?',
  transfers: 'What is on its way to us, and from us?',
  beds: 'Where can the next patient go, and which beds free up soon?',
  blood: 'Which groups run short, and what expires first?',
  donors: 'Who can donate now, and who is booked?',
  pharmacy: 'What runs out first?',
  equipment: 'Which devices are free, and which are out of service?',
  operatingRooms: 'Which rooms are free now and later today, and is the list running late?',
  staffing: 'Who is on duty now, who is missing, and is any department short?',
  ambulances: 'Which vehicles are free, and which trips are under way?',
  reports: 'What happened over a period?',
  simulation: 'How fast does the city run, and what is happening in it?',
}
