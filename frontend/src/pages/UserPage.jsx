import { useEffect } from 'react'
import PageHeader from '../components/PageHeader'
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
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100">
      <PageHeader
        title="Guardian OS"
        subtitle="User portal"
        session={session}
        onLogout={handleLogout}
      />

      <main className="mx-auto max-w-xl px-4 py-8 sm:px-6 sm:py-10">
        <div className="rounded-2xl border border-emerald-100 bg-gradient-to-br from-emerald-50 to-white p-8 text-center shadow-sm">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100">
            <svg className="h-8 w-8 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-slate-900">Welcome, {session.name}</h2>
          <p className="mt-2 text-slate-600">
            You are signed in. Your face was recognized and you were brought here automatically.
          </p>
        </div>
      </main>
    </div>
  )
}
