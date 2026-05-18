export default function AdminSectionHeader({ eyebrow = 'Online', title, subtitle, actions }) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-cyan-400">
          {eyebrow}
        </p>
        <h1 className="mt-1 text-3xl font-bold tracking-tight text-white sm:text-4xl">{title}</h1>
        {subtitle != null && subtitle !== '' && (
          <p className="mt-1 text-sm text-slate-400">{subtitle}</p>
        )}
      </div>
      {actions}
    </div>
  )
}
