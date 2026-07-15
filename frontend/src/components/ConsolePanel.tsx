import { useEffect, useRef, useState } from 'react'
import { useConsoleWS, type LogEntry } from '@/hooks/useConsoleWS'
import * as api from '@/api/instances'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { Send, Terminal, Wifi, WifiOff } from 'lucide-react'

/* ─── 日志行颜色映射（双主题感知）─── */
// 浅色模式用深色、高饱和度的同色系；深色模式用亮色，保证两种背景下的对比度均 ≥ 4.5:1
// 三种高亮消息分别用不同色相家族（蓝/绿/紫），确保一目可辨
const typeStyles: Record<string, string> = {
  warn: 'text-amber-600 dark:text-amber-400/80',
  error: 'text-red-600 dark:text-red-400',
  chat: 'text-muted-foreground',
  raw: 'text-foreground',
  separator: 'text-muted-foreground/50 text-center border-b border-border/50 my-1.5',
  info: 'text-foreground',
  trigger: 'text-purple-400 font-medium',
  bot_send: 'text-cyan-300 font-medium',
  user_atbot: 'text-[#9333EA] dark:text-[#FF55FF]',      // 紫（浅色）/ 亮洋红（深色）
  robot_reply: 'text-[#1D4ED8] dark:text-[#55FFFF]',     // 蓝（浅色）/ 亮青（深色）
  perception_reply: 'text-[#15803D] dark:text-[#86efac]', // 绿（浅色）/ 亮绿（深色）
}

function getLineStyle(type?: string): string {
  return typeStyles[type ?? ''] ?? typeStyles.info
}

/* ─── 单条日志行 ─── */
function LogLine({ entry }: { entry: LogEntry }) {
  const base = 'px-2 py-[1px] whitespace-pre-wrap break-all font-mono text-xs leading-relaxed'
  return <div className={`${base} ${getLineStyle(entry.type)}`}>{entry.text}</div>
}

/* ════════════════════════════════════════════════
   ConsolePanel
   ════════════════════════════════════════════════ */
