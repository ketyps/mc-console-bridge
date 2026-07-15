import { useEffect, useRef, useState } from 'react'
import { X, Loader2, Pencil } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface Props {
  open: boolean
  currentName: string
  onClose: () => void
  onConfirm: (newName: string) => Promise<void>
}

export default function RenameInstanceDialog({ open, currentName, onClose, onConfirm }: Props) {
  const [value, setValue] = useState('')
  const [loading, setLoading] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    setValue(currentName)
    setLoading(false)
    setTimeout(() => {
      inputRef.current?.focus()
      inputRef.current?.select()
    }, 50)
  }, [open, currentName])

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
    if (!trimmed || trimmed === currentName || loading) return
    setLoading(true)
    try {
      await onConfirm(trimmed)
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
          <h3 className="text-sm font-semibold text-foreground">重命名实例</h3>
          <button onClick={onClose} className="rounded-md p-1 text-muted-foreground hover:text-foreground hover:bg-accent transition-colors cursor-pointer">
            <X className="size-4" />
          </button>
        </div>

        <p className="text-xs text-muted-foreground mb-3">
          将 <span className="font-mono text-foreground">{currentName}</span> 重命名为：
        </p>
        <Input
          ref={inputRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="新名称"
          onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
          className="mb-4"
          disabled={loading}
        />

        <div className="flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={onClose} disabled={loading}>取消</Button>
          <Button size="sm" onClick={handleSubmit} disabled={!value.trim() || value.trim() === currentName || loading}>
            {loading ? <><Loader2 className="size-3.5 animate-spin mr-1" /> 保存中…</> : <><Pencil className="size-3.5 mr-1" /> 确认</>}
          </Button>
        </div>
      </div>
    </div>
  )
}
