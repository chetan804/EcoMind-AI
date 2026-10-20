/**
 * Loads the Google Maps JavaScript API exactly once, on demand, and reports why it is unavailable.
 *
 * The API is loaded by injecting the official script tag (`loading=async`, libraries imported with
 * `importLibrary`). Nothing is requested from Google unless a map is rendered and a browser key is
 * configured. Failure modes are classified so screens can explain them:
 *   missing_key  no VITE_GOOGLE_MAPS_API_KEY at build time
 *   network      the script could not be fetched (offline, blocked by CSP/ad-blocker/firewall)
 *   timeout      no answer within LOAD_TIMEOUT_MS
 *   auth         Google rejected the key (invalid, wrong referrer, API not enabled, billing off)
 *   unsupported  the page loaded but the expected libraries are missing
 */
import { useSyncExternalStore } from 'react';
import { config } from '@/app/config';
import type { MapsFailureReason } from '../types';

export const LOAD_TIMEOUT_MS = 12_000;
const CALLBACK_NAME = '__ecomindMapsReady';

export type MapsState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; maps: typeof google.maps }
  | { status: 'failed'; reason: MapsFailureReason };

declare global {
  interface Window {
    gm_authFailure?: () => void;
    [CALLBACK_NAME]?: () => void;
  }
}

let state: MapsState = config.googleMapsApiKey ? { status: 'idle' } : { status: 'failed', reason: 'missing_key' };
let pending: Promise<void> | null = null;
const listeners = new Set<() => void>();

function set(next: MapsState): void {
  state = next;
  for (const listener of listeners) listener();
}

function scriptUrl(key: string): string {
  const params = new URLSearchParams({ key, v: 'weekly', loading: 'async', callback: CALLBACK_NAME });
  return `https://maps.googleapis.com/maps/api/js?${params.toString()}`;
}

async function importLibraries(): Promise<typeof google.maps> {
  const maps = window.google?.maps;
  if (!maps || typeof maps.importLibrary !== 'function') throw new Error('unsupported');
  await Promise.all([maps.importLibrary('maps'), maps.importLibrary('marker')]);
  return maps;
}

function inject(key: string): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    const timer = window.setTimeout(() => reject(new Error('timeout')), LOAD_TIMEOUT_MS);
    const finish = (fn: () => void) => {
      window.clearTimeout(timer);
      fn();
    };
    window[CALLBACK_NAME] = () => finish(resolve);
    const script = document.createElement('script');
    script.src = scriptUrl(key);
    script.async = true;
    script.onerror = () => finish(() => reject(new Error('network')));
    document.head.appendChild(script);
  });
}

/** Google calls this when it rejects the key AFTER the script loaded (bad key/referrer/billing). */
function installAuthFailureHook(): void {
  window.gm_authFailure = () => set({ status: 'failed', reason: 'auth' });
}

function classify(error: unknown): MapsFailureReason {
  const message = error instanceof Error ? error.message : '';
  return message === 'timeout' || message === 'network' || message === 'unsupported' ? message : 'network';
}

/** Start loading (idempotent). Safe to call from an effect. */
export function ensureGoogleMaps(): void {
  if (state.status !== 'idle' || pending) return;
  set({ status: 'loading' });
  installAuthFailureHook();
  pending = (typeof window.google?.maps?.importLibrary === 'function' ? Promise.resolve() : inject(config.googleMapsApiKey))
    .then(importLibraries)
    .then((maps) => {
      if (state.status === 'loading') set({ status: 'ready', maps });
    })
    .catch((error: unknown) => {
      set({ status: 'failed', reason: classify(error) });
    })
    .finally(() => {
      pending = null;
    });
}

/** Try again after a network failure or timeout (not after a rejected key: that needs a fix first). */
export function retryGoogleMaps(): void {
  if (state.status !== 'failed' || state.reason === 'missing_key' || state.reason === 'auth') return;
  document.querySelectorAll('script[src^="https://maps.googleapis.com/maps/api/js"]').forEach((node) => node.remove());
  set({ status: 'idle' });
  ensureGoogleMaps();
}

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

export function useGoogleMapsState(): MapsState {
  return useSyncExternalStore(subscribe, () => state, () => state);
}