export default function ConsolePanel({
  instanceName,
  onBotStopped,
}: {
  instanceName: string
  onBotStopped?: () => void
}) {
  const { logs, connected, clearLogs } = useConsoleWS({
    instanceName,
    isRunning: true,
  })

  /* ─── 发送栏状态 ─── */
  const [text, setText] = useState('')
  const [usePrefix, setUsePrefix] = useState(false)
  const [sendMode, setSendMode] = useState('raw')
  const [sending, setSending] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  /* ─── 自动滚动 ─── */
  const scrollRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [logs, autoScroll])

  // 检测用户手动滚动
  const handleScroll = () => {
    const el = scrollRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60
    setAutoScroll(atBottom)
  }

  /* ─── 检测机器人停止 ─── */
  const prevConnected = useRef(connected)
  useEffect(() => {
    if (prevConnected.current && !connected && logs.length > 0) {
      const last = logs[logs.length - 1]
      if (last.text?.includes('已停止')) {
        onBotStopped?.()
      }
    }
    prevConnected.current = connected
  }, [connected, logs, onBotStopped])

  /* ─── 获取当前发送模式（从 runtime） ─── */
  useEffect(() => {
    api.getInstanceConfig(instanceName).then((data) => {
      let mode =
        (data as { runtime_state?: { send_mode?: string } }).runtime_state?.send_mode
      if (!mode || mode === 'say' || mode === 'json') mode = 'me'
      setSendMode(mode)
    }).catch(() => { /* ignore */ })
  }, [instanceName])

  /* ─── 发送消息 ─── */
  const handleSend = async () => {
    const trimmed = text.trim()
    if (!trimmed || sending) return
    setSending(true)
    try {
      await api.sendMessage(instanceName, trimmed, usePrefix)
      setText('')
      textareaRef.current?.focus()
    } catch (err) {
      console.error('Send failed:', err)
    } finally {
      setSending(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  /* ─── 发送模式切换 → 热更新 ─── */
  const handleSendModeChange = async (val: string) => {
    setSendMode(val)
    try {
      await api.updateRuntime(instanceName, { send_mode: val })
    } catch (err) {
      console.error('Update send mode failed:', err)
    }
  }

  /* ─── 清除控制台 ─── */
  const handleClear = () => {
    clearLogs()
  }

  return (
    <div className="animate-fadeIn flex h-full flex-col bg-card rounded-md border border-border overflow-hidden">
      {/* ─── 标题栏 ─── */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-muted/50 border-b border-border shrink-0">
        <div className="flex items-center gap-2">
          <Terminal className="size-3.5 text-muted-foreground" />
          <span className="text-xs text-muted-foreground font-mono">{instanceName}</span>
          {/* 连接状态 */}
          {connected ? (
            <span className="flex items-center gap-1 text-[11px] text-emerald-600 dark:text-emerald-500">
              <Wifi className="size-3" /> 已连接
            </span>
          ) : (
            <span className="flex items-center gap-1 text-[11px] text-muted-foreground">
              <WifiOff className="size-3" /> 断开
            </span>
          )}
        </div>
        <button
          onClick={handleClear}
          className="text-[11px] text-muted-foreground hover:text-foreground transition-colors cursor-pointer bg-transparent border-none"
        >
          清除
        </button>
      </div>

      {/* ─── 日志区域 ─── */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="console-scroll flex-1 overflow-y-auto py-1 font-mono text-xs leading-relaxed select-text scroll-smooth bg-card"
        style={{ scrollBehavior: 'smooth' }}
      >
        {logs.length === 0 && (
          <div className="flex h-full items-center justify-center text-muted-foreground text-xs">
            {connected ? '等待日志…' : '正在连接…'}
          </div>
        )}
        {logs.map((entry, i) => (
          <LogLine key={`${entry.timestamp ?? i}-${i}`} entry={entry} />
        ))}
        <div className="h-1" />
      </div>

      {/* ─── 发送栏 ─── */}
      <div className="shrink-0 border-t border-border bg-muted/30 p-2">
        <div className="flex items-end gap-2">
          {/* Textarea */}
          <div className="flex-1 min-w-0">
            <Textarea
              ref={textareaRef}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入消息… (Enter 发送, Shift+Enter 换行)"
              className="min-h-[36px] max-h-[120px] bg-input border-border text-foreground placeholder:text-muted-foreground resize-none font-mono text-xs"
              rows={1}
            />
          </div>

          {/* 发送按钮 */}
          <Button
            size="sm"
            onClick={handleSend}
            disabled={!text.trim() || sending}
            className="h-9 shrink-0"
          >
            <Send className="size-3.5" />
            {sending ? '…' : '发送'}
          </Button>
        </div>

        {/* 选项行 */}
        <div className="flex items-center gap-3 mt-1.5">
          {/* 前缀复选框 */}
          <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground cursor-pointer select-none hover:text-foreground transition-colors">
            <Checkbox
              id="send-prefix"
              checked={usePrefix}
              onCheckedChange={(c) => setUsePrefix(c === true)}
              className="size-3 border-border"
            />
            <span>前缀</span>
          </label>

          {/* 发送模式选择 */}
          <div className="flex items-center gap-1.5">
            <Label className="text-[11px] text-muted-foreground cursor-default">模式</Label>
            <Select value={sendMode} onValueChange={handleSendModeChange}>
              <SelectTrigger className="h-6 w-[80px] text-[11px] bg-input border-border text-muted-foreground px-2 py-0">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="text-xs min-w-[80px] bg-popover border-border text-popover-foreground">
                <SelectItem value="raw" className="text-xs">raw</SelectItem>
                <SelectItem value="me" className="text-xs">me</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* 日志计数 */}
          <span className="ml-auto text-[11px] text-muted-foreground">
            {logs.length} 条日志
          </span>
        </div>
      </div>
    </div>
  )
}
