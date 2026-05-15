const API_BASE = import.meta.env.VITE_API_URL || '/api'

async function parseError(response) {
  const data = await response.json().catch(() => ({}))
  const detail = data.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join(', ')
  return 'Something went wrong. Please try again.'
}

export async function faceSignup(name, imageFile, role = 'user', actorRole = null) {
  const form = new FormData()
  form.append('name', name.trim())
  form.append('image', imageFile, imageFile.name || 'capture.jpg')
  form.append('role', role)
  if (actorRole) form.append('actor_role', actorRole)

  const res = await fetch(`${API_BASE}/face/signup`, {
    method: 'POST',
    body: form,
  })

  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function faceLogin(imageFile) {
  const form = new FormData()
  form.append('image', imageFile, imageFile.name || 'capture.jpg')

  const res = await fetch(`${API_BASE}/face/login`, {
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

export async function deleteUser(userId, actorRole, actorName = null) {
  const params = new URLSearchParams({ actor_role: actorRole })
  if (actorName) params.append('actor_name', actorName)

  const res = await fetch(`${API_BASE}/face/users/${userId}?${params}`, {
    method: 'DELETE',
  })

  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}
