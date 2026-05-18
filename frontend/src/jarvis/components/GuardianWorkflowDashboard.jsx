import { useCallback, useEffect, useState } from 'react'
import {
  executeGuardianWorkflow,
  fetchGuardianEvents,
  fetchGuardianStatus,
} from '../api/guardianWorkflow'
import VoiceConsole from './VoiceConsole'
import WorkflowPipeline from './WorkflowPipeline'

export default function GuardianWorkflowDashboard({ session }) {
  const [pipeline, setPipeline] = useState([])
  const [lastStages, setLastStages] = useState([])
  const [events, setEvents] = useState([])
  const [assistantName, setAssistantName] = useState('Guardian')

  useEffect(() => {
    fetchGuardianStatus()
      .then((s) => {
        setPipeline(s.pipeline || [])
        setAssistantName(s.assistant_name || 'Guardian')
      })
      .catch(() => {})
  }, [])

  const refreshEvents = useCallback(() => {
    fetchGuardianEvents(20)
      .then((d) => setEvents(d.events || []))
      .catch(() => {})
  }, [])

  useEffect(() => {
    refreshEvents()
    const id = setInterval(refreshEvents, 12000)
    return () => clearInterval(id)
  }, [refreshEvents])

  const runWorkflow = useCallback(
    async ({ text, context }) => {
      const res = await executeGuardianWorkflow({
        text: text || '',
        userId: session?.id,
        userName: session?.name,
        identityVerified: true,
        context,
      })
      setLastStages(res.stages || [])
      refreshEvents()
      return res
    },
    [session, refreshEvents],
  )

  const firstName = session?.name?.split(' ')[0] || 'User'

  return (
    <div className="mx-auto w-full max-w-5xl space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-white/10 pb-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-cyan-400">Online</p>
          <h1 className="text-2xl font-semibold text-slate-100">{assistantName}</h1>
          <p className="text-sm text-slate-400">
            Hello, <span className="text-cyan-300">{firstName}</span>
          </p>
        </div>
        <WorkflowPipeline stages={lastStages} pipeline={pipeline} />
      </div>

      <div className="rounded-xl border border-white/10 bg-[#121a26] p-4 sm:p-5">
        <VoiceConsole
          userName={session?.name}
          userId={session?.id}
          identityVerified
          runWorkflow={runWorkflow}
          assistantLabel={assistantName}
        />
      </div>

      {events.length > 0 && (
        <div className="rounded-xl border border-white/10 bg-[#121a26] p-4">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Recent activity
          </h3>
          <ul className="max-h-28 space-y-1.5 overflow-y-auto">
            {events.slice(0, 8).map((e, i) => (
              <li
                key={`${e.ts}-${i}`}
                className="rounded-lg bg-[#0b1018] px-3 py-2 text-sm text-slate-300"
              >
                <span className="font-medium text-cyan-400">{e.type}</span>
                {e.detail && <span className="text-slate-400"> — {e.detail}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
