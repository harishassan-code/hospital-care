import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { loadSession } from '../auth/session'

export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const location = useLocation()
  const session = loadSession()

  if (!session) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  return children
}
