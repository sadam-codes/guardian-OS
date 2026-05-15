const API_BASE = import.meta.env.VITE_API_URL || '/api'

async function parseError(response) {
  const data = await response.json().catch(() => ({}))
  const detail = data.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join(', ')
  return 'Command failed.'
}

export async function sendJarvisCommand(text, userName) {
  const res = await fetch(`${API_BASE}/jarvis/command`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, user_name: userName || null }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function fetchJarvisCapabilities() {
  const res = await fetch(`${API_BASE}/jarvis/capabilities`)
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}
