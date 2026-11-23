import type { SimulationStatus } from '../../api/simulation'

/** The Simulation panel's state on a quiet regular day (B21): live at real time, two recent events. */
export function sampleSimulation(now: Date): SimulationStatus {
  const at = (minutesAgo: number) => new Date(now.getTime() - minutesAgo * 60_000).toISOString()
  return {
    enabled: true,
    mode: 'live',
    paused: false,
    speed: 1,
    speeds: [0.5, 1, 2, 5, 10, 60],
    cityTime: now.toISOString(),
    realTime: now.toISOString(),
    aheadMinutes: 0,
    engineAt: at(0.2),
    scenario: 'regular',
    scenarios: [
      { value: 'regular', label: 'Regular day' },
      { value: 'flu', label: 'Flu season' },
      { value: 'slow', label: 'Slow day' },
    ],
    fastForwardOptions: ['30m', '1h', '1d', '1w', '2w'],
    fastForward: null,
    incident: null,
    events: [
      { id: 2, at: at(4), kind: 'er.resuscitation', message: 'Eastgate Trauma Centre: a triage 1 patient arrived (ED-4821K).', hospital: 'Eastgate Trauma Centre' },
      { id: 1, at: at(12), kind: 'or.emergency', message: 'CityCare General Hospital: emergency case in Trauma theatre.', hospital: 'CityCare General Hospital' },
    ],
  }
}
