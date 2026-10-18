/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Backend origin without path; empty means same origin (see .env.example). */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
