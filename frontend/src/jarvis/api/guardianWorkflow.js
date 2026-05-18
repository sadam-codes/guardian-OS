const API_BASE = import.meta.env.VITE_API_URL || '/api'

async function parseError(response) {
  const data = await response.json().catch(() => ({}))
  const detail = data.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join(', ')
  return 'Guardian workflow failed.'
}

export async function fetchGuardianStatus() {
  const res = await fetch(`${API_BASE}/guardian/status`)
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function executeGuardianWorkflow({
  text,
  userId,
  userName,
  identityVerified,
  gesture,
  context,
  plan,
}) {
  const res = await fetch(`${API_BASE}/guardian/workflow/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      text: text || '',
      user_id: userId ?? null,
      user_name: userName || null,
      identity_verified: Boolean(identityVerified),
      gesture: gesture || null,
      context: context?.active ? context : null,
      planned_steps: plan?.planned_steps ?? null,
      understood: plan?.understood ?? null,
      jarvis_brief: plan?.jarvis_brief ?? null,
    }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function fetchGuardianEvents(limit = 30) {
  const res = await fetch(`${API_BASE}/guardian/events?limit=${limit}`)
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function fetchFrequentCommands(userId, userName) {
  const params = new URLSearchParams()
  if (userId != null) params.set('user_id', String(userId))
  if (userName) params.set('user_name', userName)
  const res = await fetch(`${API_BASE}/guardian/memory/frequent?${params}`)
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}
