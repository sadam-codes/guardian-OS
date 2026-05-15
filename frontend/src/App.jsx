import AdminPage from './pages/AdminPage'
import HomePage from './pages/HomePage'
import JarvisPage from './jarvis/pages/JarvisPage'
import UserPage from './pages/UserPage'

function resolvePage() {
  const path = window.location.pathname
  if (path === '/admin' || path.startsWith('/admin/')) {
    return <AdminPage />
  }
  if (path === '/user' || path.startsWith('/user/')) {
    return <UserPage />
  }
  if (path === '/jarvis' || path.startsWith('/jarvis/')) {
    return <JarvisPage />
  }
  return <HomePage />
}

export default function App() {
  return resolvePage()
}
