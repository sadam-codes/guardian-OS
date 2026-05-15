import UserManagement from '../UserManagement'

export default function UsersPanel({ users, actorName, currentUserId, onRefresh, onSessionUpdate }) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-bold text-slate-900">Registered users</h2>
        <p className="mt-1 text-sm text-slate-500">View and remove enrolled accounts.</p>
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <UserManagement
          users={users}
          actorRole="admin"
          actorName={actorName}
          currentUserId={currentUserId}
          onRefresh={onRefresh}
          onSessionUpdate={onSessionUpdate}
        />
      </div>
    </div>
  )
}
