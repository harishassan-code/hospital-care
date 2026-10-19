import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { PLANNED } from './features/staff/planned'
import StaffLayout from './features/staff/StaffLayout'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import NotFoundPage from './pages/NotFoundPage'
import SignupPage from './pages/SignupPage'
import BedsPage from './pages/staff/BedsPage'
import BloodPage from './pages/staff/BloodPage'
import HospitalDetailPage from './pages/staff/HospitalDetailPage'
import HospitalFormPage from './pages/staff/HospitalFormPage'
import HospitalsPage from './pages/staff/HospitalsPage'
import OverviewPage from './pages/staff/OverviewPage'
import PharmacyPage from './pages/staff/PharmacyPage'
import PlannedPage from './pages/staff/PlannedPage'
import UsersPage from './pages/staff/UsersPage'

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
        <Route path="hospitals" element={<HospitalsPage />} />
        <Route path="hospitals/new" element={<HospitalFormPage />} />
        <Route path="hospitals/:id" element={<HospitalDetailPage />} />
        <Route path="hospitals/:id/edit" element={<HospitalFormPage />} />
        <Route path="users" element={<UsersPage />} />
        {PLANNED.map((p) => (
          <Route key={p.path} path={p.path.replace('/staff/', '')} element={<PlannedPage />} />
        ))}
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
