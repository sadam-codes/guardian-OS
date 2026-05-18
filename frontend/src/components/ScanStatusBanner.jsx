const LIGHT_STYLES = {
  idle: {
    wrap: 'border-slate-200 bg-slate-50 text-slate-800',
    icon: 'text-slate-500',
    bar: 'bg-slate-400',
  },
  progress: {
    wrap: 'border-indigo-200 bg-indigo-50 text-indigo-950',
    icon: 'text-indigo-600',
    bar: 'bg-indigo-500',
  },
  loading: {
    wrap: 'border-sky-200 bg-sky-50 text-sky-950',
    icon: 'text-sky-600',
    bar: 'bg-sky-500',
  },
  success: {
    wrap: 'border-emerald-200 bg-emerald-50 text-emerald-950',
    icon: 'text-emerald-600',
    bar: 'bg-emerald-500',
  },
  error: {
    wrap: 'border-red-200 bg-red-50 text-red-950',
    icon: 'text-red-600',
    bar: 'bg-red-500',
  },
  blocked: {
    wrap: 'border-amber-200 bg-amber-50 text-amber-950',
    icon: 'text-amber-600',
    bar: 'bg-amber-500',
  },
}

const DARK_STYLES = {
  idle: {
    wrap: 'border-white/10 bg-[#0b1018] text-slate-300',
    icon: 'text-slate-400',
    bar: 'bg-slate-500',
  },
  progress: {
    wrap: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-100',
    icon: 'text-cyan-400',
    bar: 'bg-cyan-500',
  },
  loading: {
    wrap: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-100',
    icon: 'text-cyan-400',
    bar: 'bg-cyan-500',
  },
  success: {
    wrap: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100',
    icon: 'text-emerald-400',
    bar: 'bg-emerald-500',
  },
  error: {
    wrap: 'border-red-500/30 bg-red-500/10 text-red-200',
    icon: 'text-red-400',
    bar: 'bg-red-500',
  },
  blocked: {
    wrap: 'border-amber-500/30 bg-amber-500/10 text-amber-100',
    icon: 'text-amber-400',
    bar: 'bg-amber-500',
  },
}

export default function ScanStatusBanner({ message, theme = 'light' }) {
  if (!message?.title) return null

  const palette = theme === 'dark' ? DARK_STYLES : LIGHT_STYLES
  const style = palette[message.type] || palette.idle

  return (
    <div
      role="status"
      className={`rounded-xl border px-4 py-3 shadow-sm ${style.wrap}`}
    >
      <div className="flex gap-3">
        <StatusIcon type={message.type} className={`mt-0.5 h-5 w-5 shrink-0 ${style.icon}`} />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold leading-snug">{message.title}</p>
          {message.detail && (
            <p className="mt-1 text-sm leading-relaxed opacity-90">{message.detail}</p>
          )}
          {message.progress && (
            <div className="mt-3">
              <div className="mb-1 flex justify-between text-xs font-medium opacity-80">
                <span>Progress</span>
                <span>
                  {message.progress.current}/{message.progress.total}
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-white/60">
                <div
                  className={`h-full rounded-full transition-all duration-300 ${style.bar}`}
                  style={{
                    width: `${(message.progress.current / message.progress.total) * 100}%`,
                  }}
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function StatusIcon({ type, className }) {
  if (type === 'loading' || type === 'progress') {
    return (
      <svg className={`${className} animate-spin`} fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        />
      </svg>
    )
  }
  if (type === 'success') {
    return (
      <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
      </svg>
    )
  }
  if (type === 'error') {
    return (
      <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
    )
  }
  if (type === 'blocked') {
    return (
      <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
        />
      </svg>
    )
  }
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0"
      />
    </svg>
  )
}
