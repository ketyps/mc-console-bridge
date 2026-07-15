import { useEffect, useState } from 'react'
import { Outlet, useNavigate, useParams } from 'react-router-dom'
import {
  EllipsisVertical, Pin, PinOff, Pencil, Copy, Trash2,
} from 'lucide-react'
import { useStore } from '@/store/useStore'
import { toast } from '@/store/useToast'
import * as api from '@/api/instances'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import SettingsDropdown from '@/components/settings-dropdown'
import CreateInstanceDialog from '@/components/create-instance-dialog'
import DuplicateInstanceDialog from '@/components/duplicate-instance-dialog'
import RenameInstanceDialog from '@/components/rename-instance-dialog'
import ConfirmDialog from '@/components/confirm-dialog'

/* ─── Single instance list item ─── */
function InstanceItem({
  name,
  bot_name,
  running,
  pinned,
  isActive,
  onClick,
  onRename,
  onTogglePin,
  onDelete,
  onExport,
  onDuplicate,
}: {
  name: string
  bot_name: string
  running: boolean
  pinned: boolean
  isActive: boolean
  onClick: () => void
  onRename: () => void
  onTogglePin: () => void
  onDelete: () => void
  onExport: () => void
  onDuplicate: () => void
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}
      className={`
        group flex items-center gap-2
        rounded-lg px-3 py-2.5 mb-0.5
        cursor-pointer
        ${isActive ? 'bg-accent' : 'hover:bg-accent'}
        transition-colors
      `}
    >
      {/* Status dot — simple circle */}
      <span
        className={`w-2 h-2 rounded-full shrink-0 ${
          running ? 'bg-green-500' : 'bg-muted-foreground/40'
        }`}
      />

      {/* Name + subtitle */}
      <div className="flex flex-col min-w-0 flex-1">
        <span className="text-[15px] text-foreground truncate flex items-center gap-1">
          {name}
          {pinned && <Pin className="size-3 text-muted-foreground shrink-0" />}
        </span>
        <span className="text-xs text-muted-foreground truncate">
          {bot_name && bot_name !== name ? bot_name : running ? '运行中' : '已停止'}
        </span>
      </div>

      {/* Dropdown menu */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            onClick={(e) => e.stopPropagation()}
            className="opacity-0 group-hover:opacity-100 transition-opacity rounded-sm p-1 hover:bg-accent-foreground/10 cursor-pointer"
          >
            <EllipsisVertical className="size-4" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
          <DropdownMenuItem onClick={onRename}>
            <Pencil className="size-4" />
            重命名
          </DropdownMenuItem>
          <DropdownMenuItem onClick={onTogglePin}>
            {pinned
              ? <><PinOff className="size-4" /> 取消置顶</>
              : <><Pin className="size-4" /> 置顶</>
            }
          </DropdownMenuItem>
          <DropdownMenuItem onClick={onExport}>
            <Trash2 className="size-4 rotate-90" />
            导出配置
          </DropdownMenuItem>
          <DropdownMenuItem onClick={onDuplicate}>
            <Copy className="size-4" />
            复制实例
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onClick={onDelete}
            className="text-destructive focus:text-destructive focus:bg-destructive/10"
          >
            <Trash2 className="size-4" />
            删除
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}

/* ─── Root layout with sidebar ─── */
export default function RootLayout() {
  const navigate = useNavigate()
  const { name: routeName } = useParams()
  const {
    instances,
    activeName,
    isLoading,
    fetchInstances,
    setActiveName,
    removeInstance,
  } = useStore()

  /* ─── Dialog states ─── */
  const [createOpen, setCreateOpen] = useState(false)
  const [renameTarget, setRenameTarget] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)
  const [duplicateSource, setDuplicateSource] = useState<string | null>(null)

  // Fetch instances on mount
  useEffect(() => {
    fetchInstances()
  }, [fetchInstances])

  // Sync route param → activeName
  useEffect(() => {
    if (routeName && routeName !== activeName) {
      setActiveName(routeName)
    }
  }, [routeName, activeName, setActiveName])

  /* ─── Handlers ─── */

  const handleCreate = async (name: string) => {
    try {
      const inst = await api.createInstance({ name })
      useStore.getState().addInstance(inst)
      navigate(`/console/${encodeURIComponent(inst.name)}`)
      toast.success(`实例「${name}」已创建`)
    } catch (err) {
      toast.error('创建失败：' + (err instanceof Error ? err.message : String(err)))
    }
  }

  const handleRename = async (oldName: string, newName: string) => {
    try {
      await api.renameInstance(oldName, newName)
      await fetchInstances()
      toast.success(`已重命名为「${newName}」`)
    } catch (err) {
      toast.error('重命名失败：' + (err instanceof Error ? err.message : String(err)))
    }
  }

  const handleTogglePin = async (name: string) => {
    try {
      await api.pinInstance(name)
      await fetchInstances()
    } catch (err) {
      console.error('Pin toggle failed:', err)
    }
  }

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return
    try {
      await api.deleteInstance(deleteTarget)
      removeInstance(deleteTarget)
      if (activeName === deleteTarget) {
        navigate('/')
      }
      toast.success(`实例「${deleteTarget}」已删除`)
    } catch (err) {
      toast.error('删除失败：' + (err instanceof Error ? err.message : String(err)))
    }
    setDeleteTarget(null)
  }

  const handleExport = (name: string) => {
    const a = document.createElement('a')
    a.href = `/api/instances/${encodeURIComponent(name)}/export`
    a.download = `${name}_config.json`
    a.click()
  }

  const handleDuplicate = async (sourceName: string, newName: string) => {
    try {
      const inst = await api.duplicateInstance(sourceName, newName)
      useStore.getState().addInstance(inst)
      navigate(`/console/${encodeURIComponent(inst.name)}`)
      toast.success(`已从「${sourceName}」复制到「${newName}」`)
    } catch (err) {
      toast.error('复制失败：' + (err instanceof Error ? err.message : String(err)))
    }
  }

  // Sort: pinned first, then by name
  const sorted = [...instances].sort((a, b) => {
    if (a.pinned !== b.pinned) return a.pinned ? -1 : 1
    return a.name.localeCompare(b.name)
  })


  return (
    <div className="flex h-svh overflow-hidden">
      {/* ─── Sidebar ─── */}
      <aside className="flex w-60 flex-col border-r bg-sidebar shrink-0">
        {/* Header — keep original app name */}
        <div className="flex items-center px-4 py-3 border-b">
          <h1 className="text-sm font-semibold tracking-tight">Message Console</h1>
        </div>

        {/* Instance list */}
        <ScrollArea className="flex-1 px-3 py-3">
          {/* Full-width "新建实例" capsule button */}
          <button
            onClick={() => setCreateOpen(true)}
            className="
              w-full flex items-center justify-center gap-2
              rounded-full bg-muted hover:bg-accent
              text-sm text-foreground
              py-3 px-4 mb-4
              transition-colors cursor-pointer
            "
          >
            <span className="
              flex items-center justify-center
              w-5 h-5 rounded-full bg-foreground/10
            ">+</span>
            新建实例
          </button>

          {isLoading && instances.length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-8">加载中…</p>
          )}

          {!isLoading && instances.length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-8">
              暂无实例，点击上方按钮创建
            </p>
          )}

          {sorted.map((inst) => (
            <InstanceItem
              key={inst.name}
              name={inst.name}
              bot_name={inst.bot_name}
              running={inst.running}
              pinned={inst.pinned}
              isActive={inst.name === activeName}
              onClick={() => {
                setActiveName(inst.name)
                navigate(`/console/${encodeURIComponent(inst.name)}`)
              }}
              onRename={() => setRenameTarget(inst.name)}
              onTogglePin={() => handleTogglePin(inst.name)}
              onDelete={() => setDeleteTarget(inst.name)}
              onExport={() => handleExport(inst.name)}
              onDuplicate={() => setDuplicateSource(inst.name)}
            />
          ))}
        </ScrollArea>

        {/* ─── 底部：设置 ─── */}
        <div className="border-t px-2 py-2">
          <SettingsDropdown />
        </div>
      </aside>

      {/* ─── Dialogs ─── */}
      <CreateInstanceDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onConfirm={handleCreate}
        onImported={fetchInstances}
      />

      {duplicateSource && (
        <DuplicateInstanceDialog
          open={!!duplicateSource}
          sourceName={duplicateSource}
          onClose={() => setDuplicateSource(null)}
          onConfirm={(newName) => handleDuplicate(duplicateSource, newName)}
        />
      )}

      {renameTarget && (
        <RenameInstanceDialog
          open={!!renameTarget}
          currentName={renameTarget}
          onClose={() => setRenameTarget(null)}
          onConfirm={(newName) => handleRename(renameTarget, newName)}
        />
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        title="删除实例"
        message={`确定要删除实例「${deleteTarget}」吗？此操作不可撤销。`}
        confirmLabel="删除"
        destructive
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDeleteConfirm}
      />

      {/* ─── Main content ─── */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
