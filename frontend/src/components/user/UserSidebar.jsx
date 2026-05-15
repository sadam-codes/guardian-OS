const NAV = [
  {
    id: 'home',
    label: 'Home',
    href: '/user',
    icon: HomeIcon,
  },
  {
    id: 'jarvis',
    label: 'Voice assistant',
    href: '/jarvis',
    icon: JarvisIcon,
  },
]

export default function UserSidebar({ active }) {
  return (
    <aside className="flex w-full shrink-0 flex-col border-b border-slate-200 bg-white lg:w-64 lg:border-b-0 lg:border-r">
      <nav className="flex gap-1 overflow-x-auto p-3 lg:flex-col lg:overflow-visible lg:p-4">
        {NAV.map(({ id, label, icon: Icon, href }) => {
          const isActive = active === id
          return (
            <a
              key={id}
              href={href}
              className={`flex shrink-0 cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-medium transition lg:w-full ${
                isActive
                  ? 'bg-indigo-50 text-indigo-700'
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
              }`}
            >
              <Icon className={`h-5 w-5 shrink-0 ${isActive ? 'text-indigo-600' : 'text-slate-400'}`} />
              {label}
            </a>
          )
        })}
      </nav>
    </aside>
  )
}

function HomeIcon({ className }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25"
      />
    </svg>
  )
}

function JarvisIcon({ className }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z"
      />
    </svg>
  )
}
