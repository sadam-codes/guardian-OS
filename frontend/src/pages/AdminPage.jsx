import { useCallback, useEffect, useState } from 'react'
import { fetchRegisteredUsers } from '../api/face'
import ActivityLogsPanel from '../components/admin/ActivityLogsPanel'
import AdminSidebar from '../components/admin/AdminSidebar'
import DashboardPanel from '../components/admin/DashboardPanel'
import UsersPanel from '../components/admin/UsersPanel'
import AdminHeader from '../components/admin/AdminHeader'
import { useToast } from '../components/ToastProvider'
import { getSession, logoutToHome, setSession } from '../lib/session'

const ROLE_ADMIN = 'admin'

export default function AdminPage() {
  const session = getSession()
  const [activeTab, setActiveTab] = useState(() => {
    const tab = new URLSearchParams(window.location.search).get('tab')
    return tab === 'users' || tab === 'activity' ? tab : 'dashboard'
  })
  const [users, setUsers] = useState([])
  const toast = useToast()

  const isAuthed = session?.role === ROLE_ADMIN

  useEffect(() => {
    if (!isAuthed) {
      window.location.href = '/'
    }
  }, [isAuthed])

  const loadUsers = useCallback(async () => {
    try {
      const data = await fetchRegisteredUsers()
      setUsers(data.users || [])
    } catch {
      setUsers([])
    }
  }, [])

  useEffect(() => {
    if (isAuthed) loadUsers()
  }, [isAuthed, loadUsers])

  const handleLogout = () => {
    logoutToHome()
    toast.success('Logged out successfully.')
  }

  if (!isAuthed) {
    return null
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <AdminHeader session={session} onLogout={handleLogout} />

      <div className="flex flex-1 flex-col lg:flex-row">
        <AdminSidebar active={activeTab} onChange={setActiveTab} />

        <main className="flex-1 overflow-auto p-4 sm:p-6 lg:p-8">
          {activeTab === 'dashboard' && <DashboardPanel />}
          {activeTab === 'users' && (
            <UsersPanel
              users={users}
              actorName={session?.name}
              currentUserId={session?.id}
              onRefresh={loadUsers}
              onSessionUpdate={(patch) => {
                const current = getSession()
                if (current) setSession({ ...current, ...patch })
              }}
            />
          )}
          {activeTab === 'activity' && <ActivityLogsPanel />}
        </main>
      </div>
    </div>
  )
}
