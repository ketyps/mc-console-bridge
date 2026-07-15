import { create } from 'zustand'
import type { Instance } from '@/types/instance'
import * as api from '@/api/instances'

interface InstanceState {
  instances: Instance[]
  activeName: string | null
  isLoading: boolean

  setInstances: (instances: Instance[]) => void
  fetchInstances: () => Promise<void>
  setActiveName: (name: string) => void
  clearActiveName: () => void
  addInstance: (instance: Instance) => void
  removeInstance: (name: string) => void
}

export const useStore = create<InstanceState>((set) => ({
  instances: [],
  activeName: null,
  isLoading: false,

  setInstances: (instances) => set({ instances }),

  fetchInstances: async () => {
    set({ isLoading: true })
    try {
      const instances = await api.getInstances()
      set({ instances })
    } catch (err) {
      console.error('Failed to fetch instances:', err)
    } finally {
      set({ isLoading: false })
    }
  },

  setActiveName: (name) => set({ activeName: name }),
  clearActiveName: () => set({ activeName: null }),

  addInstance: (instance) =>
    set((state) => ({ instances: [...state.instances, instance] })),

  removeInstance: (name) =>
    set((state) => ({
      instances: state.instances.filter((i) => i.name !== name),
      activeName: state.activeName === name ? null : state.activeName,
    })),
}))
