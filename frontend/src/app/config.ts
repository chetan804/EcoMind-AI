/**
 * Runtime configuration. This is the ONLY place that reads import.meta.env; features import
 * `config` instead of hardcoding URLs.
 */

export const API_V1_PATH = '/api/v1';

/** Strip trailing slashes; an empty value means "same origin". */
export function normalizeBaseUrl(value: string | undefined): string {
  return (value ?? '').trim().replace(/\/+$/, '');
}

/** Trimmed value, or '' when unset or still a placeholder. */
export function normalizeKey(value: string | undefined): string {
  const key = (value ?? '').trim();
  return /^(change_?me|your[-_ ]|replace)/i.test(key) ? '' : key;
}

export type MapProvider = 'offline' | 'google';

/**
 * Which map engine the screens use. `offline` (the default) draws OpenStreetMap-based tiles that the
 * deployment hosts itself, needs no key and makes no third-party request. `google` is opt-in and also
 * needs VITE_GOOGLE_MAPS_API_KEY; with a key but no explicit choice the previous behaviour (Google) is kept.
 */
export function resolveMapProvider(value: string | undefined, googleKey: string): MapProvider {
  const choice = (value ?? '').trim().toLowerCase();
  if (choice === 'google' || choice === 'offline') return choice;
  return googleKey ? 'google' : 'offline';
}

const googleMapsApiKey = normalizeKey(import.meta.env.VITE_GOOGLE_MAPS_API_KEY);

export const config = {
  /** Backend origin (no path). Empty string = same origin, proxied by the dev/preview server. */
  apiBaseUrl: normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL),
  /**
   * Google Maps JavaScript API key. Public by nature (it ships in the bundle), so it MUST be
   * restricted by HTTP referrer and to the Maps JavaScript API in Google Cloud. Empty means maps
   * are not configured and every map screen shows its labelled fallback. Never reuse the
   * server-side key (GOOGLE_MAPS_SERVER_API_KEY) here.
   */
  googleMapsApiKey,
  mapProvider: resolveMapProvider(import.meta.env.VITE_MAP_PROVIDER, googleMapsApiKey),
  /** PMTiles file with the vector basemap (same origin, served with HTTP range support). See docs/maps/OFFLINE_MAPS.md. */
  mapTilesUrl: (import.meta.env.VITE_MAP_TILES_URL ?? '').trim() || '/map-assets/tiles/region.pmtiles',
  /** Fonts and sprites of the basemap, shipped with the app. */
  mapAssetsPath: '/map-assets',
  /** Optional cloud-based map style ID; 'DEMO_MAP_ID' is Google's id for unstyled maps with advanced markers. */
  googleMapsMapId: (import.meta.env.VITE_GOOGLE_MAPS_MAP_ID ?? '').trim() || 'DEMO_MAP_ID',
} as const;
