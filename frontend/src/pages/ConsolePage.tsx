import { useCallback, useEffect, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import {
  Play,
  Square,
  FileSymlink,
  Save,
  RotateCcw,
  FolderOpen,
} from 'lucide-react'
import * as api from '@/api/instances'
import { useStore } from '@/store/useStore'
import { toast } from '@/store/useToast'
import ConsolePanel from '@/components/ConsolePanel'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'

/* ─── Helper: a labelled form row ─── */
function FieldRow({
  label,
  children,
  className,
}: {
  label: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={`space-y-1.5 ${className ?? ''}`}>
      <Label className="text-xs text-muted-foreground font-medium">{label}</Label>
      {children}
    </div>
  )
}

/* ─── Helper: auto-resize textarea ─── */
function AutoTextarea({
  value,
  onChange,
  placeholder,
  className,
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  className?: string
}) {
  return (
    <Textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className={`font-mono text-xs leading-relaxed ${className ?? ''}`}
      rows={8}
    />
  )
}

/* ════════════════════════════════════════════════════
   ConsolePage
   ════════════════════════════════════════════════════ */
export default function ConsolePage() {
  const { name } = useParams<{ name: string }>()
  const [searchParams] = useSearchParams()
  const decodedName = decodeURIComponent(name ?? '')
  const defaultTab = searchParams.get('tab') || 'connection'

  const { fetchInstances } = useStore()

  /* ─── Local state ─── */
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [starting, setStarting] = useState(false)
  const [running, setRunning] = useState(false)
  const [runtime, setRuntime] = useState<Record<string, boolean>>({})

  // Config form fields (flat map matching backend config keys)
  const [cfg, setCfg] = useState<Record<string, unknown>>({})

  /* ─── Load config ─── */
  const load = useCallback(async () => {
    if (!decodedName) return
    setLoading(true)
    try {
      const data = await api.getInstanceConfig(decodedName)
      setRunning(data.running)
      setRuntime((data.runtime_state ?? {}) as Record<string, boolean>)
      setCfg((data.config ?? {}) as Record<string, unknown>)
    } catch (err) {
      console.error('Load config failed:', err)
    } finally {
      setLoading(false)
    }
  }, [decodedName])

  useEffect(() => {
    load()
  }, [load])

  /* ─── Helpers for form fields ─── */
  const getStr = (key: string, fallback = '') => String(cfg[key] ?? fallback)
  const getNum = (key: string, fallback: number) => Number(cfg[key] ?? fallback)

  const setStr = (key: string) => (v: string) => setCfg((prev) => ({ ...prev, [key]: v }))
  const setNum = (key: string) => (v: string) => {
    const n = v === '' ? '' : Number(v)
    setCfg((prev) => ({ ...prev, [key]: n }))
  }

  /* ─── Save ─── */
  const handleSave = async () => {
    if (!decodedName) return
    setSaving(true)
    try {
      await api.updateInstanceConfig(decodedName, cfg)
      await load()
      await fetchInstances()
    } catch (err) {
      console.error('Save failed:', err)
      toast.error('保存失败：' + (err instanceof Error ? err.message : String(err)))
    } finally {
      setSaving(false)
    }
  }

  /* ─── Start / Stop ─── */
  const handleStart = async () => {
    if (!decodedName) return
    setStarting(true)
    try {
      await api.startBot(decodedName)
      await load()
      await fetchInstances()
    } catch (err) {
      console.error('Start failed:', err)
      toast.error('启动失败：' + (err instanceof Error ? err.message : String(err)))
    } finally {
      setStarting(false)
    }
  }

  const handleStop = async () => {
    if (!decodedName) return
    try {
      await api.stopBot(decodedName)
      await load()
      await fetchInstances()
    } catch (err) {
      console.error('Stop failed:', err)
      toast.error('停止失败：' + (err instanceof Error ? err.message : String(err)))
    }
  }

  /* ─── 机器人通过 WS 检测到停止 ─── */
  const handleBotStopped = useCallback(() => {
    // 短延迟后重新加载，让后端更新状态
    setTimeout(() => {
      load()
      fetchInstances()
    }, 500)
  }, [load, fetchInstances])

  /* ─── Runtime checkbox toggle ─── */
  const handleRuntimeToggle = async (key: string, checked: boolean) => {
    if (!decodedName) return
    setRuntime((prev) => ({ ...prev, [key]: checked }))
    try {
      await api.updateRuntime(decodedName, { [key]: checked })
    } catch (err) {
      console.error('Runtime toggle failed:', err)
      setRuntime((prev) => ({ ...prev, [key]: !checked }))
    }
  }

  /* ─── Render (always from a single root — no early returns) ─── */

  const enableReply = runtime.enable_reply === true
  const enableAutoComment = runtime.enable_auto_comment === true
  const enableLogging = runtime.enable_logging !== false

  return (
    <div key={decodedName || 'empty'} className="animate-fadeIn flex h-full flex-col">
      {!decodedName ? (
        <div className="flex h-full items-center justify-center text-muted-foreground">
          无效的实例名称
        </div>
      ) : (
        <>
          {/* ═══ Toolbar ═══ */}
          <header className="flex items-center gap-2 border-b px-4 py-2 shrink-0">
            <div className="flex items-center gap-2 mr-4">
              <span
                className={`inline-block size-2 rounded-full ${
                  running ? 'bg-emerald-500 animate-pulse' : 'bg-muted-foreground/40'
                }`}
              />
              <span className="font-semibold text-sm">{decodedName}</span>
              <span className="text-xs text-muted-foreground">
                {running ? '运行中' : '已停止'}
              </span>
            </div>

            <Separator orientation="vertical" className="h-6" />

            {running ? (
              <Button variant="destructive" size="sm" onClick={handleStop}>
                <Square className="size-3.5" /> 停止
              </Button>
            ) : (
              <Button variant="default" size="sm" onClick={handleStart} disabled={starting} className="bg-emerald-600 hover:bg-emerald-700">
                <Play className="size-3.5" /> {starting ? '启动中…' : '启动'}
              </Button>
            )}

            <Button variant="outline" size="sm" onClick={handleSave} disabled={saving}>
              <Save className="size-3.5" /> {saving ? '保存中…' : '保存配置'}
            </Button>

            <Button variant="ghost" size="sm" onClick={load}>
              <RotateCcw className="size-3.5" /> 刷新
            </Button>

            <Separator orientation="vertical" className="h-6" />

            <label className="flex items-center gap-1.5 text-xs cursor-pointer select-none">
              <Checkbox
                id="rt-reply"
                checked={enableReply}
                onCheckedChange={(c) => handleRuntimeToggle('enable_reply', c === true)}
              />
              <span>回复</span>
            </label>

            <label className="flex items-center gap-1.5 text-xs cursor-pointer select-none">
              <Checkbox
                id="rt-comment"
                checked={enableAutoComment}
                onCheckedChange={(c) => handleRuntimeToggle('enable_auto_comment', c === true)}
              />
              <span>感知</span>
            </label>

            <label className="flex items-center gap-1.5 text-xs cursor-pointer select-none">
              <Checkbox
                id="rt-log"
                checked={enableLogging}
                onCheckedChange={(c) => handleRuntimeToggle('enable_logging', c === true)}
              />
              <span>日志</span>
            </label>

            <Separator orientation="vertical" className="h-6" />

            <Button
              variant="ghost"
              size="sm"
              onClick={async () => {
                try {
                  const res = await api.syncLogs(decodedName)
                  const details = res.total_lines != null ? `（${res.total_lines} 行）` : ''
                  toast.success(`日志已同步${details}`)
                } catch (err) {
                  toast.error('同步日志失败：' + (err instanceof Error ? err.message : String(err)))
                }
              }}
              title="同步日志"
            >
              <FileSymlink className="size-3.5" /> 同步日志
            </Button>
          </header>

          {/* ═══ Body ═══ */}
          <div className={`flex-1 overflow-auto ${running && !loading ? 'p-2' : 'p-4'}`}>
            {loading ? (
              <div className="flex h-full items-center justify-center text-muted-foreground">
                加载中…
              </div>
            ) : running ? (
              <div className="h-full">
                <ConsolePanel
                  instanceName={decodedName}
                  onBotStopped={handleBotStopped}
                />
              </div>
            ) : (
              <Tabs defaultValue={defaultTab} className="w-full">
                <TabsList className="w-full flex-wrap h-auto justify-start gap-1 bg-transparent p-0 mb-4">
                  <TabsTrigger value="connection" className="text-xs data-[state=active]:bg-background">连接设置</TabsTrigger>
                  <TabsTrigger value="model" className="text-xs">模型设置</TabsTrigger>
                  <TabsTrigger value="bot" className="text-xs">机器人设置</TabsTrigger>
                  <TabsTrigger value="ai" className="text-xs">AI 调优</TabsTrigger>
                  <TabsTrigger value="network" className="text-xs">网络设置</TabsTrigger>
                  <TabsTrigger value="prompts" className="text-xs">提示词与指令</TabsTrigger>
                </TabsList>

                <TabsContent value="connection">
                  <Card>
                    <CardHeader><CardTitle>连接设置</CardTitle></CardHeader>
                    <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <FieldRow label="API URL">
                        <Input value={getStr('deepseek_api_url')} onChange={(e) => setStr('deepseek_api_url')(e.target.value)} placeholder="https://api.deepseek.com/v1/chat/completions" />
                      </FieldRow>
                      <FieldRow label="WS URL">
                        <Input value={getStr('ws_url')} onChange={(e) => setStr('ws_url')(e.target.value)} placeholder="ws://127.0.0.1:8080" />
                      </FieldRow>
                      <FieldRow label="API Key" className="md:col-span-2">
                        <Input type="password" value={getStr('deepseek_api_key')} onChange={(e) => setStr('deepseek_api_key')(e.target.value)} placeholder="sk-..." />
                      </FieldRow>
                    </CardContent>
                  </Card>
                </TabsContent>

                <TabsContent value="model">
                  <Card>
                    <CardHeader><CardTitle>模型设置</CardTitle></CardHeader>
                    <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <FieldRow label="Pro 模型">
                        <Input value={getStr('model_pro')} onChange={(e) => setStr('model_pro')(e.target.value)} placeholder="deepseek-v4-pro" />
                      </FieldRow>
                      <FieldRow label="Flash 模型">
                        <Input value={getStr('model_flash')} onChange={(e) => setStr('model_flash')(e.target.value)} placeholder="deepseek-v4-flash" />
                      </FieldRow>
                    </CardContent>
                  </Card>
                </TabsContent>

                <TabsContent value="bot">
                  <Card>
                    <CardHeader><CardTitle>机器人设置</CardTitle></CardHeader>
                    <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <FieldRow label="游戏内名称">
                        <Input value={getStr('bot_name')} onChange={(e) => setStr('bot_name')(e.target.value)} />
                      </FieldRow>
                      <FieldRow label="管理员">
                        <Input value={getStr('admin_username')} onChange={(e) => setStr('admin_username')(e.target.value)} />
                      </FieldRow>
                      <FieldRow label="发送者格式识别">
                        <Input value={getStr('sender_patterns')} onChange={(e) => setStr('sender_patterns')(e.target.value)} placeholder={'<{name}>,{name}:'} />
                      </FieldRow>
                      <FieldRow label="触发前缀">
                        <Input value={getStr('trigger_prefix')} onChange={(e) => setStr('trigger_prefix')(e.target.value)} placeholder="@bot" />
                      </FieldRow>
                      <FieldRow label="发送模式">
                        <Select value={getStr('send_mode', 'raw')} onValueChange={setStr('send_mode')}>
                          <SelectTrigger><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="raw">raw — 原生</SelectItem>
                            <SelectItem value="me">me — /me 动作</SelectItem>
                            <SelectItem value="say" disabled>say — 已弃用</SelectItem>  {/* [FIX-P0-15] 仅保持旧值显示，不再可选 */}
                          </SelectContent>
                        </Select>
                      </FieldRow>
                      <FieldRow label="回复前缀">
                        <Input value={getStr('reply_prefix')} onChange={(e) => setStr('reply_prefix')(e.target.value)} />
                      </FieldRow>
                      <FieldRow label="氛围前缀">
                        <Input value={getStr('comment_prefix')} onChange={(e) => setStr('comment_prefix')(e.target.value)} />
                      </FieldRow>
                      <FieldRow label="冷却时间 (秒)">
                        <Input type="number" value={getNum('cooldown_seconds', 15)} onChange={(e) => setNum('cooldown_seconds')(e.target.value)} />
                      </FieldRow>
                    </CardContent>
                  </Card>
                </TabsContent>

                <TabsContent value="ai">
                  <Card>
                    <CardHeader><CardTitle>AI 调优</CardTitle></CardHeader>
                    <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <FieldRow label="Temperature">
                        <Input type="number" step="0.1" min="0" max="2" value={getNum('temperature', 0.7)} onChange={(e) => setNum('temperature')(e.target.value)} />
                      </FieldRow>
                      <FieldRow label="Max Tokens">
                        <Input type="number" value={getNum('max_tokens', 300)} onChange={(e) => setNum('max_tokens')(e.target.value)} />
                      </FieldRow>
                      <FieldRow label="API 超时 (秒)">
                        <Input type="number" value={getNum('api_timeout', 15)} onChange={(e) => setNum('api_timeout')(e.target.value)} />
                      </FieldRow>
                      <FieldRow label="对话记忆条数">
                        <Input type="number" value={getNum('max_history', 20)} onChange={(e) => setNum('max_history')(e.target.value)} />
                      </FieldRow>
                      <FieldRow label="重试次数">
                        <Input type="number" value={getNum('retry_count', 2)} onChange={(e) => setNum('retry_count')(e.target.value)} />
                      </FieldRow>
                      <FieldRow label="重试间隔 (秒)">
                        <Input type="number" step="0.5" value={getNum('retry_delay', 1.5)} onChange={(e) => setNum('retry_delay')(e.target.value)} />
                      </FieldRow>
                      <FieldRow label="全局上下文窗口">
                        <Input type="number" value={getNum('global_context_size', 10)} onChange={(e) => setNum('global_context_size')(e.target.value)} />
                      </FieldRow>
                      <FieldRow label="发送字节上限">
                        <Input type="number" value={getNum('max_command_bytes', 500)} onChange={(e) => setNum('max_command_bytes')(e.target.value)} />
                      </FieldRow>
                      <FieldRow label="氛围评论间隔 (秒)">
                        <Input type="number" value={getNum('auto_comment_interval', 300)} onChange={(e) => setNum('auto_comment_interval')(e.target.value)} />
                      </FieldRow>
                    </CardContent>
                  </Card>
                </TabsContent>

                <TabsContent value="network">
                  <Card>
                    <CardHeader><CardTitle>网络设置</CardTitle></CardHeader>
                    <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <FieldRow label="心跳检查间隔 (秒)">
                        <Input type="number" value={getNum('heartbeat_check_interval', 30)} onChange={(e) => setNum('heartbeat_check_interval')(e.target.value)} />
                      </FieldRow>
                      <FieldRow label="心跳超时 (秒)">
                        <Input type="number" value={getNum('heartbeat_timeout', 600)} onChange={(e) => setNum('heartbeat_timeout')(e.target.value)} />
                      </FieldRow>
                      <FieldRow label="重连延迟 (秒)">
                        <Input type="number" value={getNum('reconnect_delay', 5)} onChange={(e) => setNum('reconnect_delay')(e.target.value)} />
                      </FieldRow>
                      <FieldRow label="重连长延迟 (秒)">
                        <Input type="number" value={getNum('reconnect_delay_long', 10)} onChange={(e) => setNum('reconnect_delay_long')(e.target.value)} />
                      </FieldRow>
                      <FieldRow label="日志保存路径">
                        <div className="flex gap-2">
                          <Input value={getStr('log_dir', 'logs')} onChange={(e) => setStr('log_dir')(e.target.value)} placeholder="logs" className="flex-1" />
                          <Button
                            variant="outline"
                            size="icon"
                            type="button"
                            title="打开日志文件夹"
                            onClick={() => {
                              api.openLogFolder(decodedName).catch((err) =>
                                console.error('openLogFolder failed:', err)
                              )
                            }}
                          >
                            <FolderOpen className="size-4" />
                          </Button>
                        </div>
                      </FieldRow>
                    </CardContent>
                  </Card>
                </TabsContent>

                <TabsContent value="prompts">
                  <div className="space-y-4">
                    <Card>
                      <CardHeader><CardTitle>系统提示词</CardTitle></CardHeader>
                      <CardContent>
                        <AutoTextarea
                          value={getStr('system_prompt')}
                          onChange={setStr('system_prompt')}
                          placeholder="输入系统提示词…"
                        />
                      </CardContent>
                    </Card>

                    <Card>
                      <CardHeader><CardTitle>氛围评论提示词</CardTitle></CardHeader>
                      <CardContent>
                        <AutoTextarea
                          value={getStr('auto_comment_prompt')}
                          onChange={setStr('auto_comment_prompt')}
                          placeholder="输入氛围评论提示词…"
                        />
                      </CardContent>
                    </Card>

                    <Card>
                      <CardHeader><CardTitle>自定义指令 (JSON)</CardTitle></CardHeader>
                      <CardContent>
                        <AutoTextarea
                          value={(() => {
                            try {
                              const raw = cfg.custom_commands
                              return raw ? JSON.stringify(raw, null, 2) : '[]'
                            } catch {
                              return '[]'
                            }
                          })()}
                          onChange={(v) => {
                            try {
                              const parsed = JSON.parse(v)
                              setCfg((prev) => ({ ...prev, custom_commands: parsed }))
                            } catch {
                              // Allow typing — don't update state while JSON is invalid
                            }
                          }}
                          placeholder='[{ "name": "帮助", "response": "...", "admin_only": false }]'
                        />
                        <p className="text-xs text-muted-foreground mt-1">
                          输入 JSON 数组格式，语法错误时不会保存。每项可包含: name, response, action, description, admin_only
                        </p>
                      </CardContent>
                    </Card>
                  </div>
                </TabsContent>

              </Tabs>
            )}
          </div>
        </>
      )}
    </div>
  )
}
