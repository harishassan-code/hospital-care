import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { getBedBoard } from '../../api/beds'
import { getBloodUnits } from '../../api/blood'
import { getMedicines } from '../../api/pharmacy'
import { getPublicStatus } from '../../api/publicStatus'
import { useNow } from '../../lib/useNow'
import { applyAction, type BedAction } from '../beds/beds'
import { buildAttention } from './attention'
import { canSee, type Role } from './roles'
import { StaffContext, type StaffData, type StaffState } from './staffContext'

/**
 * Loads everything the staff pages need once and keeps it here, so a change on one page
 * (a bed discharged) is reflected everywhere (the overview, the bell) without refetching.
 */
export function StaffProvider({ children }: { children: ReactNode }) {
  const now = useNow()
  const [role, setRole] = useState<Role>('admin')
  const [data, setData] = useState<StaffData | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let active = true
    const loadedAt = new Date()
    Promise.all([getBedBoard(loadedAt), getBloodUnits(loadedAt), getMedicines(loadedAt), getPublicStatus()])
      .then(([board, units, medicines, status]) => {
        if (active) setData({ ...board, units, medicines, emergency: status.emergency })
      })
      .catch(() => active && setFailed(true))
    return () => {
      active = false
    }
  }, [])

  const updateBed = useCallback((bedId: string, action: BedAction) => {
    setData((current) =>
      current && {
        ...current,
        beds: current.beds.map((bed) => (bed.id === bedId ? applyAction(bed, action, new Date()) : bed)),
      },
    )
  }, [])

  const attention = useMemo(
    () => (data ? buildAttention(data, now).filter((item) => canSee(role, item.module)) : []),
    [data, now, role],
  )

  const value = useMemo<StaffState>(
    () => ({ role, setRole, now, data, failed, attention, updateBed }),
    [role, now, data, failed, attention, updateBed],
  )

  return <StaffContext.Provider value={value}>{children}</StaffContext.Provider>
}
