/**
 * Vite Config — Ngon-Ngon Frontend
 * =================================
 * Multi-page app: admin.html, index.html, kds.html
 * Proxy API calls to backend during development.
 */
import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
  root: '.',
  build: {
    rollupOptions: {
      input: {
        index: resolve(__dirname, 'index.html'),
        admin: resolve(__dirname, 'admin.html'),
        kds: resolve(__dirname, 'kds.html'),
      }
    },
    outDir: 'dist',
    minify: 'terser',
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    }
  }
});
