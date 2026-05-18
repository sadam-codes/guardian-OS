import { useCallback, useEffect, useState } from 'react'
import { fetchRegisteredUsers } from '../api/face'
import ActivityLogsPanel from '../components/admin/ActivityLogsPanel'
import AdminShell from '../components/admin/AdminShell'
import DashboardPanel from '../components/admin/DashboardPanel'
import UsersPanel from '../components/admin/UsersPanel'
import { useToast } from '../components/ToastProvider'
import { getSession, logoutToHome, setSession } from '../lib/session'

const ROLE_ADMIN = 'admin'

function getActiveTab() {
  const tab = new URLSearchParams(window.location.search).get('tab')
  return tab === 'users' || tab === 'activity' ? tab : 'dashboard'
}

export default function AdminPage() {
  const session = getSession()
  const activeTab = getActiveTab()
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
    <AdminShell session={session} active={activeTab} onLogout={handleLogout}>
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
    </AdminShell>
  )
}
