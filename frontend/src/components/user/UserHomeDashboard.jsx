import { useEffect, useState } from 'react'
import { fetchGuardianEvents, fetchGuardianStatus } from '../../jarvis/api/guardianWorkflow'
import { fetchJarvisCapabilities } from '../../jarvis/api/jarvis'

const CAPABILITIES = [
  { title: 'Voice commands', desc: 'Speak naturally — open apps, search, control volume' },
  { title: 'WhatsApp & Instagram', desc: 'Send messages by voice to your contacts' },
  { title: 'Desktop control', desc: 'Launch apps, folders, terminal, and more' },
  { title: 'Secured', desc: 'Face-verified session with safety checks' },
]

function useLiveClock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 30_000)
    return () => clearInterval(id)
  }, [])
  return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function StatCard({ label, value, accent }) {
  return (
    <div className="rounded-xl border border-white/10 bg-[#121a26] px-4 py-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`mt-0.5 text-lg font-semibold ${accent || 'text-slate-100'}`}>{value}</p>
    </div>
  )
}

export default function UserHomeDashboard({ session }) {
  const [assistantName, setAssistantName] = useState('Guardian')
  const [examples, setExamples] = useState([])
  const [recentEvents, setRecentEvents] = useState([])
  const [osEnabled, setOsEnabled] = useState(true)
  const time = useLiveClock()
  const firstName = session?.name?.split(' ')[0] || 'there'

  useEffect(() => {
    fetchJarvisCapabilities()
      .then((d) => {
        setAssistantName(d.assistant_name || 'Guardian')
        setExamples((d.examples || []).slice(0, 6))
      })
      .catch(() => {})
    fetchGuardianStatus()
      .then((s) => setOsEnabled(s.os_control_enabled !== false))
      .catch(() => {})
    fetchGuardianEvents(5)
      .then((d) => setRecentEvents(d.events || []))
      .catch(() => {})
  }, [])

  return (
    <div className="mx-auto w-full max-w-6xl space-y-5">
      {/* hero */}
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-white/10 pb-5">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-cyan-400">
            Dashboard · {time}
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-slate-100 sm:text-3xl">
            Welcome back, {firstName}
          </h1>
          <p className="mt-1 max-w-xl text-sm text-slate-400">
            Your identity is verified. {assistantName} is ready to run voice commands on this PC.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            Verified
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs font-medium text-cyan-400">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-400" />
            Online
          </span>
        </div>
      </div>

      {/* stats row */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Assistant" value={assistantName} accent="text-cyan-400" />
        <StatCard label="Session" value="Active" accent="text-emerald-400" />
        <StatCard label="OS control" value={osEnabled ? 'Enabled' : 'Off'} />
        <StatCard label="User" value={session?.name || '—'} />
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        {/* main CTA */}
        <div className="lg:col-span-2">
          <div className="relative overflow-hidden rounded-2xl border border-cyan-500/20 bg-gradient-to-br from-[#121a26] to-[#0d1520] p-6 sm:p-8">
            <div
              className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-cyan-500/10 blur-3xl"
              aria-hidden
            />
            <div className="relative flex flex-col gap-6 sm:flex-row sm:items-center">
              <div className="flex h-24 w-24 shrink-0 items-center justify-center rounded-full border border-cyan-500/40 bg-cyan-500/10 shadow-[0_0_40px_rgba(6,182,212,0.15)]">
                <svg
                  className="h-11 w-11 text-cyan-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={1.5}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z"
                  />
                </svg>
              </div>
              <div className="min-w-0 flex-1">
                <h2 className="text-xl font-semibold text-slate-100">Talk to {assistantName}</h2>
                <p className="mt-2 text-sm leading-relaxed text-slate-400">
                  Open the voice assistant to control your computer — send WhatsApp or Instagram messages,
                  search the web, and run multi-step commands hands-free.
                </p>
                <a
                  href="/jarvis"
                  className="mt-5 inline-flex cursor-pointer items-center gap-2 rounded-lg bg-cyan-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-cyan-900/30 transition hover:bg-cyan-500"
                >
                  Launch assistant
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </a>
              </div>
            </div>

            {examples.length > 0 && (
              <div className="relative mt-6 border-t border-white/10 pt-5">
                <p className="mb-3 text-xs font-medium text-slate-400">Try saying</p>
                <div className="flex flex-wrap gap-2">
                  {examples.map((ex) => (
                    <span
                      key={ex}
                      className="rounded-lg border border-white/10 bg-[#0b1018] px-2.5 py-1.5 text-xs text-slate-300"
                    >
                      &ldquo;{ex.length > 55 ? `${ex.slice(0, 55)}…` : ex}&rdquo;
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* side panel */}
        <div className="space-y-4">
          <div className="rounded-xl border border-white/10 bg-[#121a26] p-4">
            <h3 className="text-sm font-semibold text-slate-200">Recent activity</h3>
            <ul className="mt-3 space-y-2">
              {recentEvents.length === 0 && (
                <li className="text-sm text-slate-500">No commands yet — try the assistant.</li>
              )}
              {recentEvents.map((e, i) => (
                <li
                  key={`${e.ts}-${i}`}
                  className="rounded-lg bg-[#0b1018] px-3 py-2 text-xs text-slate-400"
                >
                  <span className="font-medium text-cyan-400">{e.type}</span>
                  {e.detail && <span> — {e.detail}</span>}
                </li>
              ))}
            </ul>
            {recentEvents.length > 0 && (
              <a
                href="/jarvis"
                className="mt-3 inline-block text-xs font-medium text-cyan-400 hover:text-cyan-300"
              >
                View all in assistant →
              </a>
            )}
          </div>

          <div className="rounded-xl border border-white/10 bg-[#121a26] p-4">
            <h3 className="text-sm font-semibold text-slate-200">How you signed in</h3>
            <ul className="mt-3 space-y-2 text-sm text-slate-400">
              <li className="flex items-center gap-2">
                <span className="text-emerald-400">✓</span> Face recognition matched
              </li>
              <li className="flex items-center gap-2">
                <span className="text-emerald-400">✓</span> Secure session started
              </li>
              <li className="flex items-center gap-2">
                <span className="text-cyan-400">→</span> Voice control available
              </li>
            </ul>
          </div>
        </div>
      </div>

      {/* capabilities grid */}
      <div>
        <h3 className="mb-3 text-sm font-semibold text-slate-300">What you can do</h3>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {CAPABILITIES.map(({ title, desc }) => (
            <div
              key={title}
              className="rounded-xl border border-white/10 bg-[#121a26] p-4 transition hover:border-cyan-500/20"
            >
              <span className="inline-block h-1 w-8 rounded-full bg-cyan-500/60" />
              <p className="mt-3 font-medium text-slate-200">{title}</p>
              <p className="mt-1 text-xs leading-relaxed text-slate-500">{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

