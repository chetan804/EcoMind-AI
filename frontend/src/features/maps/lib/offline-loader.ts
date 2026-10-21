/**
 * Loads the built-in (offline) map engine on demand: MapLibre GL JS plus the PMTiles reader, both
 * bundled with the app (nothing comes from a third-party host). Reports why a map cannot be drawn:
 *   no_webgl    the browser has no WebGL (disabled, unsupported, remote session)
 *   load_error  the code chunk could not be loaded
 * A missing tile file is NOT a failure: markers and routes are still drawn on a plain background and
 * the screen says the base map is not installed (`basemap: 'missing'`).
 */
import { useSyncExternalStore } from 'react';
import type * as MapLibre from 'maplibre-gl';
import type * as PMTilesModule from 'pmtiles';
import { config } from '@/app/config';
import type { MapsFailureReason } from '../types';
import { basemapStyle, plainStyle } from './offline-style';
import { openMapTilesStyle } from './openmaptiles-style';
import { detectTileSchema, openMapTilesAttribution } from './tile-schema';

export const BASEMAP_CHECK_TIMEOUT_MS = 8_000;

export type OfflineMapsState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; lib: typeof MapLibre; style: MapLibre.StyleSpecification; basemap: 'installed' | 'missing' | 'unsupported' }
  | { status: 'failed'; reason: Extract<MapsFailureReason, 'no_webgl' | 'load_error'> };

let state: OfflineMapsState = { status: 'idle' };
let pending: Promise<void> | null = null;
let protocolAdded = false;
const listeners = new Set<() => void>();

function set(next: OfflineMapsState): void {
  state = next;
  for (const listener of listeners) listener();
}

/** True when the browser exposes WebGL. (jsdom has none, so tests fall back to the list view.) */
export function webglAvailable(): boolean {
  if (typeof WebGL2RenderingContext === 'undefined' && typeof WebGLRenderingContext === 'undefined') return false;
  try {
    const canvas = document.createElement('canvas');
    return Boolean(canvas.getContext('webgl2') ?? canvas.getContext('webgl'));
  } catch {
    return false;
  }
}

type Inspection = { installed: false } | { installed: true; metadata: unknown };

/** Reads the tile file header (it exists) and metadata (which layout it uses). */
async function inspectTiles(PMTiles: typeof PMTilesModule.PMTiles, url: string): Promise<Inspection> {
  const source = new PMTiles(new URL(url, window.location.origin).href);
  const timeout = new Promise<never>((_, reject) => {
    window.setTimeout(() => reject(new Error('timeout')), BASEMAP_CHECK_TIMEOUT_MS);
  });
  try {
    await Promise.race([source.getHeader(), timeout]);
  } catch {
    return { installed: false };
  }
  let metadata: unknown;
  try {
    metadata = await Promise.race([source.getMetadata(), timeout]);
  } catch {
    metadata = undefined; // unreadable metadata: treated as the documented default layout
  }
  return { installed: true, metadata };
}

function styleFor(inspection: Inspection): { style: MapLibre.StyleSpecification; basemap: 'installed' | 'missing' | 'unsupported' } {
  if (!inspection.installed) return { style: plainStyle(), basemap: 'missing' };
  const schema = detectTileSchema(inspection.metadata);
  if (schema === 'unknown') return { style: plainStyle(), basemap: 'unsupported' };
  if (schema === 'openmaptiles') {
    const attribution = openMapTilesAttribution(inspection.metadata);
    return { style: openMapTilesStyle(config.mapTilesUrl, config.mapAssetsPath, attribution), basemap: 'installed' };
  }
  return { style: basemapStyle(config.mapTilesUrl, config.mapAssetsPath), basemap: 'installed' };
}

async function load(): Promise<void> {
  if (!webglAvailable()) {
    set({ status: 'failed', reason: 'no_webgl' });
    return;
  }
  try {
    const [lib, pmtiles, worker] = await Promise.all([
      import('maplibre-gl'),
      import('pmtiles'),
      // The worker is built as its own bundled file and served from this origin. (MapLibre 6 otherwise
      // looks for it next to its own module, which does not exist once the app is bundled.)
      import('maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'),
      import('maplibre-gl/dist/maplibre-gl.css'),
    ]);
    if (!protocolAdded) {
      lib.setWorkerUrl(worker.default);
      lib.addProtocol('pmtiles', new pmtiles.Protocol().tile);
      protocolAdded = true;
    }
    const { style, basemap } = styleFor(await inspectTiles(pmtiles.PMTiles, config.mapTilesUrl));
    set({ status: 'ready', lib, basemap, style });
  } catch {
    set({ status: 'failed', reason: 'load_error' });
  }
}

/** Start loading (idempotent). Safe to call from an effect. */
export function ensureOfflineMaps(): void {
  if (state.status !== 'idle' || pending) return;
  set({ status: 'loading' });
  pending = load().finally(() => {
    pending = null;
  });
}

/** Try again after a load error. */
export function retryOfflineMaps(): void {
  if (state.status !== 'failed' || state.reason !== 'load_error') return;
  set({ status: 'idle' });
  ensureOfflineMaps();
}

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

export function useOfflineMapsState(): OfflineMapsState {
  return useSyncExternalStore(subscribe, () => state, () => state);
}
