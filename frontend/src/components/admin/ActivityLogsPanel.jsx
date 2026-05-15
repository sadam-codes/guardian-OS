import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchActivityLogs } from '../../api/activity'

const ROLE_ADMIN = 'admin'
const POLL_MS = 3000

const STATUS_STYLES = {
  success: 'bg-emerald-50 text-emerald-700 border-emerald-100',
  failure: 'bg-red-50 text-red-700 border-red-100',
  warning: 'bg-amber-50 text-amber-700 border-amber-100',
  info: 'bg-slate-50 text-slate-600 border-slate-100',
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
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Activity logs</h2>
          <p className="mt-1 text-sm text-slate-500">
            Live monitoring of sign-ins, enrollments, and admin actions.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setLive((v) => !v)}
            className={`cursor-pointer rounded-lg px-3 py-1.5 text-xs font-semibold ${
              live ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-600'
            }`}
          >
            {live ? '● Live' : 'Paused'}
          </button>
          <button
            type="button"
            onClick={loadInitial}
            className="cursor-pointer rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        {loading ? (
          <p className="p-8 text-center text-sm text-slate-500">Loading activity…</p>
        ) : logs.length === 0 ? (
          <p className="p-8 text-center text-sm text-slate-500">No activity recorded yet.</p>
        ) : (
          <ul className="max-h-[calc(100vh-14rem)] divide-y divide-slate-100 overflow-y-auto">
            {logs.map((log) => (
              <li key={log.id} className="flex gap-4 px-4 py-3 hover:bg-slate-50/80">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`rounded-full border px-2 py-0.5 text-xs font-semibold capitalize ${
                        STATUS_STYLES[log.status] || STATUS_STYLES.info
                      }`}
                    >
                      {log.status}
                    </span>
                    <span className="text-xs font-medium uppercase tracking-wide text-slate-400">
                      {formatEventType(log.event_type)}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-slate-800">{log.message}</p>
                  {(log.actor_name || log.target_name) && (
                    <p className="mt-0.5 text-xs text-slate-500">
                      {log.actor_name && <span>By {log.actor_name}</span>}
                      {log.actor_name && log.target_name && ' · '}
                      {log.target_name && <span>Target: {log.target_name}</span>}
                    </p>
                  )}
                </div>
                <time className="shrink-0 text-xs text-slate-400">{formatTime(log.created_at)}</time>
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
