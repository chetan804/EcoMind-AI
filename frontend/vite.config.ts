import { createReadStream, statSync } from 'node:fs';
import path from 'node:path';
import react from '@vitejs/plugin-react';
import type { Connect, Plugin } from 'vite';
import { defineConfig } from 'vitest/config';

// Server-side only settings (never bundled into client code):
//   DEV_PROXY_TARGET      backend origin the dev/preview server proxies API calls to
//   DEV_ALLOWED_HOSTS     comma-separated extra Host headers accepted by the dev server
//   MAP_DATA_DIR          folder with the offline map tile file (default ../deployment/map-data)
const proxyTarget = process.env.DEV_PROXY_TARGET ?? 'http://localhost:8000';
const allowedHosts = (process.env.DEV_ALLOWED_HOSTS ?? '')
  .split(',')
  .map((host) => host.trim())
  .filter(Boolean);

const proxy = Object.fromEntries(
  ['/api', '/health', '/ready'].map((prefix) => [prefix, { target: proxyTarget, changeOrigin: true }]),
);

const mapDataDir = path.resolve(process.env.MAP_DATA_DIR ?? path.join(import.meta.dirname, '..', 'deployment', 'map-data'));

/**
 * Serves the git-ignored offline tile file (PMTiles) at /map-assets/tiles/<name>.pmtiles for the dev and
 * preview servers, with HTTP Range support (PMTiles reads the file in slices). The production image serves
 * the same URL from a mounted volume (see deployment/docker/nginx.conf). Only *.pmtiles files in that
 * folder are served, and the name may not contain a path.
 */
const mapTiles: Connect.NextHandleFunction = (req, res, next) => {
  const match = /^\/map-assets\/tiles\/([A-Za-z0-9._-]+\.pmtiles)(?:\?.*)?$/.exec(req.url ?? '');
  if (!match?.[1] || (req.method !== 'GET' && req.method !== 'HEAD')) return next();
  const file = path.join(mapDataDir, match[1]);
  let size: number;
  try {
    size = statSync(file).size;
  } catch {
    res.statusCode = 404;
    res.end('Tile file not installed');
    return undefined;
  }
  res.setHeader('Accept-Ranges', 'bytes');
  res.setHeader('Content-Type', 'application/octet-stream');
  const range = /^bytes=(\d*)-(\d*)$/.exec(String(req.headers.range ?? ''));
  let start = 0;
  let end = size - 1;
  if (range) {
    if (range[1] !== '') start = Number(range[1]);
    if (range[2] !== '') end = Math.min(Number(range[2]), size - 1);
    if (range[1] === '' && range[2] !== '') {
      start = Math.max(0, size - Number(range[2]));
      end = size - 1;
    }
    if (start > end || start >= size) {
      res.statusCode = 416;
      res.setHeader('Content-Range', `bytes */${size}`);
      res.end();
      return undefined;
    }
    res.statusCode = 206;
    res.setHeader('Content-Range', `bytes ${start}-${end}/${size}`);
  }
  res.setHeader('Content-Length', String(end - start + 1));
  if (req.method === 'HEAD') {
    res.end();
    return undefined;
  }
  createReadStream(file, { start, end }).pipe(res);
  return undefined;
};
const mapTilesPlugin = (): Plugin => ({
  name: 'ecomind-map-tiles',
  configureServer: (server) => void server.middlewares.use(mapTiles),
  configurePreviewServer: (server) => void server.middlewares.use(mapTiles),
});

export default defineConfig({
  plugins: [react(), mapTilesPlugin()],
  resolve: { alias: { '@': path.resolve(import.meta.dirname, 'src') } },
  server: { host: '0.0.0.0', port: 5173, allowedHosts, proxy },
  preview: { host: '0.0.0.0', port: 4173, allowedHosts, proxy },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.test.{ts,tsx}'],
    css: false,
    testTimeout: 15000,
  },
});
