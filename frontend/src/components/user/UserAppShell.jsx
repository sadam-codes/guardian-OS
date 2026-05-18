import UserSidebar from './UserSidebar'

export default function UserAppShell({ session, active, onLogout, children }) {
  return (
    <div className="flex min-h-screen flex-col bg-[#0b1018] text-slate-200">
      <header className="shrink-0 border-b border-white/10 bg-[#0b1018]">
        <div className="flex items-center justify-between gap-4 px-4 py-3 sm:px-5">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-cyan-500/30 bg-cyan-500/10">
              <svg className="h-4 w-4 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z"
                />
              </svg>
            </div>
            <div>
              <h1 className="text-sm font-semibold text-slate-100">Guardian OS</h1>
              <p className="text-xs text-slate-500">Voice assistant</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {session?.name && <span className="text-sm text-slate-400">{session.name}</span>}
            <button
              type="button"
              onClick={onLogout}
              aria-label="Log out"
              className="flex h-9 w-9 cursor-pointer items-center justify-center rounded-lg border border-white/10 text-slate-400 transition hover:border-red-500/40 hover:bg-red-500/10 hover:text-red-400"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9"
                />
              </svg>
            </button>
          </div>
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <UserSidebar active={active} />
        <main className="min-h-0 flex-1 overflow-auto p-4 sm:p-5">{children}</main>
      </div>
    </div>
  )
}
