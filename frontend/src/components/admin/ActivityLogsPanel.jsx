import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchActivityLogs } from '../../api/activity'
import AdminSectionHeader from './AdminSectionHeader'

const ROLE_ADMIN = 'admin'
const POLL_MS = 3000

const STATUS_STYLES = {
  success: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  failure: 'bg-red-500/10 text-red-400 border-red-500/20',
  warning: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  info: 'bg-slate-500/10 text-slate-400 border-slate-500/20',
}

export default function ActivityLogsPanel() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [live, setLive] = useState(true)
  const maxIdRef = useRef(0)

  const mergeLogs = useCallback((incoming, initial = false) => {
    if (!incoming.length) return
    setLogs((prev) => {
      const combined = initial ? incoming : [...incoming, ...prev]
      const byId = new Map(combined.map((l) => [l.id, l]))
      return [...byId.values()].sort((a, b) => b.id - a.id).slice(0, 200)
    })
    const newest = Math.max(...incoming.map((l) => l.id))
    if (newest > maxIdRef.current) maxIdRef.current = newest
  }, [])

  const loadInitial = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchActivityLogs(ROLE_ADMIN, { limit: 100 })
      maxIdRef.current = 0
      mergeLogs(data.logs || [], true)
    } catch {
      setLogs([])
    } finally {
      setLoading(false)
    }
  }, [mergeLogs])

  const pollNew = useCallback(async () => {
    try {
      const data = await fetchActivityLogs(ROLE_ADMIN, {
        afterId: maxIdRef.current,
        limit: 50,
      })
      if (data.logs?.length) mergeLogs(data.logs)
    } catch {
      /* keep polling */
    }
  }, [mergeLogs])

  useEffect(() => {
    loadInitial()
  }, [loadInitial])

  useEffect(() => {
    if (!live) return undefined
    const id = setInterval(pollNew, POLL_MS)
    return () => clearInterval(id)
  }, [live, pollNew])

  return (
    <div className="space-y-6">
      <AdminSectionHeader
        title="Activity logs"
        subtitle="Live monitoring of sign-ins, enrollments, and admin actions."
        actions={
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setLive((v) => !v)}
              className={`cursor-pointer rounded-lg px-3 py-1.5 text-xs font-semibold ${
                live
                  ? 'bg-emerald-500/15 text-emerald-400'
                  : 'bg-white/5 text-slate-400'
              }`}
            >
              {live ? '● Live' : 'Paused'}
            </button>
            <button
              type="button"
              onClick={loadInitial}
              className="cursor-pointer rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-white/10"
            >
              Refresh
            </button>
          </div>
        }
      />

      <div className="overflow-hidden rounded-2xl border border-white/[0.08] bg-[#121820]">
        {loading ? (
          <p className="p-8 text-center text-sm text-slate-500">Loading activity…</p>
        ) : logs.length === 0 ? (
          <p className="p-8 text-center text-sm text-slate-500">No activity recorded yet.</p>
        ) : (
          <ul className="max-h-[calc(100vh-14rem)] divide-y divide-white/[0.06] overflow-y-auto">
            {logs.map((log) => (
              <li key={log.id} className="flex gap-4 px-4 py-3 hover:bg-white/[0.02]">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`rounded-full border px-2 py-0.5 text-xs font-semibold capitalize ${
                        STATUS_STYLES[log.status] || STATUS_STYLES.info
                      }`}
                    >
                      {log.status}
                    </span>
                    <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
                      {formatEventType(log.event_type)}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-slate-200">{log.message}</p>
                  {(log.actor_name || log.target_name) && (
                    <p className="mt-0.5 text-xs text-slate-500">
                      {log.actor_name && <span>By {log.actor_name}</span>}
                      {log.actor_name && log.target_name && ' · '}
                      {log.target_name && <span>Target: {log.target_name}</span>}
                    </p>
                  )}
                </div>
                <time className="shrink-0 text-xs text-slate-500">{formatTime(log.created_at)}</time>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

function formatEventType(type) {
  return type.replace(/_/g, ' ')
}

function formatTime(iso) {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return iso
  }
}
