/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** URL base del servicio local (por defecto http://127.0.0.1:8000). */
  readonly VITE_API_BASE_URL?: string;
  /** Token de sesión; debe coincidir con `local_agent.cli serve --token`. */
  readonly VITE_API_TOKEN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
