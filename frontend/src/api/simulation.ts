import { apiGet, apiPost } from './client'

/** The live city simulation (B21). Shapes of apps/simulation/controls.status() and views.py. */
export type Scenario = 'regular' | 'flu' | 'slow'
export type FastForward = '30m' | '1h' | '1d' | '1w' | '2w'
export type SimulationAction =
  | 'pause'
  | 'resume'
  | 'speed'
  | 'fastForward'
  | 'catchUp'
  | 'scenario'
  | 'massCasualty'
  | 'endIncident'

export interface SimEvent {
  id: number
  at: string
  kind: string
  message: string
  hospital: string | null
}

export interface SimulationStatus {
  enabled: boolean
  mode: 'real' | 'live' | 'paused' | 'fastForward'
  paused: boolean
  speed: number
  speeds: number[]
  cityTime: string
  realTime: string
  /** Minutes the city clock is ahead of the real one (negative: behind). */
  aheadMinutes: number
  engineAt: string
  scenario: Scenario
  scenarios: { value: Scenario; label: string }[]
  fastForwardOptions: FastForward[]
  fastForward: { from: string; to: string; progress: string; percent: number } | null
  incident: { until: string; hospitals: string[] } | null
  events: SimEvent[]
  /** Only on /advance/: whether the engine ran, and whether it still has catching up to do. */
  ran?: boolean
  behind?: boolean
}

/** GET /api/simulation/: the CityCare admin only. */
export function getSimulation(): Promise<SimulationStatus> {
  return apiGet<SimulationStatus>('/simulation/')
}

/** POST /api/simulation/control/: pause, resume, speed, fast-forward, scenario, mass-casualty event. */
export function controlSimulation(action: SimulationAction, value = ''): Promise<SimulationStatus> {
  return apiPost<SimulationStatus>('/simulation/control/', { action, value })
}

/** POST /api/simulation/advance/: run the next stretch now (polled while fast-forwarding). */
export function advanceSimulation(): Promise<SimulationStatus> {
  return apiPost<SimulationStatus>('/simulation/advance/', {})
}

/** POST /api/simulation/tick/: brings the city up to its clock. Any page may call it; it's cheap when too soon. */
export function tickSimulation(): Promise<{ ran: boolean; behind: boolean; mode: string; cityTime: string }> {
  return apiPost('/simulation/tick/', {})
}
