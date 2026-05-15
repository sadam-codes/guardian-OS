const API_BASE = import.meta.env.VITE_API_URL || '/api'
const REQUEST_TIMEOUT_MS = 15000

async function parseError(response) {
  const data = await response.json().catch(() => ({}))
  const detail = data.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join(', ')
  return 'Something went wrong. Please try again.'
}

async function fetchWithTimeout(url, options = {}) {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  try {
    return await fetch(url, { ...options, signal: controller.signal })
  } catch (err) {
    if (err.name === 'AbortError') {
      throw new Error('Request timed out. Check your connection and try again.')
    }
    throw err
  } finally {
    clearTimeout(timeout)
  }
}

function appendImages(form, imageFiles) {
  const files = Array.isArray(imageFiles) ? imageFiles : [imageFiles]
  files.forEach((file, index) => {
    form.append('images', file, file.name || `face-${index}.jpg`)
  })
}

function appendEyeEncodings(form, eyeEncodingsList) {
  form.append('eye_encodings', JSON.stringify(eyeEncodingsList))
}

export async function faceSignup(name, imageFiles, eyeEncodings, role = 'user', actorRole = null) {
  const form = new FormData()
  form.append('name', name.trim())
  appendImages(form, imageFiles)
  appendEyeEncodings(form, eyeEncodings)
  form.append('role', role)
  if (actorRole) form.append('actor_role', actorRole)

  const res = await fetchWithTimeout(`${API_BASE}/face/signup`, {
    method: 'POST',
    body: form,
  })

  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function faceLogin(imageFiles, eyeEncodings) {
  const form = new FormData()
  appendImages(form, imageFiles)
  appendEyeEncodings(form, eyeEncodings)

  const res = await fetchWithTimeout(`${API_BASE}/face/login`, {
    method: 'POST',
    body: form,
  })

  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function fetchRegisteredUsers() {
  const res = await fetch(`${API_BASE}/face/users`)
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function updateUser(userId, { name, role, imageFile }, actorRole, actorName = null) {
  const form = new FormData()
  form.append('actor_role', actorRole)
  if (actorName) form.append('actor_name', actorName)
  if (name != null) form.append('name', name.trim())
  if (role != null) form.append('role', role)
  if (imageFile) form.append('image', imageFile, imageFile.name || 'face.jpg')

  const res = await fetch(`${API_BASE}/face/users/${userId}`, {
    method: 'PUT',
    body: form,
  })

  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function deleteUser(userId, actorRole, actorUserId = null) {
  const params = new URLSearchParams({ actor_role: actorRole })
  if (actorUserId != null) params.append('actor_user_id', String(actorUserId))

  const res = await fetch(`${API_BASE}/face/users/${userId}?${params}`, {
    method: 'DELETE',
  })

  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}
