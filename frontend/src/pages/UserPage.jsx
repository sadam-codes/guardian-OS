import { useEffect } from 'react'
import UserAppShell from '../components/user/UserAppShell'
import UserHomeDashboard from '../components/user/UserHomeDashboard'
import { useToast } from '../components/ToastProvider'
import { getSession, logoutToHome } from '../lib/session'

const ROLE_USER = 'user'

export default function UserPage() {
  const toast = useToast()
  const session = getSession()

  useEffect(() => {
    if (!session) {
      window.location.href = '/'
      return
    }
    if (session.role === 'admin') {
      window.location.href = '/admin'
    }
  }, [session])

  if (!session || session.role !== ROLE_USER) {
    return null
  }

  const handleLogout = () => {
    const name = session.name
    logoutToHome()
    toast.success(name ? `Logged out. See you soon, ${name}.` : 'Logged out successfully.')
  }

  return (
    <UserAppShell session={session} active="home" onLogout={handleLogout}>
      <UserHomeDashboard session={session} />
    </UserAppShell>
  )
}
