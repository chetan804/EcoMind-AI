import path from 'node:path';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// Server-side only settings (never bundled into client code):
//   DEV_PROXY_TARGET      backend origin the dev/preview server proxies API calls to
//   DEV_ALLOWED_HOSTS     comma-separated extra Host headers accepted by the dev server
const proxyTarget = process.env.DEV_PROXY_TARGET ?? 'http://localhost:8000';
const allowedHosts = (process.env.DEV_ALLOWED_HOSTS ?? '')
  .split(',')
  .map((host) => host.trim())
  .filter(Boolean);

const proxy = Object.fromEntries(
  ['/api', '/health', '/ready'].map((prefix) => [prefix, { target: proxyTarget, changeOrigin: true }]),
);

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': path.resolve(import.meta.dirname, 'src') } },
  server: { host: '0.0.0.0', port: 5173, allowedHosts, proxy },
  preview: { host: '0.0.0.0', port: 4173, allowedHosts, proxy },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.test.{ts,tsx}'],
    css: false,
  },
});
