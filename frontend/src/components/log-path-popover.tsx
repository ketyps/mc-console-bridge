import { useEffect, useRef, useState } from 'react'
import { X, Check, Loader2, FolderSearch } from 'lucide-react'
import * as api from '@/api/instances'
import { toast } from '@/store/useToast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface Props {
  instanceName: string
  open: boolean
  onClose: () => void
}

export default function LogPathPopover({ instanceName, open, onClose }: Props) {
  const [value, setValue] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [browsing, setBrowsing] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const overlayRef = useRef<HTMLDivElement>(null)

  // Load current log_dir on open
  useEffect(() => {
    if (!open) return
    setLoading(true)
    api.getInstanceConfig(instanceName)
      .then((data) => {
        const cfg = (data as { config?: Record<string, unknown> }).config ?? {}
        setValue(String(cfg.log_dir ?? 'logs'))
      })
      .catch((err) => {
        toast.error('加载配置失败: ' + (err instanceof Error ? err.message : String(err)))
      })
      .finally(() => setLoading(false))
  }, [open, instanceName])

  // Focus input when loaded
  useEffect(() => {
    if (!loading && open && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [loading, open])

  // Close on Escape
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, onClose])

  const handleBrowse = async () => {
    setBrowsing(true)
    try {
      const result = await api.browseFolder()
      if (result.path) {
        setValue(result.path)
      }
    } catch (err) {
      toast.error('打开文件夹选择器失败: ' + (err instanceof Error ? err.message : String(err)))
    } finally {
      setBrowsing(false)
    }
  }

  const handleSave = async () => {
    const trimmed = value.trim()
    if (!trimmed) return
    setSaving(true)
    try {
      await api.updateInstanceConfig(instanceName, { log_dir: trimmed })
      toast.success(`日志保存路径已更新为: ${trimmed}`)
      onClose()
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      if (msg.includes('409') || msg.includes('请先停止')) {
        toast.error('请先停止机器人再修改日志路径')
      } else {
        toast.error('保存失败: ' + msg)
      }
    } finally {
      setSaving(false)
    }
  }

  const handleBackdrop = (e: React.MouseEvent) => {
    if (e.target === overlayRef.current) onClose()
  }

  if (!open) return null

  return (
    <div
      ref={overlayRef}
      onClick={handleBackdrop}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
    >
      <div className="w-full max-w-sm rounded-xl border border-border bg-card p-5 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-foreground">更改日志保存路径</h3>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-muted-foreground hover:text-foreground hover:bg-accent transition-colors cursor-pointer"
          >
            <X className="size-4" />
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-6 text-muted-foreground">
            <Loader2 className="size-4 animate-spin mr-2" />
            <span className="text-sm">加载中…</span>
          </div>
        ) : (
          <>
            <p className="text-xs text-muted-foreground mb-3">
              实例 <span className="font-mono text-foreground">{instanceName}</span> 的日志保存路径：
            </p>
            <div className="flex gap-2 mb-4">
              <Input
                ref={inputRef}
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder="logs"
                onKeyDown={(e) => e.key === 'Enter' && handleSave()}
                className="flex-1"
              />
              <Button
                variant="outline"
                size="sm"
                type="button"
                onClick={handleBrowse}
                disabled={browsing}
                className="shrink-0"
              >
                {browsing ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <FolderSearch className="size-3.5" />
                )}
                浏览…
              </Button>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={onClose}>
                取消
              </Button>
              <Button size="sm" onClick={handleSave} disabled={!value.trim() || saving}>
                {saving ? (
                  <><Loader2 className="size-3.5 animate-spin mr-1" /> 保存中…</>
                ) : (
                  <><Check className="size-3.5 mr-1" /> 确认</>
                )}
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
