import { useEffect } from 'react'
import AdminHeader from '../../components/admin/AdminHeader'
import AdminSidebar from '../../components/admin/AdminSidebar'
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
      <div className="flex min-h-screen flex-col bg-[#0b1018] text-slate-200">
        <AdminHeader session={session} onLogout={handleLogout} />
        <div className="flex flex-1 flex-col lg:flex-row">
          <AdminSidebar active="jarvis" linkNav onChange={() => {}} />
          <main className="flex-1 overflow-auto p-4 sm:p-5">
            <GuardianWorkflowDashboard session={session} />
          </main>
        </div>
      </div>
    )
  }

  return (
    <UserAppShell session={session} active="jarvis" onLogout={handleLogout}>
      <GuardianWorkflowDashboard session={session} />
    </UserAppShell>
  )
}
