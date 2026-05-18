const API_BASE = import.meta.env.VITE_API_URL || '/api'

async function parseError(response) {
  const data = await response.json().catch(() => ({}))
  const detail = data.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join(', ')
  return 'Command failed.'
}

export async function planJarvisCommand(text, userName, context = null) {
  const res = await fetch(`${API_BASE}/jarvis/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      text,
      user_name: userName || null,
      context: context?.active ? context : null,
    }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function sendJarvisCommand(text, userName, context = null, plan = null) {
  const res = await fetch(`${API_BASE}/jarvis/command`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      text,
      user_name: userName || null,
      context: context?.active ? context : null,
      planned_steps: plan?.planned_steps ?? null,
      understood: plan?.understood ?? null,
      jarvis_brief: plan?.jarvis_brief ?? null,
    }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function fetchJarvisCapabilities() {
  const res = await fetch(`${API_BASE}/jarvis/capabilities`)
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

/** Recorded mic audio → Groq Whisper text (reliable vs browser SpeechRecognition). */
export async function transcribeJarvisAudio(blob) {
  const form = new FormData()
  const name = blob.type?.includes('webm') ? 'voice.webm' : 'voice.bin'
  form.append('file', blob, name)
  const res = await fetch(`${API_BASE}/jarvis/transcribe`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}
