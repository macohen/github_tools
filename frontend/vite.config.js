import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  // Use relative paths for Electron file:// loading
  base: mode === 'electron' ? './' : '/',
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:5001',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: mode === 'electron' ? '../electron/frontend-dist' : 'dist',
    emptyOutDir: true,
  }
}))
