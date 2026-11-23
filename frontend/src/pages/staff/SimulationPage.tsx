import { useEffect, useRef, useState } from 'react'
import {
  advanceSimulation,
  controlSimulation,
  getSimulation,
  type FastForward,
  type SimulationAction,
  type SimulationStatus,
} from '../../api/simulation'
import { fieldErrors } from '../../api/client'
import { FormAlert } from '../../components/form/FormAlert'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { useNow } from '../../lib/useNow'
import { StaffDataState } from './StaffDataState'
import styles from './SimulationPage.module.css'

const REFRESH_MS = 5_000
const FAST_FORWARD_LABEL: Record<FastForward, string> = {
  '30m': '30 minutes',
  '1h': '1 hour',
  '1d': '1 day',
  '1w': '1 week',
  '2w': '2 weeks',
}
const SCENARIO_NOTE: Record<string, string> = {
  regular: 'The everyday rhythm: busy late mornings and evenings, quiet before dawn.',
  flu: 'More arrivals, many with breathing problems; longer stays, fuller wards and more staff off sick.',
  slow: 'Fewer arrivals and planned cases, like a public holiday.',
}
const MODE_LABEL = { real: 'Real time', live: 'Running', paused: 'Paused', fastForward: 'Fast-forwarding' } as const

const dateTime = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Asia/Karachi',
  weekday: 'short',
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
})
const timeOnly = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Karachi', hour: '2-digit', minute: '2-digit' })

function speedLabel(speed: number): string {
  return speed === 0.5 ? '½×' : `${speed}×`
}

function offsetText(minutes: number): string {
  if (Math.abs(minutes) < 2) return 'On the real clock.'
  const abs = Math.abs(minutes)
  const span = abs >= 2880 ? `${Math.round(abs / 1440)} days` : abs >= 120 ? `${Math.round(abs / 60)} hours` : `${abs} minutes`
  return minutes > 0 ? `${span} ahead of the real clock.` : `${span} behind the real clock.`
}

/**
 * The CityCare admin's Simulation panel (B21): the city clock (pause, speed, fast-forward, catch up), the scenario,
 * a mass-casualty event, and what the simulation did lately. Only the admin with no hospital sees it.
 */
