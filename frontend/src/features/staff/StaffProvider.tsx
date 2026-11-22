import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { getMe, logout, type User } from '../../api/auth'
import { getBedBoard, postBedAction, type BedAction, type BedBoard } from '../../api/beds'
import { getBloodUnits, type BloodUnit } from '../../api/blood'
import { ApiError } from '../../api/client'
import { getCases } from '../../api/emergencies'
import { getMedicines } from '../../api/pharmacy'
import { getPublicStatus } from '../../api/publicStatus'
import { listTransfers } from '../../api/transfers'
import { useNotificationFeed } from '../notifications/useNotificationFeed'
import { useNow } from '../../lib/useNow'
import { buildAttention } from './attention'
import { canSee, type Role } from './roles'
import { SessionScreen } from './SessionScreen'
import { StaffContext, type BedActionResult, type StaffData, type StaffState } from './staffContext'

type Session = { state: 'checking' } | { state: 'unavailable' } | { state: 'patient' } | { state: 'staff'; user: User }

const NO_BEDS: BedBoard = { wards: [], beds: [] }

/** How often the staff workspace reloads what it shows (B08). */
const REFRESH_MS = 30_000

/**
 * Gate for the staff workspace: asks the server who is signed in, sends signed-out visitors to the
 * login page (remembering where they were going), and turns patients away. Staff get the workspace.
 */
export function StaffProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const requestedPath = useRef(pathname)
  const [session, setSession] = useState<Session>({ state: 'checking' })

  useEffect(() => {
    let active = true
    getMe()
      .then((user) => {
        if (!active) return
        if (!user) navigate(`/login?next=${encodeURIComponent(requestedPath.current)}`, { replace: true })
        else setSession(user.isStaff ? { state: 'staff', user } : { state: 'patient' })
      })
      .catch(() => active && setSession({ state: 'unavailable' }))
    return () => {
      active = false
    }
  }, [navigate])

  switch (session.state) {
    case 'checking':
      return <SessionScreen title="Checking your sign-in…" />
    case 'unavailable':
      return (
        <SessionScreen title="Can’t reach the hospital’s system">
          The hospital’s system didn’t respond. Check your connection and reload the page.
        </SessionScreen>
      )
    case 'patient':
      return (
        <SessionScreen title="This area is for hospital staff" homeLink>
          You’re signed in with a patient account. Staff accounts are set up by your hospital administrator.
        </SessionScreen>
      )
    case 'staff':
      return <StaffSession user={session.user}>{children}</StaffSession>
  }
}

/**
 * Every call the role's workspace makes, answered together. A call that fails leaves its part undefined. Null when a call
 * the pages can't do without (beds, blood, pharmacy) failed. `complete` is false when an optional call (the public ER
 * status, cases, transfers) failed.
 */
async function loadStaffData(role: Role): Promise<{ data: StaffData; complete: boolean } | null> {
  const attempt = <T,>(request: Promise<T>) => request.catch(() => undefined)
  const [board, units, medicines, emergency, cases, transfers] = await Promise.all([
    canSee(role, 'beds') ? attempt(getBedBoard()) : NO_BEDS,
    canSee(role, 'blood') ? attempt(getBloodUnits()) : [],
    canSee(role, 'pharmacy') ? attempt(getMedicines()) : [],
    attempt(getPublicStatus().then((status) => status.emergency)),
    canSee(role, 'emergencies') ? attempt(getCases()) : null,
    canSee(role, 'transfers')
      ? attempt(
          Promise.all([listTransfers({ direction: 'incoming' }), listTransfers({ direction: 'outgoing' })]).then(
            ([incoming, outgoing]) => ({ incoming, outgoing }),
          ),
        )
      : null,
  ])
  if (board === undefined || units === undefined || medicines === undefined) return null
  return {
    complete: emergency !== undefined && cases !== undefined && transfers !== undefined,
    data: {
      wards: board.wards,
      beds: board.beds,
      units,
      medicines,
      emergency: emergency ?? null,
      cases: cases ?? null,
      transfers: transfers ?? null,
    },
  }
}

