import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// /api goes to the local api by default; set API_PROXY_TARGET to use a deployed environment
const apiTarget = process.env.API_PROXY_TARGET ?? 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: apiTarget, changeOrigin: true },
    },
  },
})
