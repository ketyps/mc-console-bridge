import { useEffect, useRef, useState } from 'react'
import { X, Loader2, Copy } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface Props {
  open: boolean
  sourceName: string
  onClose: () => void
  onConfirm: (newName: string) => Promise<void>
}

export default function DuplicateInstanceDialog({ open, sourceName, onClose, onConfirm }: Props) {
  const [value, setValue] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    setValue('')
    setLoading(false)
    setError('')
    setTimeout(() => inputRef.current?.focus(), 50)
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
    const trimmed = value.trim()
    if (!trimmed || loading) return
    setLoading(true)
    setError('')
    try {
      await onConfirm(trimmed)
      onClose()
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      if (msg.includes('409')) {
        setError('目标名称已存在')
      } else {
        setError(msg || '复制失败')
      }
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
          <h3 className="text-sm font-semibold text-foreground">复制实例</h3>
          <button onClick={onClose} className="rounded-md p-1 text-muted-foreground hover:text-foreground hover:bg-accent transition-colors cursor-pointer">
            <X className="size-4" />
          </button>
        </div>

        <p className="text-xs text-muted-foreground mb-3">
          从 <span className="font-mono text-foreground">{sourceName}</span> 复制到新实例：
        </p>
        <Input
          ref={inputRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="新实例名称"
          onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
          className="mb-4"
          disabled={loading}
        />

        {error && (
          <p className="text-xs text-destructive mb-3">{error}</p>
        )}

        <div className="flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={onClose} disabled={loading}>取消</Button>
          <Button size="sm" onClick={handleSubmit} disabled={!value.trim() || loading}>
            {loading ? <><Loader2 className="size-3.5 animate-spin mr-1" /> 复制中…</> : <><Copy className="size-3.5 mr-1" /> 复制</>}
          </Button>
        </div>
      </div>
    </div>
  )
}
