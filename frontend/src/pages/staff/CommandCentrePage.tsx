import { useEffect } from 'react'
import { BLOOD_GROUPS } from '../../api/blood'
import { getNetworkSnapshot } from '../../api/commandCentre'
import { Panel } from '../../components/ui/Panel'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { useLoad } from '../../lib/useLoad'
import { StaffDataState } from './StaffDataState'
import pageStyles from './StaffPages.module.css'

const REFRESH_MS = 60_000

/** City command centre (story #55): the whole network on one page, refreshed every minute. */
export default function CommandCentrePage() {
  const { result, setData } = useLoad(getNetworkSnapshot)

  useEffect(() => {
    const timer = setInterval(() => {
      if (document.visibilityState === 'hidden') return
      getNetworkSnapshot()
        .then((fresh) => setData(() => fresh))
        .catch(() => undefined)
    }, REFRESH_MS)
    return () => clearInterval(timer)
  }, [setData])

  if (result.state !== 'ready') return <StaffDataState failed={result.state === 'failed'} />
  const { totals, hospitals, shortages } = result.data

  return (
    <div className={pageStyles.stack}>
      <Panel title="Network">
        <ul aria-label="Network totals">
          <li>{totals.hospitals} hospitals</li>
          <li>{totals.freeBeds} free beds</li>
          <li>{totals.freeIcu} free ICU beds</li>
          <li>{totals.redCells} red-cell units available</li>
          <li>{totals.nearExpiry} units expiring within 3 days</li>
          <li>{totals.activeEmergencies} active emergencies</li>
        </ul>
      </Panel>
      <Panel title="Shortages">
        {shortages.length === 0 ? (
          <p>No shortages anywhere in the network.</p>
        ) : (
          <ul aria-label="Shortages">
            {shortages.map((s, i) => (
              <li key={i}>
                <StatusBadge tone={s.level === 'critical' ? 'critical' : 'warning'}>{s.level}</StatusBadge>{' '}
                {s.kind === 'icu'
                  ? `${s.hospital}: no free ICU bed`
                  : `${s.hospital}: ${s.group} red cells ${s.count} of ${s.minimum} minimum`}
              </li>
            ))}
          </ul>
        )}
      </Panel>
      <Panel title="Hospitals">
        <div className="table-scroll">
          <table aria-label="Hospitals in the network">
            <thead>
              <tr>
                <th scope="col">Hospital</th>
                <th scope="col">Beds free</th>
                <th scope="col">ICU free</th>
                {BLOOD_GROUPS.map((g) => (
                  <th key={g} scope="col">
                    {g}
                  </th>
                ))}
                <th scope="col">Near expiry</th>
                <th scope="col">Equipment free</th>
                <th scope="col">Active emergencies</th>
              </tr>
            </thead>
            <tbody>
              {hospitals.map((h) => (
                <tr key={h.id}>
                  <th scope="row">{h.name}</th>
                  <td>
                    {h.beds.free}/{h.beds.total}
                  </td>
                  <td>{h.icu.total && h.icu.free === 0 ? <StatusBadge tone="critical">0/{h.icu.total}</StatusBadge> : `${h.icu.free}/${h.icu.total}`}</td>
                  {BLOOD_GROUPS.map((g) => (
                    <td key={g}>{h.redCells[g] ?? 0}</td>
                  ))}
                  <td>{h.nearExpiry ? <StatusBadge tone="warning">{h.nearExpiry}</StatusBadge> : 0}</td>
                  <td>
                    {h.equipment.available}/{h.equipment.total}
                  </td>
                  <td>{Object.values(h.emergencies).reduce((a, b) => a + (b ?? 0), 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  )
}
