import { Routes, Route } from 'react-router-dom'
import RootLayout from '@/layouts/RootLayout'
import ConsolePage from '@/pages/ConsolePage'
import ToastContainer from '@/components/toast-container'

export default function App() {
  return (
    <>
      <Routes>
        <Route path="/" element={<RootLayout />}>
          <Route
            index
            element={
              <div className="flex h-full items-center justify-center text-muted-foreground">
                <div className="text-center space-y-2">
                  <p className="text-lg">请选择一个实例开始配置</p>
                  <p className="text-sm">点击左侧实例进入控制台</p>
                </div>
              </div>
            }
          />
          <Route path="console/:name" element={<ConsolePage />} />
        </Route>
      </Routes>
      <ToastContainer />
    </>
  )
}
