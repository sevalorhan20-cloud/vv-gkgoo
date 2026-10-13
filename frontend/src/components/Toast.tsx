import { CheckCircle2, CircleAlert, Info, X } from 'lucide-react'
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react'
import type { ToastMessage } from '../types'

type ToastInput = Omit<ToastMessage, 'id'>
type ToastContextValue = { notify: (toast: ToastInput) => void }

const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastMessage[]>([])
  const idRef = useRef(0)

  const remove = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const notify = useCallback(
    (toast: ToastInput) => {
      const id = ++idRef.current
      setToasts((current) => [...current.slice(-3), { ...toast, id }])
      window.setTimeout(() => remove(id), toast.kind === 'error' ? 7000 : 4500)
    },
    [remove],
  )

  const value = useMemo(() => ({ notify }), [notify])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-region" role="status" aria-live="polite" aria-atomic="true">
        {toasts.map((toast) => {
          const Icon = toast.kind === 'success' ? CheckCircle2 : toast.kind === 'error' ? CircleAlert : Info
          return (
            <div className={`toast toast--${toast.kind}`} key={toast.id}>
              <Icon aria-hidden="true" size={19} />
              <div className="toast__content">
                <strong>{toast.title}</strong>
                {toast.description && <span>{toast.description}</span>}
              </div>
              <button className="icon-button icon-button--small" onClick={() => remove(toast.id)} aria-label="Bildirimi kapat">
                <X size={16} />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext)
  if (!context) throw new Error('useToast must be used inside ToastProvider')
  return context
}
