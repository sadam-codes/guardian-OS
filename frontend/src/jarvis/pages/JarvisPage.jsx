import { useEffect } from 'react'
import AdminHeader from '../../components/admin/AdminHeader'
import AdminSidebar from '../../components/admin/AdminSidebar'
import PageHeader from '../../components/PageHeader'
import UserSidebar from '../../components/user/UserSidebar'
import { useToast } from '../../components/ToastProvider'
import VoiceConsole from '../components/VoiceConsole'
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

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      {isAdmin ? (
        <AdminHeader session={session} onLogout={handleLogout} />
      ) : (
        <PageHeader
          title="Guardian OS"
          subtitle="Voice assistant"
          session={session}
          onLogout={handleLogout}
        />
      )}

      <div className="flex flex-1 flex-col lg:flex-row">
        {isAdmin ? (
          <AdminSidebar active="jarvis" linkNav onChange={() => {}} />
        ) : (
          <UserSidebar active="jarvis" />
        )}

        <main className="flex-1 overflow-auto p-4 sm:p-6 lg:p-8">
          <div className="mx-auto max-w-2xl">
            <div className="mb-6 lg:hidden">
              <h2 className="text-xl font-bold text-slate-900">Voice assistant</h2>
              <p className="mt-1 text-sm text-slate-500">Speak or type commands to control your PC.</p>
            </div>
            <VoiceConsole userName={session.name} />
          </div>
        </main>
      </div>
    </div>
  )
}
