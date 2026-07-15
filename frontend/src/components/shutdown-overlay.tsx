import { Power } from 'lucide-react'

export default function ShutdownOverlay() {
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-background">
      <div className="text-center space-y-4 max-w-sm px-6">
        <div className="mx-auto size-16 rounded-full bg-muted flex items-center justify-center">
          <Power className="size-8 text-muted-foreground" />
        </div>
        <h1 className="text-xl font-semibold text-foreground">程序已退出</h1>
        <p className="text-sm text-muted-foreground leading-relaxed">
          服务器和所有正在运行的机器人实例已安全关闭。
          <br />
          你可以关闭此浏览器标签页了。
        </p>
      </div>
    </div>
  )
}
