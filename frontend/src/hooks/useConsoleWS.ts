import { useCallback, useEffect, useRef, useState } from 'react'

export interface LogEntry {
  text: string
  type?: string
  timestamp?: number
}

interface UseConsoleWSOptions {
  instanceName: string
  isRunning: boolean
}

/** 断开后自动重连的间隔 */
const RECONNECT_DELAY_MS = 3000

/** 服务端发出这些消息表示机器人已经不在运行，再重连只会反复收到"未运行"，应停止重连 */
const TERMINAL_MESSAGES = ['机器人已停止', '机器人未运行']

export function useConsoleWS({ instanceName, isRunning }: UseConsoleWSOptions) {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<number | null>(null)
  // 本次 effect 是否已被清理（卸载 / 参数变化）
  const disposedRef = useRef(true)

  // Accumulator ref to avoid stale closure inside onmessage
  const logsRef = useRef<LogEntry[]>([])

  const addLog = useCallback((entry: LogEntry) => {
    const enriched = { ...entry, timestamp: entry.timestamp ?? Date.now() }
    logsRef.current = [...logsRef.current, enriched]
    setLogs(logsRef.current)
  }, [])

  const clearLogs = useCallback(() => {
    logsRef.current = []
    setLogs([])
  }, [])

  useEffect(() => {
    // 参数变化或卸载时，先彻底停掉上一次的连接与重连计划
    disposedRef.current = true
    if (reconnectTimerRef.current !== null) {
      window.clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.onclose = null
      wsRef.current.close()
      wsRef.current = null
    }
    setConnected(false)

    if (!isRunning || !instanceName) {
      return
    }

    let disposed = false
    disposedRef.current = false

    const scheduleReconnect = () => {
      if (disposed || disposedRef.current) return
      setConnected(false)
      wsRef.current = null
      if (reconnectTimerRef.current !== null) return
      reconnectTimerRef.current = window.setTimeout(() => {
        reconnectTimerRef.current = null
        connect()
      }, RECONNECT_DELAY_MS)
    }

    const connect = () => {
      if (disposed || disposedRef.current) return

      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const host = window.location.host
      const url = `${proto}://${host}/ws/console/${encodeURIComponent(instanceName)}`

      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        if (disposed || disposedRef.current) return
        setConnected(true)
      }

      ws.onmessage = (event: MessageEvent) => {
        if (disposed || disposedRef.current) return
        try {
          const data = JSON.parse(event.data) as LogEntry
          addLog(data)
          // 服务端明确告知已停止/未运行：不再自动重连，等待 isRunning 由上层刷新
          if (data.type === 'warn' && data.text && TERMINAL_MESSAGES.some((t) => data.text!.includes(t))) {
            setConnected(false)
            disposedRef.current = true
            if (reconnectTimerRef.current !== null) {
              window.clearTimeout(reconnectTimerRef.current)
              reconnectTimerRef.current = null
            }
            if (wsRef.current) {
              wsRef.current.onclose = null
              wsRef.current.close()
              wsRef.current = null
            }
          }
        } catch {
          // Plain text fallback（二进制帧/Blob 不当作日志文本）
          const text = typeof event.data === 'string' ? event.data : ''
          if (text) addLog({ text, type: 'raw' })
        }
      }

      ws.onclose = () => {
        if (disposed || disposedRef.current) return
        scheduleReconnect()
      }

      ws.onerror = () => {
        if (disposed || disposedRef.current) return
        addLog({ text: '[WebSocket 连接错误，正在重连…]', type: 'error' })
        // 关闭触发 onclose，由它统一调度重连
        try {
          ws.close()
        } catch {
          /* ignore */
        }
      }
    }

    connect()

    return () => {
      disposed = true
      disposedRef.current = true
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close()
        wsRef.current = null
      }
      setConnected(false)
    }
  }, [isRunning, instanceName, addLog])

  return { logs, connected, clearLogs }
}
