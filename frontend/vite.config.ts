import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/chat': { target: 'http://localhost:8000', changeOrigin: true },
      '/ingest': { target: 'http://localhost:8000', changeOrigin: true },
      '/health': { target: 'http://localhost:8000', changeOrigin: true },
      '/seed': { target: 'http://localhost:8000', changeOrigin: true },
      '/data': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
