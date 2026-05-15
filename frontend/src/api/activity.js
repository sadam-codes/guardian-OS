const API_BASE = import.meta.env.VITE_API_URL || '/api'

async function parseError(response) {
  const data = await response.json().catch(() => ({}))
  const detail = data.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join(', ')
  return 'Something went wrong. Please try again.'
}

export async function fetchActivityLogs(actorRole, { afterId = null, limit = 100 } = {}) {
  const params = new URLSearchParams({ actor_role: actorRole, limit: String(limit) })
  if (afterId != null) params.append('after_id', String(afterId))

  const res = await fetch(`${API_BASE}/activity/logs?${params}`)
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function fetchActivitySummary(actorRole) {
  const params = new URLSearchParams({ actor_role: actorRole })
  const res = await fetch(`${API_BASE}/activity/summary?${params}`)
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}
