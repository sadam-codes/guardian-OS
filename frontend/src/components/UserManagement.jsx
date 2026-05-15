import { useState } from 'react'
import { deleteUser } from '../api/face'
import { useToast } from './ToastProvider'

const ROLE_ADMIN = 'admin'

export default function UserManagement({ users, actorRole, actorName, onRefresh }) {
  const toast = useToast()
  const [deleting, setDeleting] = useState(null)
  const [busy, setBusy] = useState(false)

  if (users.length === 0) {
    return <p className="text-sm text-slate-500">No users registered yet.</p>
  }

  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[280px] text-left text-sm">
          <thead>
            <tr className="border-b border-slate-100 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <th className="pb-2 pr-2">User</th>
              <th className="pb-2 pr-2">Role</th>
              <th className="pb-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {users.map((u) => (
              <tr key={u.id}>
                <td className="py-2.5 pr-2">
                  <span className="font-medium text-slate-800">{u.name}</span>
                  {actorName === u.name && (
                    <span className="ml-1 text-xs text-slate-400">(you)</span>
                  )}
                </td>
                <td className="py-2.5 pr-2">
                  <RoleBadge role={u.role} />
                </td>
                <td className="py-2.5 text-right">
                  <button
                    type="button"
                    onClick={() => setDeleting(u)}
                    disabled={actorName === u.name}
                    aria-label={actorName === u.name ? 'Cannot delete your own account' : `Delete ${u.name}`}
                    title={actorName === u.name ? 'Cannot delete your own account' : 'Delete user'}
                    className="inline-flex h-9 w-9 cursor-pointer items-center justify-center rounded-lg text-red-600 transition hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-40"
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
          title="Delete user"
          message={`Remove "${deleting.name}"? This cannot be undone.`}
          confirmLabel="Delete"
          danger
          busy={busy}
          onClose={() => setDeleting(null)}
          onConfirm={async () => {
            setBusy(true)
            try {
              const data = await deleteUser(deleting.id, actorRole, actorName)
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

function ConfirmModal({ title, message, confirmLabel, danger, busy, onClose, onConfirm }) {
  return (
    <Modal title={title} onClose={onClose}>
      <p className="text-sm text-slate-600">{message}</p>
      <ModalActions
        busy={busy}
        onCancel={onClose}
        onConfirm={onConfirm}
        confirmLabel={confirmLabel}
        danger={danger}
      />
    </Modal>
  )
}

function Modal({ title, children, onClose }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        className="absolute inset-0 cursor-pointer bg-slate-900/40 backdrop-blur-sm"
        aria-label="Close"
        onClick={onClose}
      />
      <div className="relative z-10 w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-xl">
        <h3 className="text-lg font-semibold text-slate-900">{title}</h3>
        <div className="mt-4">{children}</div>
      </div>
    </div>
  )
}

function ModalActions({ busy, onCancel, onConfirm, confirmLabel, danger }) {
  return (
    <div className="mt-6 flex justify-end gap-2">
      <button
        type="button"
        onClick={onCancel}
        disabled={busy}
        className="cursor-pointer rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
      >
        Cancel
      </button>
      <button
        type="button"
        onClick={onConfirm}
        disabled={busy}
        className={`cursor-pointer rounded-xl px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50 ${
          danger ? 'bg-red-600 hover:bg-red-700' : 'bg-indigo-600 hover:bg-indigo-700'
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

function RoleBadge({ role }) {
  const isAdmin = role === ROLE_ADMIN
  return (
    <span
      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${
        isAdmin ? 'bg-violet-100 text-violet-700' : 'bg-slate-100 text-slate-600'
      }`}
    >
      {isAdmin ? 'Admin' : 'User'}
    </span>
  )
}
