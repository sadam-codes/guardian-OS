import { useState } from 'react'
import { deleteUser, updateUser } from '../api/face'
import { useToast } from './ToastProvider'

const ROLE_ADMIN = 'admin'
const ROLE_USER = 'user'

export default function UserManagement({
  users,
  actorRole,
  actorName,
  currentUserId,
  onRefresh,
  onSessionUpdate,
  variant = 'light',
}) {
  const toast = useToast()
  const [deleting, setDeleting] = useState(null)
  const [busy, setBusy] = useState(false)
  const [roleBusy, setRoleBusy] = useState(null)
  const dark = variant === 'dark'

  async function handleRoleChange(user, newRole) {
    if (newRole === user.role) return
    setRoleBusy(user.id)
    try {
      const data = await updateUser(user.id, { role: newRole }, actorRole, actorName)
      toast.success(data.message || `Role updated to ${newRole === ROLE_ADMIN ? 'Admin' : 'User'}.`)
      if (currentUserId === user.id && onSessionUpdate) {
        onSessionUpdate({ role: newRole })
      }
      await onRefresh()
    } catch (err) {
      toast.error(err.message || 'Could not update role.')
    } finally {
      setRoleBusy(null)
    }
  }

  if (users.length === 0) {
    return <p className={`text-sm ${dark ? 'text-slate-500' : 'text-slate-500'}`}>No users registered yet.</p>
  }

  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[320px] text-left text-sm">
          <thead>
            <tr
              className={`border-b text-xs font-semibold uppercase tracking-wide ${
                dark
                  ? 'border-white/10 text-slate-500'
                  : 'border-slate-100 text-slate-500'
              }`}
            >
              <th className="pb-2 pr-2">User</th>
              <th className="pb-2 pr-2">Role</th>
              <th className="pb-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className={dark ? 'divide-y divide-white/[0.06]' : 'divide-y divide-slate-100'}>
            {users.map((u) => (
              <tr key={u.id}>
                <td className="py-2.5 pr-2">
                  <span className={`font-medium ${dark ? 'text-slate-100' : 'text-slate-800'}`}>
                    {u.name}
                  </span>
                  <span className="ml-1 text-xs text-slate-500">#{u.id}</span>
                  {currentUserId === u.id && (
                    <span className="ml-1 text-xs text-slate-500">(you)</span>
                  )}
                </td>
                <td className="py-2.5 pr-2">
                  <select
                    value={u.role}
                    disabled={roleBusy === u.id}
                    onChange={(e) => handleRoleChange(u, e.target.value)}
                    aria-label={`Role for ${u.name}`}
                    className={`cursor-pointer rounded-lg border px-2.5 py-1.5 text-sm font-medium outline-none disabled:cursor-wait disabled:opacity-60 ${
                      dark
                        ? 'border-white/10 bg-[#0a0e14] text-slate-200 focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/25'
                        : 'border-slate-200 bg-white text-slate-700 shadow-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20'
                    }`}
                  >
                    <option value={ROLE_USER}>User</option>
                    <option value={ROLE_ADMIN}>Admin</option>
                  </select>
                </td>
                <td className="py-2.5 text-right">
                  <button
                    type="button"
                    onClick={() => setDeleting(u)}
                    disabled={currentUserId === u.id}
                    aria-label={
                      currentUserId === u.id ? 'Cannot delete your own account' : `Delete ${u.name}`
                    }
                    title={currentUserId === u.id ? 'Cannot delete your own account' : 'Delete user'}
                    className={`inline-flex h-9 w-9 cursor-pointer items-center justify-center rounded-lg text-red-500 transition disabled:cursor-not-allowed disabled:opacity-40 ${
                      dark ? 'hover:bg-red-500/10' : 'hover:bg-red-50'
                    }`}
                  >
                    <TrashIcon className="h-5 w-5" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {deleting && (
        <ConfirmModal
          dark={dark}
          title="Delete user"
          message={`Remove "${deleting.name}"? This cannot be undone.`}
          confirmLabel="Delete"
          danger
          busy={busy}
          onClose={() => setDeleting(null)}
          onConfirm={async () => {
            setBusy(true)
            try {
              const data = await deleteUser(deleting.id, actorRole, currentUserId)
              toast.success(data.message)
              setDeleting(null)
              await onRefresh()
            } catch (err) {
              toast.error(err.message)
            } finally {
              setBusy(false)
            }
          }}
        />
      )}
    </>
  )
}

function ConfirmModal({ title, message, confirmLabel, danger, busy, onClose, onConfirm, dark }) {
  return (
    <Modal title={title} onClose={onClose} dark={dark}>
      <p className={`text-sm ${dark ? 'text-slate-400' : 'text-slate-600'}`}>{message}</p>
      <ModalActions
        dark={dark}
        busy={busy}
        onCancel={onClose}
        onConfirm={onConfirm}
        confirmLabel={confirmLabel}
        danger={danger}
      />
    </Modal>
  )
}

function Modal({ title, children, onClose, dark }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        className="absolute inset-0 cursor-pointer bg-black/60 backdrop-blur-sm"
        aria-label="Close"
        onClick={onClose}
      />
      <div
        className={`relative z-10 w-full max-w-md rounded-2xl border p-6 shadow-xl ${
          dark ? 'border-white/10 bg-[#121820]' : 'border-slate-200 bg-white'
        }`}
      >
        <h3 className={`text-lg font-semibold ${dark ? 'text-white' : 'text-slate-900'}`}>
          {title}
        </h3>
        <div className="mt-4">{children}</div>
      </div>
    </div>
  )
}

function ModalActions({ busy, onCancel, onConfirm, confirmLabel, danger, dark }) {
  return (
    <div className="mt-6 flex justify-end gap-2">
      <button
        type="button"
        onClick={onCancel}
        disabled={busy}
        className={`cursor-pointer rounded-xl border px-4 py-2 text-sm font-medium disabled:opacity-50 ${
          dark
            ? 'border-white/10 text-slate-300 hover:bg-white/5'
            : 'border-slate-200 text-slate-700 hover:bg-slate-50'
        }`}
      >
        Cancel
      </button>
      <button
        type="button"
        onClick={onConfirm}
        disabled={busy}
        className={`cursor-pointer rounded-xl px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50 ${
          danger
            ? 'bg-red-600 hover:bg-red-700'
            : dark
              ? 'bg-cyan-600 hover:bg-cyan-500'
              : 'bg-indigo-600 hover:bg-indigo-700'
        }`}
      >
        {busy ? 'Please wait…' : confirmLabel}
      </button>
    </div>
  )
}

function TrashIcon({ className }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"
      />
    </svg>
  )
}
