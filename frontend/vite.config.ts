import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// En développement, Vite relaie /api vers FastAPI : le navigateur ne voit qu'une seule origine,
// ce qui permet au cookie de session SameSite=Strict de fonctionner sans CORS.
// En production, FastAPI sert directement le build (frontend/dist).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': 'http://127.0.0.1:8000', '/health': 'http://127.0.0.1:8000' },
  },
  build: { chunkSizeWarningLimit: 1500 },
})
