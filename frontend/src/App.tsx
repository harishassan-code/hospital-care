import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { PLANNED } from './features/staff/planned'
import StaffLayout from './features/staff/StaffLayout'
import HospitalPublicPage from './pages/HospitalPublicPage'
import PrivacyPage from './pages/PrivacyPage'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import NotFoundPage from './pages/NotFoundPage'
import SignupPage from './pages/SignupPage'
import AlertsPage from './pages/staff/AlertsPage'
import BedsPage from './pages/staff/BedsPage'
import AuditPage from './pages/staff/AuditPage'
import BloodPage from './pages/staff/BloodPage'
import CommandCentrePage from './pages/staff/CommandCentrePage'
import DonorsPage from './pages/staff/DonorsPage'
import EmergenciesPage from './pages/staff/EmergenciesPage'
import AmbulancesPage from './pages/staff/AmbulancesPage'
import EmergencyFeedPage from './pages/staff/EmergencyFeedPage'
import EmergencyCasePage from './pages/staff/EmergencyCasePage'
import HospitalDetailPage from './pages/staff/HospitalDetailPage'
import HospitalFormPage from './pages/staff/HospitalFormPage'
import HospitalsPage from './pages/staff/HospitalsPage'
import OverviewPage from './pages/staff/OverviewPage'
import EquipmentPage from './pages/staff/EquipmentPage'
import OperatingRoomSchedulePage from './pages/staff/OperatingRoomSchedulePage'
import OperatingRoomsPage from './pages/staff/OperatingRoomsPage'
import PharmacyPage from './pages/staff/PharmacyPage'
import PlannedPage from './pages/staff/PlannedPage'
import ReportsPage from './pages/staff/ReportsPage'
import SimulationPage from './pages/staff/SimulationPage'
import EmergencyDepartmentPage from './pages/staff/EmergencyDepartmentPage'
import StaffingPage from './pages/staff/StaffingPage'
import { CityTicker } from './features/simulation/CityTicker'
import SpecialistDetailPage from './pages/staff/SpecialistDetailPage'
import SpecialistFormPage from './pages/staff/SpecialistFormPage'
import SpecialistsPage from './pages/staff/SpecialistsPage'
import TransfersPage from './pages/staff/TransfersPage'
import UsersPage from './pages/staff/UsersPage'

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/hospitals/:id" element={<HospitalPublicPage />} />
      <Route path="/privacy" element={<PrivacyPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/staff" element={<StaffLayout />}>
        <Route index element={<OverviewPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="command-centre" element={<CommandCentrePage />} />
        <Route path="emergency-department" element={<EmergencyDepartmentPage />} />
        <Route path="emergencies" element={<EmergenciesPage />} />
        <Route path="emergencies/feed" element={<EmergencyFeedPage />} />
        <Route path="emergencies/:reference" element={<EmergencyCasePage />} />
        <Route path="transfers" element={<TransfersPage />} />
        <Route path="beds" element={<BedsPage />} />
        <Route path="blood" element={<BloodPage />} />
        <Route path="donors" element={<DonorsPage />} />
        <Route path="pharmacy" element={<PharmacyPage />} />
        <Route path="equipment" element={<EquipmentPage />} />
        <Route path="ambulances" element={<AmbulancesPage />} />
        <Route path="operating-rooms" element={<OperatingRoomsPage />} />
        <Route path="operating-rooms/schedule" element={<OperatingRoomSchedulePage />} />
        <Route path="staffing" element={<StaffingPage />} />
        <Route path="hospitals" element={<HospitalsPage />} />
        <Route path="hospitals/new" element={<HospitalFormPage />} />
        <Route path="hospitals/:id" element={<HospitalDetailPage />} />
        <Route path="hospitals/:id/edit" element={<HospitalFormPage />} />
        <Route path="specialists" element={<SpecialistsPage />} />
        <Route path="specialists/new" element={<SpecialistFormPage />} />
        <Route path="specialists/:id" element={<SpecialistDetailPage />} />
        <Route path="specialists/:id/edit" element={<SpecialistFormPage />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="audit" element={<AuditPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="simulation" element={<SimulationPage />} />
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
      <CityTicker />
      <AppRoutes />
    </BrowserRouter>
  )
}
