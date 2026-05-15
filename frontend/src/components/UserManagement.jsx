import { useState } from 'react'
import { deleteUser, updateUser } from '../api/face'
import { useToast } from './ToastProvider'

const ROLE_ADMIN = 'admin'
const ROLE_USER = 'user'

export default function UserManagement({ users, actorRole, actorName, onRefresh }) {
  const toast = useToast()
  const [editing, setEditing] = useState(null)
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
                  <div className="flex justify-end gap-1">
                    <button
                      type="button"
                      onClick={() => setEditing(u)}
                      className="rounded-lg px-2 py-1 text-xs font-medium text-indigo-600 hover:bg-indigo-50"
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => setDeleting(u)}
                      disabled={actorName === u.name}
                      title={actorName === u.name ? 'Cannot delete your own account' : 'Delete user'}
                      className="rounded-lg px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {editing && (
        <EditUserModal
          user={editing}
          busy={busy}
          onClose={() => setEditing(null)}
          onSave={async (payload) => {
            if (!payload.name && !payload.role && !payload.imageFile) {
              toast.error('No changes to save')
              return
            }
            setBusy(true)
            try {
              const data = await updateUser(editing.id, payload, actorRole)
              toast.success(data.message)
              setEditing(null)
              await onRefresh()
            } catch (err) {
              toast.error(err.message)
            } finally {
              setBusy(false)
            }
          }}
        />
      )}

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

function EditUserModal({ user, busy, onClose, onSave }) {
  const [name, setName] = useState(user.name)
  const [role, setRole] = useState(user.role)
  const [faceFile, setFaceFile] = useState(null)

  return (
    <Modal title="Edit user" onClose={onClose}>
      <div className="space-y-4">
        <Field label="Full name">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={inputClass}
          />
        </Field>
        <Field label="Role">
          <select value={role} onChange={(e) => setRole(e.target.value)} className={inputClass}>
            <option value={ROLE_USER}>User</option>
            <option value={ROLE_ADMIN}>Admin</option>
          </select>
        </Field>
        <Field label="Update face (optional)">
          <input
            type="file"
            accept="image/*"
            capture="user"
            onChange={(e) => setFaceFile(e.target.files?.[0] || null)}
            className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-indigo-50 file:px-3 file:py-2 file:text-sm file:font-medium file:text-indigo-700"
          />
          <p className="mt-1 text-xs text-slate-500">Leave empty to keep the current face data.</p>
        </Field>
      </div>
      <ModalActions
        busy={busy}
        onCancel={onClose}
        onConfirm={() =>
          onSave({
            name: name.trim() !== user.name ? name.trim() : null,
            role: role !== user.role ? role : null,
            imageFile: faceFile,
          })
        }
        confirmDisabled={!name.trim()}
        confirmLabel="Save changes"
      />
    </Modal>
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
        className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm"
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

function ModalActions({ busy, onCancel, onConfirm, confirmLabel, confirmDisabled, danger }) {
  return (
    <div className="mt-6 flex justify-end gap-2">
      <button
        type="button"
        onClick={onCancel}
        disabled={busy}
        className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
      >
        Cancel
      </button>
      <button
        type="button"
        onClick={onConfirm}
        disabled={busy || confirmDisabled}
        className={`rounded-xl px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 ${
          danger ? 'bg-red-600 hover:bg-red-700' : 'bg-indigo-600 hover:bg-indigo-700'
        }`}
      >
        {busy ? 'Please wait…' : confirmLabel}
      </button>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-slate-700">{label}</label>
      {children}
    </div>
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

const inputClass =
  'w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-slate-900 shadow-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20'
