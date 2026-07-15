import { useState } from 'react'
import { Settings, Monitor, Sun, Moon, FolderOpen, BookOpen, Check, Power } from 'lucide-react'
import { useTheme } from '@/components/theme-provider'
import { useStore } from '@/store/useStore'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import LogPathPopover from '@/components/log-path-popover'
import UsageGuide from '@/components/UsageGuide'
import ShutdownOverlay from '@/components/shutdown-overlay'

const THEME_OPTIONS = [
  { value: 'system' as const, label: '跟随系统', icon: Monitor },
  { value: 'light' as const, label: '浅色模式', icon: Sun },
  { value: 'dark' as const, label: '深色模式', icon: Moon },
]

export default function SettingsDropdown() {
  const { theme, setTheme } = useTheme()
  const activeName = useStore((s) => s.activeName)
  const [open, setOpen] = useState(false)
  const [logPathOpen, setLogPathOpen] = useState(false)
  const [showGuide, setShowGuide] = useState(false)
  const [confirmExit, setConfirmExit] = useState(false)
  const [exiting, setExiting] = useState(false)
  const [shutdownDone, setShutdownDone] = useState(false)

  const handleShutdown = async () => {
    setExiting(true)
    try {
      // Use a shorter timeout since the server will go down
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 5000)
      await fetch('/api/shutdown', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
      })
      clearTimeout(timeoutId)
    } catch {
      // Server may shut down before responding — that's expected
    }
    setShutdownDone(true)
    setConfirmExit(false)
    setExiting(false)
  }

  if (shutdownDone) return <ShutdownOverlay />

  return (
    <>
      <DropdownMenu open={open} onOpenChange={setOpen}>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start gap-2 text-xs text-muted-foreground hover:text-foreground"
          >
            <Settings className="size-4" />
            设置
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          side="top"
          align="start"
          sideOffset={8}
          className="w-56"
        >
          {/* ── 主题（子菜单） ── */}
          <DropdownMenuSub>
            <DropdownMenuSubTrigger className="gap-2 cursor-pointer">
              <Monitor className="size-4" />
              <span>主题</span>
            </DropdownMenuSubTrigger>
            <DropdownMenuSubContent className="w-44">
              {THEME_OPTIONS.map((opt) => {
                const Icon = opt.icon
                return (
                  <DropdownMenuItem
                    key={opt.value}
                    onClick={() => setTheme(opt.value)}
                    className="gap-2 cursor-pointer"
                  >
                    <Icon className="size-4" />
                    <span className="flex-1">{opt.label}</span>
                    {theme === opt.value && (
                      <Check className="size-4 text-primary" />
                    )}
                  </DropdownMenuItem>
                )
              })}
            </DropdownMenuSubContent>
          </DropdownMenuSub>

          <DropdownMenuSeparator />

          {/* ── 更改日志保存路径 ── */}
          <DropdownMenuItem
            onClick={() => {
              if (activeName) {
                setOpen(false)
                setTimeout(() => setLogPathOpen(true), 150)
              }
            }}
            disabled={!activeName}
            className="gap-2 cursor-pointer"
          >
            <FolderOpen className="size-4" />
            <span className="flex-1">更改日志保存路径</span>
            {!activeName && (
              <span className="text-[10px] text-muted-foreground">请先选实例</span>
            )}
          </DropdownMenuItem>

          <DropdownMenuSeparator />

          {/* ── 使用说明 ── */}
          <DropdownMenuItem
            onClick={() => { setOpen(false); setShowGuide(true) }}
            className="gap-2 cursor-pointer"
          >
            <BookOpen className="size-4" />
            <span className="flex-1">使用说明</span>
          </DropdownMenuItem>

          <DropdownMenuSeparator />

          {/* ── 退出程序 ── */}
          <DropdownMenuItem
            onClick={() => { setOpen(false); setConfirmExit(true) }}
            className="gap-2 cursor-pointer text-destructive focus:text-destructive"
          >
            <Power className="size-4" />
            <span className="flex-1">退出程序</span>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* 日志路径弹窗 */}
      {activeName && (
        <LogPathPopover
          instanceName={activeName}
          open={logPathOpen}
          onClose={() => setLogPathOpen(false)}
        />
      )}

      {/* 使用说明弹窗 */}
      {showGuide && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={(e) => { if (e.target === e.currentTarget) setShowGuide(false) }}
        >
          <div className="w-full max-w-2xl max-h-[85vh] mx-4 rounded-xl border border-border bg-card shadow-xl overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3 border-b border-border">
              <h3 className="text-sm font-semibold text-foreground">使用说明</h3>
              <button
                onClick={() => setShowGuide(false)}
                className="rounded-sm p-1 hover:bg-accent text-muted-foreground hover:text-foreground cursor-pointer"
              >
                ✕
              </button>
            </div>
            <div className="overflow-y-auto max-h-[calc(85vh-53px)]">
              <UsageGuide embedded />
            </div>
          </div>
        </div>
      )}

      {/* 退出确认弹窗 */}
      {confirmExit && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={(e) => { if (e.target === e.currentTarget) setConfirmExit(false) }}
        >
          <div className="w-full max-w-sm rounded-xl border border-border bg-card p-5 shadow-xl">
            <h3 className="text-sm font-semibold text-foreground mb-3">退出程序</h3>
            <div className="flex items-start gap-3 mb-4 p-3 rounded-lg bg-destructive/10">
              <Power className="size-5 shrink-0 mt-0.5 text-destructive" />
              <p className="text-sm text-foreground">
                确定要退出吗？所有正在运行的机器人实例将被停止，整个服务器将关闭。
              </p>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setConfirmExit(false)} disabled={exiting}>
                取消
              </Button>
              <Button size="sm" variant="destructive" onClick={handleShutdown} disabled={exiting}>
                {exiting ? '正在退出…' : '确认退出'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
