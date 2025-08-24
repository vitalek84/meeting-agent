/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_WEBSOCKET_HOST: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
