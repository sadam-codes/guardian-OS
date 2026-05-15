const SESSION_KEY = 'guardian_session'

export function getSession() {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function setSession(session) {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session))
}

export function clearSession() {
  sessionStorage.removeItem(SESSION_KEY)
}

export function redirectForRole(role) {
  if (role === 'admin') {
    window.location.href = '/admin'
  } else {
    window.location.href = '/user'
  }
}

export function logoutToHome() {
  clearSession()
  window.location.href = '/'
}
