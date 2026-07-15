import { create } from 'zustand'

export type ToastType = 'success' | 'error' | 'info'

export interface ToastItem {
  id: number
  type: ToastType
  message: string
}

interface ToastState {
  toasts: ToastItem[]
  addToast: (type: ToastType, message: string) => void
  removeToast: (id: number) => void
}

let nextId = 1

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  addToast: (type, message) => {
    // 【修复】去重：同一条消息+类型已存在则不再重复添加
    const exists = useToastStore.getState().toasts.some(
      (t) => t.message === message && t.type === type,
    )
    if (exists) return

    const id = nextId++
    set((s) => ({ toasts: [...s.toasts, { id, type, message }] }))
    // Auto-dismiss after 5s
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }))
    }, 5000)
  },
  removeToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}))

/** Convenience helpers */
export const toast = {
  success: (msg: string) => useToastStore.getState().addToast('success', msg),
  error: (msg: string) => useToastStore.getState().addToast('error', msg),
  info: (msg: string) => useToastStore.getState().addToast('info', msg),
}
