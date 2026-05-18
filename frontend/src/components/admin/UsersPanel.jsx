import UserManagement from '../UserManagement'
import AdminSectionHeader from './AdminSectionHeader'

export default function UsersPanel({ users, actorName, currentUserId, onRefresh, onSessionUpdate }) {
  return (
    <div className="space-y-6">
      <AdminSectionHeader
        title="Registered users"
        subtitle="View and manage enrolled accounts."
      />

      <div className="rounded-2xl border border-white/[0.08] bg-[#121820] p-6 sm:p-8">
        <UserManagement
          users={users}
          actorRole="admin"
          actorName={actorName}
          currentUserId={currentUserId}
          onRefresh={onRefresh}
          onSessionUpdate={onSessionUpdate}
          variant="dark"
        />
      </div>
    </div>
  )
}
