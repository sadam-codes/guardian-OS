import { useEffect } from 'react'
import AdminShell from '../../components/admin/AdminShell'
import UserAppShell from '../../components/user/UserAppShell'
import { useToast } from '../../components/ToastProvider'
import GuardianWorkflowDashboard from '../components/GuardianWorkflowDashboard'
import { getSession, logoutToHome } from '../../lib/session'

const ROLE_ADMIN = 'admin'

export default function JarvisPage() {
  const session = getSession()
  const toast = useToast()
  const isAdmin = session?.role === ROLE_ADMIN

  useEffect(() => {
    if (!session) window.location.href = '/'
  }, [session])

  if (!session) return null

  const handleLogout = () => {
    const name = session.name
    logoutToHome()
    toast.success(name ? `Logged out. See you soon, ${name}.` : 'Logged out successfully.')
  }

  if (isAdmin) {
    return (
      <AdminShell session={session} active="jarvis" onLogout={handleLogout}>
        <GuardianWorkflowDashboard session={session} />
      </AdminShell>
    )
  }

  return (
    <UserAppShell session={session} active="jarvis" onLogout={handleLogout}>
      <GuardianWorkflowDashboard session={session} />
    </UserAppShell>
  )
}
