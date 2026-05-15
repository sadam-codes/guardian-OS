function BrandBlock({ title, subtitle }) {
  return (
    <div className="flex min-w-0 items-center gap-3">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-600 shadow-md shadow-indigo-600/25">
        <ShieldIcon className="h-5 w-5 text-white" />
      </div>
      <div className="min-w-0">
        <h1 className="truncate text-lg font-semibold text-slate-900 sm:text-xl">{title}</h1>
        <p className="truncate text-sm text-slate-500">{subtitle}</p>
      </div>
    </div>
  )
}

function UserActions({ session, onLogout }) {
  if (!session) return null
  return (
    <div className="flex shrink-0 items-center gap-3">
      <span className="text-sm font-medium text-slate-700">{session.name}</span>
      <button
        type="button"
        onClick={onLogout}
        aria-label="Log out"
        title="Log out"
        className="flex h-10 w-10 cursor-pointer items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:border-red-200 hover:bg-red-50 hover:text-red-600"
      >
        <LogoutIcon className="h-5 w-5" />
      </button>
    </div>
  )
}

export default function AdminHeader({ session, onLogout }) {
  return (
    <header className="shrink-0 border-b border-slate-200/80 bg-white/80 backdrop-blur-md">
      <div className="flex w-full">
        <div className="flex w-full items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:hidden">
          <BrandBlock title="Guardian OS" subtitle="Control center" />
          <UserActions session={session} onLogout={onLogout} />
        </div>

        <div className="hidden lg:flex lg:w-64 lg:shrink-0 lg:items-center lg:border-r lg:border-slate-200/80 lg:px-4 lg:py-4">
          <BrandBlock title="Guardian OS" subtitle="Control center" />
        </div>

        <div className="hidden flex-1 items-center justify-end gap-3 px-8 py-4 lg:flex">
          <UserActions session={session} onLogout={onLogout} />
        </div>
      </div>
    </header>
  )
}

function LogoutIcon({ className }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9"
      />
    </svg>
  )
}

function ShieldIcon({ className }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016a11.959 11.959 0 00-6.918-1.736L12 2.25z"
      />
    </svg>
  )
}
