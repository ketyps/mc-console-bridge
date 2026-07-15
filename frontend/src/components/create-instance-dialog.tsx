import { useEffect, useRef, useState } from 'react'
import { X, Loader2, Plus, Upload } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import * as api from '@/api/instances'

interface Props {
  open: boolean
  onClose: () => void
  onConfirm: (name: string) => Promise<void>
  onImported?: () => void
}

export default function CreateInstanceDialog({ open, onClose, onConfirm, onImported }: Props) {
  const [value, setValue] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    setValue('')
    setLoading(false)
    setError('')
    setSelectedFile(null)
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

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null
    setSelectedFile(file)
    setError('')
  }

  const handleSubmit = async () => {
    const trimmed = value.trim()
    if (!trimmed || loading) return
    setLoading(true)
    setError('')

    try {
      if (selectedFile) {
        // ─── 导入模式 ───
        const text = await selectedFile.text()
        let parsed: Record<string, unknown>
        try {
          parsed = JSON.parse(text)
        } catch {
          setError('配置文件格式错误')
          setLoading(false)
          return
        }
        if (typeof parsed !== 'object' || parsed === null) {
          setError('配置文件格式错误')
          setLoading(false)
          return
        }

        // 【安全】前端显式删除 API Key，不发给后端
        const config = { ...parsed }
        delete (config as Record<string, unknown>).deepseek_api_key

        await api.importInstance(trimmed, config)
        onImported?.()
      } else {
        // ─── 普通创建模式 ───
        await onConfirm(trimmed)
      }
      onClose()
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      // 不要打印 config 完整内容到控制台
      if (msg.includes('409')) {
        setError('实例已存在')
      } else {
        setError(msg || '操作失败')
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
          <h3 className="text-sm font-semibold text-foreground">新建实例</h3>
          <button onClick={onClose} className="rounded-md p-1 text-muted-foreground hover:text-foreground hover:bg-accent transition-colors cursor-pointer">
            <X className="size-4" />
          </button>
        </div>

        <p className="text-xs text-muted-foreground mb-3">输入新实例的名称：</p>
        <Input
          ref={inputRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="实例名称"
          onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
          className="mb-4"
          disabled={loading}
        />

        {/* 导入入口 */}
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs text-muted-foreground">或从配置文件导入</span>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            onChange={handleFileChange}
            className="hidden"
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className={`
              w-full flex items-center gap-2 rounded-lg border border-dashed px-3 py-2
              text-sm transition-colors cursor-pointer
              ${selectedFile
                ? 'border-primary text-foreground bg-primary/5'
                : 'border-border text-muted-foreground hover:border-foreground/30 hover:text-foreground'
              }
            `}
            disabled={loading}
          >
            <Upload className="size-4 shrink-0" />
            <span className="truncate">
              {selectedFile ? selectedFile.name : '选择配置文件…'}
            </span>
          </button>
        </div>

        {/* 错误提示 */}
        {error && (
          <p className="text-xs text-destructive mb-3">{error}</p>
        )}

        <div className="flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={onClose} disabled={loading}>取消</Button>
          <Button size="sm" onClick={handleSubmit} disabled={!value.trim() || loading}>
            {loading ? <><Loader2 className="size-3.5 animate-spin mr-1" /> 处理中…</> : <><Plus className="size-3.5 mr-1" /> 创建</>}
          </Button>
        </div>
      </div>
    </div>
  )
}
