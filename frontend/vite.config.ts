import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          charts: ['recharts'],
          map: ['leaflet', 'react-leaflet'],
          vendor: ['react', 'react-dom', 'react-router-dom', '@tanstack/react-query'],
        },
      },
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Allow the sandbox preview host (and any subdomain of e2b.app) to reach the dev server.
    allowedHosts: ['.e2b.app', '.localhost'],
    proxy: {
      // Browser-facing code uses relative URLs only; the dev server proxies to the API.
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/docs': { target: 'http://127.0.0.1:8000' },
      '/openapi.json': { target: 'http://127.0.0.1:8000' },
    },
  },
  test: {
    environment: 'node',
  },
})