type Load = { data: StaffData | null; failed: boolean; updatedAt: Date | null; refreshFailed: boolean }

/**
 * Loads what this role may see, keeps it here so every page and the bell share it, and reloads it every 30 seconds.
 * A reload is skipped while the tab is hidden or another reload is running. A reload that fails keeps the data on
 * screen; the next one tries again.
 */
function StaffSession({ user, children }: { user: User; children: ReactNode }) {
  const role = user.role as Role
  const now = useNow()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [load, setLoad] = useState<Load>({ data: null, failed: false, updatedAt: null, refreshFailed: false })
  const { data, failed, updatedAt, refreshFailed } = load
  const reloading = useRef(false)
  const notifications = useNotificationFeed()

  const reload = useCallback(async () => {
    if (reloading.current) return
    reloading.current = true
    try {
      const result = await loadStaffData(role)
      const at = new Date()
      setLoad((current) => {
        if (!result) return current.data ? { ...current, refreshFailed: true } : { ...current, failed: true }
        if (!result.complete && current.data) return { ...current, refreshFailed: true }
        return { data: result.data, failed: false, updatedAt: at, refreshFailed: false }
      })
    } finally {
      reloading.current = false
    }
  }, [role])

  useEffect(() => {
    void reload()
    const tick = setInterval(() => {
      if (document.visibilityState !== 'hidden') void reload()
    }, REFRESH_MS)
    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') void reload()
    }
    document.addEventListener('visibilitychange', onVisibilityChange)
    return () => {
      clearInterval(tick)
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [reload])

  const setData = useCallback((update: (current: StaffData) => StaffData) => {
    setLoad((current) => (current.data ? { ...current, data: update(current.data) } : current))
  }, [])

  const updateBed = useCallback(
    async (bedId: string, action: BedAction): Promise<BedActionResult> => {
      try {
        const saved = await postBedAction(bedId, action)
        setData((current) => ({ ...current, beds: current.beds.map((b) => (b.id === saved.id ? saved : b)) }))
        return { ok: true }
      } catch (error) {
        const status = error instanceof ApiError ? error.status : 0
        if (status === 409) {
          const board = await getBedBoard().catch(() => null)
          if (board) setData((current) => ({ ...current, ...board }))
          return { ok: false, message: 'Someone else changed this bed first. The board now shows its latest state.' }
        }
        if (status === 403) {
          const me = await getMe().catch(() => user)
          if (!me) {
            navigate(`/login?next=${encodeURIComponent(pathname)}`)
            return { ok: false, message: 'Your sign-in has ended. Sign in again to continue.' }
          }
          return { ok: false, message: 'Your role can’t change bed status.' }
        }
        return { ok: false, message: 'The hospital’s system didn’t respond, so the bed wasn’t changed. Try again.' }
      }
    },
    [navigate, pathname, setData, user],
  )

  const signOut = useCallback(async () => {
    await logout().catch(() => undefined)
    navigate('/login')
  }, [navigate])

  const upsertUnit = useCallback(
    (unit: BloodUnit) => {
      setData((current) => ({
        ...current,
        units: current.units.some((u) => u.id === unit.id)
          ? current.units.map((u) => (u.id === unit.id ? unit : u))
          : [...current.units, unit],
      }))
    },
    [setData],
  )

  const refreshUnits = useCallback(async () => {
    const units = await getBloodUnits().catch(() => null)
    if (units) setData((current) => ({ ...current, units }))
  }, [setData])

  const attention = useMemo(
    () => (data ? buildAttention(data, now).filter((item) => canSee(role, item.module)) : []),
    [data, now, role],
  )

  const value = useMemo<StaffState>(
    () => ({ user, role, now, data, failed, updatedAt, refreshFailed, attention, notifications, updateBed, upsertUnit, refreshUnits, signOut }),
    [user, role, now, data, failed, updatedAt, refreshFailed, attention, notifications, updateBed, upsertUnit, refreshUnits, signOut],
  )

  return <StaffContext.Provider value={value}>{children}</StaffContext.Provider>
}
