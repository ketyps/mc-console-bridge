import type { Instance, InstanceConfig } from '@/types/instance'

const BASE = '/api'

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    throw new Error(`[${res.status}] ${url}: ${text}`)
  }
  // Handle 204 No Content
  if (res.status === 204) return undefined as T
  return res.json()
}

/* ─── Instance CRUD ─── */

export async function getInstances(): Promise<Instance[]> {
  return request<Instance[]>('/instances')
}

export async function createInstance(data: { name: string; bot_name?: string }): Promise<Instance> {
  return request<Instance>('/instances', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function importInstance(
  name: string,
  config: Record<string, unknown>,
): Promise<{ name: string; bot_name: string }> {
  return request<{ name: string; bot_name: string }>('/instances/import', {
    method: 'POST',
    body: JSON.stringify({ name, config }),
  })
}

export async function deleteInstance(name: string): Promise<void> {
  return request<void>(`/instances/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  })
}

export async function renameInstance(name: string, newName: string): Promise<Instance> {
  return request<Instance>(`/instances/${encodeURIComponent(name)}/rename`, {
    method: 'POST',
    body: JSON.stringify({ new_name: newName }),
  })
}

export async function duplicateInstance(name: string, newName: string): Promise<Instance> {
  return request<Instance>(`/instances/${encodeURIComponent(name)}/duplicate`, {
    method: 'POST',
    body: JSON.stringify({ new_name: newName }),
  })
}

export async function pinInstance(name: string): Promise<Instance> {
  return request<Instance>(`/instances/${encodeURIComponent(name)}/pin`, {
    method: 'POST',
  })
}

/* ─── Config ─── */

export async function getInstanceConfig(name: string): Promise<InstanceConfig> {
  return request<InstanceConfig>(`/instances/${encodeURIComponent(name)}`)
}

export async function updateInstanceConfig(name: string, config: Record<string, unknown>): Promise<Instance> {
  return request<Instance>(`/instances/${encodeURIComponent(name)}`, {
    method: 'PUT',
    body: JSON.stringify(config),
  })
}

/* ─── Bot Control ─── */

export async function startBot(name: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/instances/${encodeURIComponent(name)}/start`, {
    method: 'POST',
  })
}

export async function stopBot(name: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/instances/${encodeURIComponent(name)}/stop`, {
    method: 'POST',
  })
}

/* ─── Runtime hot-update ─── */

export async function updateRuntime(
  name: string,
  data: Record<string, unknown>,
): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/instances/${encodeURIComponent(name)}/runtime`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

/* ─── Chat & Actions ─── */

export async function sendMessage(
  name: string,
  text: string,
  usePrefix?: boolean,
): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/instances/${encodeURIComponent(name)}/send`, {
    method: 'POST',
    body: JSON.stringify({ text, use_prefix: usePrefix }),
  })
}

export async function triggerComment(name: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/instances/${encodeURIComponent(name)}/trigger-comment`, {
    method: 'POST',
  })
}

export async function replyRecent(name: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/instances/${encodeURIComponent(name)}/reply-recent`, {
    method: 'POST',
  })
}

export async function syncLogs(name: string): Promise<{ ok: boolean; total_lines?: number; days?: string[] }> {
  return request<{ ok: boolean; total_lines?: number; days?: string[] }>(`/instances/${encodeURIComponent(name)}/sync-logs`, {
    method: 'POST',
  })
}

export async function openLogFolder(name: string): Promise<{ ok: boolean; path?: string }> {
  return request<{ ok: boolean; path?: string }>(
    `/instances/${encodeURIComponent(name)}/open-log-folder`,
    { method: 'POST' },
  )
}

export async function shutdownServer(): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>('/shutdown', { method: 'POST' })
}

export async function browseFolder(): Promise<{ path: string }> {
  return request<{ path: string }>('/browse-folder', { method: 'POST' })
}
