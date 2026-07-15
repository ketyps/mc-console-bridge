export interface Instance {
  name: string
  bot_name: string
  running: boolean
  local: boolean
  pinned: boolean
  config?: Record<string, unknown>
}

export interface InstanceConfig extends Instance {
  config: Record<string, unknown>
  runtime_state?: Record<string, unknown>
}
