const STAGE_LABELS = {
  camera_mic_input: 'Camera / Mic',
  identity_verification: 'Identity',
  voice_understanding: 'Voice',
  ai_decision_engine: 'AI Engine',
  system_action_execution: 'Execute',
  desktop_control: 'Desktop',
}

const STATUS_STYLES = {
  ok: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  warn: 'border-amber-200 bg-amber-50 text-amber-800',
  fail: 'border-red-200 bg-red-50 text-red-800',
  blocked: 'border-red-300 bg-red-100 text-red-900',
  skip: 'border-slate-200 bg-slate-50 text-slate-500',
  pending: 'border-slate-200 bg-white text-slate-400',
}

export default function WorkflowPipeline({ stages = [], pipeline = [] }) {
  const byStage = Object.fromEntries(stages.map((s) => [s.stage, s]))
  const ordered = pipeline.length ? pipeline : Object.keys(STAGE_LABELS)

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold text-slate-900">Jarvis workflow pipeline</h3>
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-stretch">
        {ordered.map((stage, i) => {
          const log = byStage[stage]
          const status = log?.status || 'pending'
          const style = STATUS_STYLES[status] || STATUS_STYLES.pending
          return (
            <div key={stage} className="flex items-center gap-1 sm:flex-1">
              <div
                className={`min-w-0 flex-1 rounded-lg border px-2 py-2 text-center text-[10px] leading-tight sm:text-xs ${style}`}
              >
                <p className="font-semibold">{STAGE_LABELS[stage] || stage}</p>
                {log?.detail && (
                  <p className="mt-0.5 truncate text-[9px] opacity-80" title={log.detail}>
                    {log.detail}
                  </p>
                )}
                {log?.duration_ms != null && log.duration_ms > 0 && (
                  <p className="text-[9px] opacity-60">{log.duration_ms}ms</p>
                )}
              </div>
              {i < ordered.length - 1 && (
                <span className="hidden text-slate-300 sm:inline" aria-hidden>
                  →
                </span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
