/**
 * ToastContainer — renders live toast notifications in the top-right corner.
 * Toasts are driven by MetricsContext (WebSocket events push them in).
 */
import { X, AlertTriangle, Zap, Info, CheckCircle2 } from 'lucide-react'
import { useMetrics } from '../../context/MetricsContext'

const ICONS = {
  danger:  AlertTriangle,
  warning: AlertTriangle,
  info:    Info,
  success: CheckCircle2,
}

export default function ToastContainer() {
  const { toasts, removeToast } = useMetrics()
  if (!toasts.length) return null

  return (
    <div
      className="fixed top-4 right-4 z-50 flex flex-col gap-2 pointer-events-none"
      aria-live="polite"
    >
      {toasts.map(toast => {
        const Icon = ICONS[toast.type] ?? Zap
        return (
          <div
            key={toast.id}
            className={`toast-${toast.type} pointer-events-auto`}
          >
            <Icon className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-xs leading-none mb-1">{toast.title}</p>
              <p className="text-xs opacity-80 leading-snug line-clamp-2">{toast.message}</p>
            </div>
            <button
              onClick={() => removeToast(toast.id)}
              className="flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )
      })}
    </div>
  )
}
