import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/runs': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/shipments': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/evals': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})

