export default function AppSidebar({ items, active, onChange }) {
  return (
    <aside className="flex w-full shrink-0 flex-col border-b border-white/10 bg-[#0b1018] lg:w-64 lg:border-b-0 lg:border-r">
      <nav className="flex gap-1 overflow-x-auto p-3 lg:flex-col lg:overflow-visible lg:p-4">
        {items.map(({ id, label, icon: Icon, href }) => {
          const isActive = active === id

          if (href) {
            return (
              <a key={id} href={href} className={navItemClass(isActive)}>
                <Icon className={iconClass(isActive)} />
                {label}
              </a>
            )
          }

          return (
            <button
              key={id}
              type="button"
              onClick={() => onChange?.(id)}
              className={navItemClass(isActive)}
            >
              <Icon className={iconClass(isActive)} />
              {label}
            </button>
          )
        })}
      </nav>
    </aside>
  )
}

function navItemClass(isActive) {
  return `flex shrink-0 cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-medium transition lg:w-full ${
    isActive
      ? 'border border-cyan-500/25 bg-cyan-500/10 text-cyan-300'
      : 'border border-transparent text-slate-400 hover:bg-white/5 hover:text-slate-200'
  }`
}

function iconClass(isActive) {
  return `h-5 w-5 shrink-0 ${isActive ? 'text-cyan-400' : 'text-slate-500'}`
}
