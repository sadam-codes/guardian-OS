import { createContext, useCallback, useContext, useMemo, useState } from 'react'

const ToastContext = createContext(null)

let toastId = 0

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const push = useCallback(
    (type, message, duration = 4000) => {
      const id = ++toastId
      setToasts((prev) => [...prev, { id, type, message }])
      setTimeout(() => dismiss(id), duration)
    },
    [dismiss],
  )

  const toast = useMemo(
    () => ({
      success: (message) => push('success', message),
      error: (message) => push('error', message),
      info: (message) => push('info', message),
    }),
    [push],
  )

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div
        className="pointer-events-none fixed right-4 top-4 z-[100] flex w-full max-w-sm flex-col gap-3"
        aria-live="polite"
      >
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onDismiss={() => dismiss(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}

function ToastItem({ toast, onDismiss }) {
  const styles =
    toast.type === 'success'
      ? 'border-emerald-200 bg-white text-emerald-900 shadow-emerald-100'
      : toast.type === 'error'
        ? 'border-red-200 bg-white text-red-900 shadow-red-100'
        : 'border-indigo-200 bg-white text-indigo-900 shadow-indigo-100'

  const iconColor =
    toast.type === 'success' ? 'text-emerald-600' : toast.type === 'error' ? 'text-red-600' : 'text-indigo-600'

  return (
    <div
      role="alert"
      className={`toast-enter pointer-events-auto flex items-start gap-3 rounded-xl border px-4 py-3 shadow-lg ${styles}`}
    >
      <ToastIcon type={toast.type} className={`mt-0.5 h-5 w-5 shrink-0 ${iconColor}`} />
      <p className="flex-1 text-sm font-medium leading-snug">{toast.message}</p>
      <button
        type="button"
        onClick={onDismiss}
        className="shrink-0 rounded-md p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
        aria-label="Dismiss"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  )
}

function ToastIcon({ type, className }) {
  if (type === 'error') {
    return (
      <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
    )
  }
  if (type === 'info') {
    return (
      <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
    )
  }
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  )
}
