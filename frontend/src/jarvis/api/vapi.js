const API_BASE = import.meta.env.VITE_API_URL || '/api'

export async function fetchVapiDiagnose() {
  const res = await fetch(`${API_BASE}/vapi/diagnose`)
  if (!res.ok) throw new Error('Could not load Vapi diagnose')
  return res.json()
}
