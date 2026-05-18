const STAGE_LABELS = {
  camera_mic_input: 'Input',
  identity_verification: 'Identity',
  voice_understanding: 'Voice',
  ai_decision_engine: 'AI',
  system_action_execution: 'Execute',
  desktop_control: 'Desktop',
}

const STATUS_DOT = {
  ok: 'bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.8)]',
  warn: 'bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.6)]',
  fail: 'bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.6)]',
  blocked: 'bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.8)]',
  skip: 'bg-slate-600',
  pending: 'bg-slate-700',
}

export default function WorkflowPipeline({ stages = [], pipeline = [] }) {
  const byStage = Object.fromEntries(stages.map((s) => [s.stage, s]))
  const ordered = pipeline.length ? pipeline : Object.keys(STAGE_LABELS)
  const hasActivity = stages.some((s) => s.status && s.status !== 'pending')

  if (!hasActivity) {
    return (
      <div className="flex items-center justify-center gap-2 py-1">
        {ordered.slice(0, 6).map((stage) => (
          <span
            key={stage}
            className="h-1.5 w-1.5 rounded-full bg-slate-600/80"
            title={STAGE_LABELS[stage]}
          />
        ))}
      </div>
    )
  }

  return (
    <div className="flex flex-wrap items-center justify-center gap-1 sm:gap-2">
      {ordered.map((stage, i) => {
        const log = byStage[stage]
        const status = log?.status || 'pending'
        const dot = STATUS_DOT[status] || STATUS_DOT.pending
        const active = status === 'ok' || status === 'warn'
        return (
          <div key={stage} className="flex items-center gap-1 sm:gap-2">
            <div
              className="flex items-center gap-1.5 rounded-full border border-white/5 bg-white/[0.03] px-2 py-1 sm:px-2.5"
              title={log?.detail || STAGE_LABELS[stage]}
            >
              <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${dot}`} />
              <span
                className={`text-[10px] font-medium tracking-wide sm:text-[11px] ${
                  active ? 'text-cyan-300/90' : 'text-slate-500'
                }`}
              >
                {STAGE_LABELS[stage] || stage}
              </span>
            </div>
            {i < ordered.length - 1 && (
              <span className="hidden h-px w-3 bg-gradient-to-r from-cyan-500/40 to-transparent sm:block" />
            )}
          </div>
        )
      })}
    </div>
  )
}
