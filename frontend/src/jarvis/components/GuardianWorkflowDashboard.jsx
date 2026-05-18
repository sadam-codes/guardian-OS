import { useCallback, useEffect, useState } from 'react'
import {
  executeGuardianWorkflow,
  fetchGuardianEvents,
  fetchGuardianStatus,
} from '../api/guardianWorkflow'
import AdminSectionHeader from '../../components/admin/AdminSectionHeader'
import { VapiCallProvider } from '../context/VapiCallContext'
import VapiVoicePanel from './VapiVoicePanel'
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
    async ({ text, context, plan }) => {
      const res = await executeGuardianWorkflow({
        text: text || '',
        userId: session?.id,
        userName: session?.name,
        identityVerified: true,
        context,
        plan,
      })
      setLastStages(res.stages || [])
      refreshEvents()
      return res
    },
    [session, refreshEvents],
  )

  const firstName = session?.name?.split(' ')[0] || 'User'

  return (
    <div className="space-y-6">
      <AdminSectionHeader
        title={assistantName}
        subtitle={
          <>
            Hello, <span className="font-medium text-cyan-400">{firstName}</span>
          </>
        }
        actions={<WorkflowPipeline stages={lastStages} pipeline={pipeline} />}
      />

      <VapiCallProvider>
        <div className="flex min-h-[min(520px,70vh)] flex-col items-center justify-center rounded-2xl border border-white/[0.08] bg-[#121820] px-6 py-10 sm:px-10 sm:py-12">
          <VapiVoicePanel userName={session?.name} assistantName={assistantName} />
          <VoiceConsole
            userName={session?.name}
            userId={session?.id}
            identityVerified
            runWorkflow={runWorkflow}
            assistantLabel={assistantName}
          />
        </div>
      </VapiCallProvider>
    </div>
  )
}
