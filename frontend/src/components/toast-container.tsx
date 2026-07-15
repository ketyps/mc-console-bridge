import { X } from 'lucide-react'
import { useToastStore } from '@/store/useToast'

export default function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts)
  const removeToast = useToastStore((s) => s.removeToast)

  if (toasts.length === 0) return null

  return (
    <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 max-w-sm">
      {toasts.map((t) => {
        const isError = t.type === 'error'
        return (
          <div
            key={t.id}
            className={`
              flex items-start gap-2 rounded-lg border px-4 py-3 shadow-lg text-sm
              animate-[fadeSlideIn_0.25s_ease-out]
              ${isError
                ? 'bg-destructive text-destructive-foreground border-destructive/30'
                : t.type === 'success'
                ? 'bg-card text-foreground border-border'
                : 'bg-card text-foreground border-border'
              }
            `}
          >
            {/* Icon */}
            {t.type === 'error' && <span className="shrink-0 mt-0.5 text-white/80">!</span>}
            {t.type === 'success' && <span className="shrink-0 mt-0.5 text-emerald-500">✓</span>}
            {t.type === 'info' && <span className="shrink-0 mt-0.5 text-muted-foreground">i</span>}

            <span className="flex-1 break-words">{t.message}</span>
            <button
              onClick={() => removeToast(t.id)}
              className="shrink-0 opacity-60 hover:opacity-100 cursor-pointer bg-transparent border-none p-0 leading-none"
            >
              <X className="size-3.5" />
            </button>
          </div>
        )
      })}
    </div>
  )
}
