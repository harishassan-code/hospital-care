import { Link } from 'react-router-dom'

export default function AdminDashboard() {
  return (
    <main data-testid="admin-dashboard" style={{ maxWidth: 960, margin: '0 auto', padding: '32px 16px' }}>
      <h1>Hospital network</h1>
      <nav aria-label="Administrator">
        <Link to="/admin/hospitals/register" data-testid="admin-register-hospital">
          Register Hospital
        </Link>
        <Link to="/admin/users" data-testid="admin-manage-users">
          Manage Users
        </Link>
      </nav>
    </main>
  )
}
