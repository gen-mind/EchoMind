import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // Proxy API requests to backend
      '/api': {
        target: 'http://api.localhost',
        changeOrigin: true,
        secure: false,
      },
      // Proxy WebSocket connections
      '/api/v1/ws': {
        target: 'ws://api.localhost',
        ws: true,
        changeOrigin: true,
      },
    },
  },
})