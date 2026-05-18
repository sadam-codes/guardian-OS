import AdminHeader from './AdminHeader'
import AdminSidebar from './AdminSidebar'

export default function AdminShell({ session, active, onLogout, children }) {
  return (
    <div className="flex min-h-screen flex-col bg-[#0a0c10] text-slate-200">
      <AdminHeader session={session} onLogout={onLogout} />
      <div className="flex flex-1 flex-col lg:flex-row">
        <AdminSidebar active={active} linkNav onChange={() => {}} />
        <main className="flex-1 overflow-auto bg-[#0a0c10] p-5 sm:p-6 lg:p-8">
          <div className="mx-auto w-full max-w-5xl">{children}</div>
        </main>
      </div>
    </div>
  )
}
