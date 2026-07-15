import { useEffect, useRef, useState } from 'react'
import { X, Loader2, AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface Props {
  open: boolean
  title: string
  message: string
  confirmLabel?: string
  destructive?: boolean
  onClose: () => void
  onConfirm: () => Promise<void>
}

export default function ConfirmDialog({
  open, title, message, confirmLabel = '确认', destructive, onClose, onConfirm,
}: Props) {
  const [loading, setLoading] = useState(false)
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    setLoading(false)
  }, [open])

  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, onClose])

  const handleSubmit = async () => {
    setLoading(true)
    try {
      await onConfirm()
      onClose()
    } finally {
      setLoading(false)
    }
  }

  const handleBackdrop = (e: React.MouseEvent) => {
    if (e.target === overlayRef.current) onClose()
  }

  if (!open) return null

  return (
    <div ref={overlayRef} onClick={handleBackdrop} className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-sm rounded-xl border border-border bg-card p-5 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-foreground">{title}</h3>
          <button onClick={onClose} className="rounded-md p-1 text-muted-foreground hover:text-foreground hover:bg-accent transition-colors cursor-pointer">
            <X className="size-4" />
          </button>
        </div>

        {destructive && (
          <div className="flex items-start gap-3 mb-4 p-3 rounded-lg bg-destructive/10">
            <AlertTriangle className="size-5 shrink-0 mt-0.5 text-destructive" />
            <p className="text-sm text-foreground">{message}</p>
          </div>
        )}
        {!destructive && (
          <p className="text-sm text-foreground mb-4">{message}</p>
        )}

        <div className="flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={onClose} disabled={loading}>取消</Button>
          <Button
            size="sm"
            variant={destructive ? 'destructive' : 'default'}
            onClick={handleSubmit}
            disabled={loading}
          >
            {loading ? <><Loader2 className="size-3.5 animate-spin mr-1" /> 处理中…</> : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  )
}
