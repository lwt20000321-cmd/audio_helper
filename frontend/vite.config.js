import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: 'localhost',
    port: 5175,
    strictPort: true,   // 端口被占用时直接报错，不自动换端口
  },
})
