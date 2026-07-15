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

export function useConsoleWS({ instanceName, isRunning }: UseConsoleWSOptions) {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

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
    if (!isRunning || !instanceName) {
      // Clean up if not running
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      setConnected(false)
      return
    }

    // Build WS URL via the Vite proxy path
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const host = window.location.host
    const url = `${proto}://${host}/ws/console/${encodeURIComponent(instanceName)}`

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
    }

    ws.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data) as LogEntry
        addLog(data)
      } catch {
        // Plain text fallback
        addLog({ text: event.data, type: 'raw' })
      }
    }

    ws.onclose = () => {
      setConnected(false)
      wsRef.current = null
    }

    ws.onerror = () => {
      setConnected(false)
      addLog({ text: '[WebSocket 连接错误]', type: 'error' })
    }

    return () => {
      ws.close()
      wsRef.current = null
      setConnected(false)
    }
  }, [isRunning, instanceName, addLog])

  return { logs, connected, clearLogs }
}
