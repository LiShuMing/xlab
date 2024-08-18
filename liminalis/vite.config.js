import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

const projectRoot = fileURLToPath(new URL('.', import.meta.url));
const xlabDocsRoot = fileURLToPath(new URL('../docs', import.meta.url));

export default defineConfig({
  plugins: [react()],
  server: {
    fs: {
      allow: [projectRoot, xlabDocsRoot],
    },
    proxy: {
      '/api/radar': 'http://localhost:8010',
      '/api/admin': 'http://localhost:8010',
      '/api/invest': 'http://localhost:8010',
      '/api/ego': 'http://localhost:8010',
      '/api': 'http://localhost:5000',
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-icons': ['lucide-react'],
        },
      },
    },
  },
});
