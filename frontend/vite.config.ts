import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// 注意: Tailwind CSS v4 @import "tailwindcss" 必须通过
// @tailwindcss/vite 插件注册才会生效，缺少此插件时 Vite
// 不会报错，但所有 utility class 和 @apply 都会被静默丢弃，
// 导致页面无任何样式。
// https://vite.dev/config/
export default defineConfig({
  plugins: [tailwindcss(), react()],
  resolve: {
    tsconfigPaths: true,
  },
  server: {
    port: 1420,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:18750',
        changeOrigin: true,
        ws: true,
      },
      '/ws': {
        target: 'http://127.0.0.1:18750',
        ws: true,
      },
    },
  },
})
