import { useCallback, useEffect, useState } from 'react'
import { fetchActivityLogs, fetchActivitySummary } from '../../api/activity'
import AdminSectionHeader from './AdminSectionHeader'

const ROLE_ADMIN = 'admin'

export default function DashboardPanel() {
  const [summary, setSummary] = useState(null)
  const [recent, setRecent] = useState([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [sum, logsRes] = await Promise.all([
        fetchActivitySummary(ROLE_ADMIN),
        fetchActivityLogs(ROLE_ADMIN, { limit: 8 }),
      ])
      setSummary(sum)
      setRecent(logsRes.logs || [])
    } catch {
      setSummary(null)
      setRecent([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const id = setInterval(load, 10000)
    return () => clearInterval(id)
  }, [load])

  const stats = [
    { label: 'Total users', value: summary?.total_users ?? 0 },
    { label: 'Administrators', value: summary?.admin_count ?? 0 },
    { label: 'Regular users', value: summary?.user_count ?? 0 },
    { label: 'System events', value: summary?.total_events ?? 0 },
  ]

  return (
    <div className="space-y-6">
      <AdminSectionHeader
        title="Dashboard"
        subtitle="Overview of Guardian OS activity and users."
      />

      {loading && !summary ? (
        <p className="text-sm text-slate-500">Loading dashboard…</p>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {stats.map((s) => (
              <div
                key={s.label}
                className="rounded-2xl border border-white/[0.08] bg-[#121820] p-5"
              >
                <p className="text-sm font-medium text-slate-400">{s.label}</p>
                <p className="mt-2 text-3xl font-bold text-white">{s.value}</p>
              </div>
            ))}
          </div>

          <div className="rounded-2xl border border-white/[0.08] bg-[#121820] p-6">
            <h3 className="text-sm font-semibold text-slate-200">Recent activity</h3>
            {recent.length === 0 ? (
              <p className="mt-4 text-sm text-slate-500">No events yet.</p>
            ) : (
              <ul className="mt-4 space-y-3">
                {recent.map((log) => (
                  <li key={log.id} className="flex items-start justify-between gap-4 text-sm">
                    <span className="text-slate-300">{log.message}</span>
                    <span className="shrink-0 text-xs text-slate-500">
                      {new Date(log.created_at).toLocaleTimeString()}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  )
}
