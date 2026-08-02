import { fileURLToPath } from 'node:url'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const contractsDir = fileURLToPath(new URL('../../contracts/generated/typescript', import.meta.url))

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@contracts': contractsDir,
    },
  },
  server: {
    fs: {
      allow: ['.', contractsDir],
    },
  },
})
