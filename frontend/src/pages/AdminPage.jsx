import { useCallback, useEffect, useRef, useState } from 'react'
import { faceSignup, fetchRegisteredUsers } from '../api/face'
import LiveFaceScanner from '../components/LiveFaceScanner'
import PageHeader from '../components/PageHeader'
import UserManagement from '../components/UserManagement'
import { useToast } from '../components/ToastProvider'
import { getSession, logoutToHome } from '../lib/session'

const ROLE_ADMIN = 'admin'
const ROLE_USER = 'user'

export default function AdminPage() {
  const session = getSession()
  const [users, setUsers] = useState([])
  const [showEnroll, setShowEnroll] = useState(false)
  const [enrollName, setEnrollName] = useState('')
  const [enrollRole, setEnrollRole] = useState(ROLE_USER)
  const [scanStatus, setScanStatus] = useState('scanning')
  const [hint, setHint] = useState("Look at the camera to capture the new user's face")
  const enrollBusyRef = useRef(false)
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

  const handleEnrollFrame = useCallback(
    async (file) => {
      if (!enrollName.trim() || enrollBusyRef.current) return
      enrollBusyRef.current = true

      try {
        const data = await faceSignup(enrollName, file, enrollRole, ROLE_ADMIN)
        toast.success(data.message || `Enrolled ${data.name}`)
        setEnrollName('')
        setEnrollRole(ROLE_USER)
        setShowEnroll(false)
        setScanStatus('scanning')
        await loadUsers()
      } catch (err) {
        toast.error(err.message || 'Enrollment failed')
        setScanStatus('error')
        setTimeout(() => setScanStatus('scanning'), 2500)
      } finally {
        enrollBusyRef.current = false
      }
    },
    [enrollName, enrollRole, loadUsers, toast],
  )

  const enrollEnabled = showEnroll && enrollName.trim().length > 0

  if (!isAuthed) {
    return null
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100">
      <PageHeader
        title="Guardian OS Admin"
        subtitle="User management"
        session={session}
        onLogout={handleLogout}
      />

      <main className="mx-auto max-w-4xl px-4 py-8 sm:px-6 sm:py-10">
        <div className="space-y-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-2xl font-bold tracking-tight text-slate-900">User management</h2>
              <p className="mt-1 text-slate-600">Create, edit, and delete registered users.</p>
            </div>
            <button
              type="button"
              onClick={() => {
                setShowEnroll((v) => !v)
                setScanStatus('scanning')
                setHint("Look at the camera to capture the new user's face")
              }}
              className="rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700"
            >
              {showEnroll ? 'Cancel enroll' : 'Add user'}
            </button>
          </div>

          {showEnroll && (
            <Card title="Enroll new user">
              <div className="mb-6 grid gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="enroll-name" className="mb-2 block text-sm font-medium text-slate-700">
                    Full name
                  </label>
                  <input
                    id="enroll-name"
                    type="text"
                    value={enrollName}
                    onChange={(e) => setEnrollName(e.target.value)}
                    placeholder="Enter full name"
                    className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-900 shadow-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20"
                  />
                </div>
                <div>
                  <label htmlFor="enroll-role" className="mb-2 block text-sm font-medium text-slate-700">
                    Role
                  </label>
                  <select
                    id="enroll-role"
                    value={enrollRole}
                    onChange={(e) => setEnrollRole(e.target.value)}
                    className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-900 shadow-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20"
                  >
                    <option value={ROLE_USER}>User</option>
                    <option value={ROLE_ADMIN}>Admin</option>
                  </select>
                </div>
              </div>
              <LiveFaceScanner
                enabled={enrollEnabled}
                paused={false}
                onFrame={handleEnrollFrame}
                status={scanStatus}
                hint={enrollName.trim() ? hint : 'Enter a name first'}
              />
            </Card>
          )}

          <Card title="All users">
            <UserManagement
              users={users}
              actorRole={ROLE_ADMIN}
              actorName={session?.name}
              onRefresh={loadUsers}
            />
          </Card>
        </div>
      </main>
    </div>
  )
}

function Card({ title, children }) {
  return (
    <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-sm shadow-slate-200/50 sm:p-8">
      {title && <h3 className="mb-4 text-sm font-semibold text-slate-900">{title}</h3>}
      {children}
    </div>
  )
}
