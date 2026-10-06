import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    // The Monaco editor chunk is ~2.7 MB (~700 kB gzipped). It is loaded lazily after the page
    // shell (React.lazy), so its size doesn't delay first paint; the default 500 kB warning is
    // just noise for it.
    chunkSizeWarningLimit: 3000,
  },
  test: {
    environment: 'node', // our unit tests cover pure modules only; no DOM needed
  },
})