export default function SimulationPage() {
  const [status, setStatus] = useState<SimulationStatus | null>(null)
  const [failed, setFailed] = useState(false)
  const [error, setError] = useState('')
  const [pending, setPending] = useState<string | null>(null)
  const advancing = useRef(false)
  const now = useNow(1_000)

  useEffect(() => {
    let active = true
    const load = () =>
      getSimulation()
        .then((next) => {
          if (!active) return
          setStatus(next)
          setFailed(false)
        })
        .catch(() => active && setFailed(true))
    void load()
    const id = setInterval(() => {
      if (document.visibilityState !== 'hidden' && !advancing.current) void load()
    }, REFRESH_MS)
    return () => {
      active = false
      clearInterval(id)
    }
  }, [])

  // While fast-forwarding, keep the engine going: each call runs a few seconds of it and reports progress.
  const fastForwarding = status?.mode === 'fastForward'
  useEffect(() => {
    if (!fastForwarding) return
    let stopped = false
    advancing.current = true
    async function step() {
      while (!stopped) {
        try {
          const next = await advanceSimulation()
          if (stopped) return
          setStatus(next)
          if (next.mode !== 'fastForward') break
        } catch {
          await new Promise((resolve) => setTimeout(resolve, 2_000))
        }
      }
      advancing.current = false
    }
    void step()
    return () => {
      stopped = true
      advancing.current = false
    }
  }, [fastForwarding])

  async function act(action: SimulationAction, value = '') {
    setError('')
    setPending(`${action}:${value}`)
    try {
      setStatus(await controlSimulation(action, value))
    } catch (err) {
      const fields = fieldErrors(err)
      setError(fields.action ?? fields.value ?? fields.detail ?? 'That didn’t work. Try again.')
    } finally {
      setPending(null)
    }
  }

  if (!status) return <StaffDataState failed={failed} />

  const busy = pending !== null
  const ff = status.fastForward

  return (
    <div className={styles.page}>
      <FormAlert>{error}</FormAlert>
      <Panel
        id="clock"
        title="City clock"
        aside={
          <StatusBadge tone={status.mode === 'paused' ? 'warning' : status.mode === 'fastForward' ? 'neutral' : 'ok'}>
            {MODE_LABEL[status.mode]}
            {status.mode === 'live' && status.speed !== 1 ? ` · ${speedLabel(status.speed)}` : ''}
          </StatusBadge>
        }
      >
        <p className={styles.time} aria-live="polite">
          {/* useNow reads the city clock, which every API response sets, and runs on at its speed between them. */}
          <time dateTime={now.toISOString()}>{dateTime.format(now)}</time>
        </p>
        <p className={styles.muted}>
          {offsetText(status.aheadMinutes)} Everything on the site follows this clock; sign-in sessions keep the real one.
        </p>
        <div className={styles.row}>
          {status.paused ? (
            <button type="button" className={styles.primary} disabled={busy || fastForwarding} onClick={() => void act('resume')}>
              Resume
            </button>
          ) : (
            <button type="button" className={styles.primary} disabled={busy || fastForwarding} onClick={() => void act('pause')}>
              Pause
            </button>
          )}
          {status.aheadMinutes <= -2 && (
            <button type="button" className={styles.button} disabled={busy || fastForwarding} onClick={() => void act('catchUp')}>
              Catch up to the real time
            </button>
          )}
        </div>
        <fieldset className={styles.group} disabled={busy || fastForwarding}>
          <legend>Speed</legend>
          <div className={styles.segmented}>
            {status.speeds.map((speed) => (
              <button
                key={speed}
                type="button"
                aria-pressed={status.speed === speed}
                className={styles.segment}
                onClick={() => void act('speed', String(speed))}
              >
                {speed === 1 ? 'Real time (1×)' : speedLabel(speed)}
              </button>
            ))}
          </div>
        </fieldset>
      </Panel>

      <Panel id="fast-forward" title="Fast-forward">
        <p className={styles.muted}>
          The city lives through the time it skips: the last two hours patient by patient, earlier time hour by hour, so
          charts, stock and rotas carry on. A day takes about ten seconds, a week a few minutes.
        </p>
        {ff ? (
          <div className={styles.progressBlock}>
            <div
              className={styles.progress}
              role="progressbar"
              aria-label="Fast-forward"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={ff.percent}
            >
              <span style={{ width: `${ff.percent}%` }} />
            </div>
            <p className={styles.muted}>
              {ff.percent}% · now at {dateTime.format(new Date(ff.progress))}, going to {dateTime.format(new Date(ff.to))}
            </p>
          </div>
        ) : (
          <div className={styles.row}>
            {status.fastForwardOptions.map((option) => (
              <button
                key={option}
                type="button"
                className={styles.button}
                disabled={busy}
                onClick={() => void act('fastForward', option)}
              >
                + {FAST_FORWARD_LABEL[option]}
              </button>
            ))}
          </div>
        )}
      </Panel>

      <Panel id="scenario" title="Scenario">
        <fieldset className={styles.group} disabled={busy}>
          <legend className={styles.srOnly}>Scenario</legend>
          <div className={styles.options}>
            {status.scenarios.map((s) => (
              <label key={s.value} className={styles.option}>
                <input
                  type="radio"
                  name="scenario"
                  value={s.value}
                  checked={status.scenario === s.value}
                  onChange={() => void act('scenario', s.value)}
                />
                <span>
                  <strong>{s.label}</strong>
                  <span className={styles.muted}>{SCENARIO_NOTE[s.value]}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
        <div className={styles.incident}>
          {status.incident ? (
            <>
              <StatusBadge tone="critical">Mass-casualty event</StatusBadge>
              <p>
                Patients are going to {status.incident.hospitals.join(', ')} until {timeOnly.format(new Date(status.incident.until))}.
              </p>
              <button type="button" className={styles.button} disabled={busy} onClick={() => void act('endIncident')}>
                End it now
              </button>
            </>
          ) : (
            <>
              <p className={styles.muted}>
                A mass-casualty event sends waves of injured patients to the three nearest general hospitals for one to three
                hours, with a surge in O-negative and O-positive blood use and emergency theatre cases.
              </p>
              <button type="button" className={styles.danger} disabled={busy} onClick={() => void act('massCasualty')}>
                Set off a mass-casualty event
              </button>
            </>
          )}
        </div>
      </Panel>

      <Panel id="events" title="What happened lately">
        {status.events.length === 0 ? (
          <p className={styles.muted}>Nothing yet. Events appear as the city runs.</p>
        ) : (
          <ol className={styles.events}>
            {status.events.map((e) => (
              <li key={e.id}>
                <time dateTime={e.at}>{dateTime.format(new Date(e.at))}</time>
                <span>{e.message}</span>
              </li>
            ))}
          </ol>
        )}
      </Panel>
    </div>
  )
}

