import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Dev: the UI talks to the adapter on :8090. Prod: the adapter serves dist/.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api/terminal': { target: process.env.SMT_DEV_ADAPTER || 'http://127.0.0.1:8090', changeOrigin: true } },
  },
  build: { outDir: 'dist', sourcemap: false },
});
