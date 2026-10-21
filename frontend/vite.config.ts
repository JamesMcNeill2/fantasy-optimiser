import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// /api goes to the local api by default; set API_PROXY_TARGET to use a deployed environment
const apiTarget = process.env.API_PROXY_TARGET ?? 'http://127.0.0.1:8000'

// Team avatars only exist in a deployed site bucket (the batch copies them
// there), so /avatars goes to a deployed environment: SITE_PROXY_TARGET, or
// the api's target when that's a deployed one. With neither, every avatar
// fails to load and its initials badge shows instead.
const siteTarget = process.env.SITE_PROXY_TARGET ?? process.env.API_PROXY_TARGET

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: apiTarget, changeOrigin: true },
      ...(siteTarget === undefined
        ? {}
        : { '/avatars': { target: siteTarget, changeOrigin: true } }),
    },
  },
})
