import { BrowserRouter, Route, Routes } from 'react-router-dom'
import StaffLayout from './features/staff/StaffLayout'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import NotFoundPage from './pages/NotFoundPage'
import SignupPage from './pages/SignupPage'
import BedsPage from './pages/staff/BedsPage'
import BloodPage from './pages/staff/BloodPage'
import OverviewPage from './pages/staff/OverviewPage'
import PharmacyPage from './pages/staff/PharmacyPage'

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/staff" element={<StaffLayout />}>
        <Route index element={<OverviewPage />} />
        <Route path="beds" element={<BedsPage />} />
        <Route path="blood" element={<BloodPage />} />
        <Route path="pharmacy" element={<PharmacyPage />} />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}
