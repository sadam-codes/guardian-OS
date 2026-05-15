const ROLE_ADMIN = 'admin'

export default function RoleBadge({ role }) {
  const isAdmin = role === ROLE_ADMIN
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${
        isAdmin ? 'bg-violet-100 text-violet-700' : 'bg-slate-100 text-slate-600'
      }`}
    >
      {isAdmin ? 'Admin' : 'User'}
    </span>
  )
}
