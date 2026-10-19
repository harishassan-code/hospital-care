import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { getMe, logout, type User } from '../../api/auth'
import { getBedBoard, postBedAction, type BedAction, type BedBoard } from '../../api/beds'
import { getBloodUnits } from '../../api/blood'
import { ApiError } from '../../api/client'
import { getMedicines } from '../../api/pharmacy'
import { getPublicStatus } from '../../api/publicStatus'
import { useNow } from '../../lib/useNow'
import { buildAttention } from './attention'
import { canSee, type Role } from './roles'
import { SessionScreen } from './SessionScreen'
import { StaffContext, type BedActionResult, type StaffData, type StaffState } from './staffContext'

type Session = { state: 'checking' } | { state: 'unavailable' } | { state: 'patient' } | { state: 'staff'; user: User }

const NO_BEDS: BedBoard = { wards: [], beds: [] }

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

/** Loads what this role may see once, and keeps it here so every page and the bell share it. */
function StaffSession({ user, children }: { user: User; children: ReactNode }) {
  const role = user.role as Role
  const now = useNow()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [data, setData] = useState<StaffData | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let active = true
    Promise.all([
      canSee(role, 'beds') ? getBedBoard() : NO_BEDS,
      canSee(role, 'blood') ? getBloodUnits() : [],
      canSee(role, 'pharmacy') ? getMedicines() : [],
      getPublicStatus()
        .then((status) => status.emergency)
        .catch(() => null),
    ])
      .then(([board, units, medicines, emergency]) => {
        if (active) setData({ ...board, units, medicines, emergency })
      })
      .catch(() => active && setFailed(true))
    return () => {
      active = false
    }
  }, [role])

  const updateBed = useCallback(
    async (bedId: string, action: BedAction): Promise<BedActionResult> => {
      try {
        const saved = await postBedAction(bedId, action)
        setData((current) => current && { ...current, beds: current.beds.map((b) => (b.id === saved.id ? saved : b)) })
        return { ok: true }
      } catch (error) {
        const status = error instanceof ApiError ? error.status : 0
        if (status === 409) {
          const board = await getBedBoard().catch(() => null)
          if (board) setData((current) => current && { ...current, ...board })
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
    [navigate, pathname, user],
  )

  const signOut = useCallback(async () => {
    await logout().catch(() => undefined)
    navigate('/login')
  }, [navigate])

  const attention = useMemo(
    () => (data ? buildAttention(data, now).filter((item) => canSee(role, item.module)) : []),
    [data, now, role],
  )

  const value = useMemo<StaffState>(
    () => ({ user, role, now, data, failed, attention, updateBed, signOut }),
    [user, role, now, data, failed, attention, updateBed, signOut],
  )

  return <StaffContext.Provider value={value}>{children}</StaffContext.Provider>
}
