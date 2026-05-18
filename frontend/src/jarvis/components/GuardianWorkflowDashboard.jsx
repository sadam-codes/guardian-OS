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

  return (
    <div className="mx-auto w-full max-w-6xl space-y-4">
      <div className="rounded-xl border border-indigo-100 bg-gradient-to-r from-indigo-50 to-slate-50 px-4 py-3 sm:px-5">
        <h1 className="text-lg font-bold text-slate-900">{assistantName} — Autonomous Guardian</h1>
        <p className="text-xs text-slate-600 sm:text-sm">
          Voice → AI decision → system actions → desktop control
        </p>
      </div>

      <WorkflowPipeline stages={lastStages} pipeline={pipeline} />

      <VoiceConsole
        userName={session?.name}
        userId={session?.id}
        identityVerified
        runWorkflow={runWorkflow}
      />

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h3 className="mb-2 text-sm font-semibold text-slate-900">Automation & security events</h3>
        <ul className="max-h-36 space-y-1 overflow-y-auto text-xs">
          {events.length === 0 && <li className="text-slate-400">No recent events</li>}
          {events.map((e, i) => (
            <li key={`${e.ts}-${i}`} className="rounded border border-slate-100 bg-slate-50 px-2 py-1">
              <span className="font-medium text-indigo-700">{e.type}</span>
              {e.user && <span className="text-slate-500"> · {e.user}</span>}
              {e.detail && <span className="text-slate-600"> — {e.detail}</span>}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}