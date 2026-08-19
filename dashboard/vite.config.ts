import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",   // accessible depuis l'extérieur du conteneur Docker
    port: 5173,
    watch: {
      usePolling: true, // nécessaire sur certains systèmes (Windows + Docker)
    },
  },
})
