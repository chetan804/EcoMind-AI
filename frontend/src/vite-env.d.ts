/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Backend origin without path; empty means same origin (see .env.example). */
  readonly VITE_API_BASE_URL?: string;
  /** Browser key for the Maps JavaScript API (referrer-restricted; public by nature). */
  readonly VITE_GOOGLE_MAPS_API_KEY?: string;
  /** Optional Google Maps map ID (cloud styling); defaults to DEMO_MAP_ID. */
  readonly VITE_GOOGLE_MAPS_MAP_ID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
