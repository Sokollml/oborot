import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // При локальной разработке (npm run dev) запросы /api уходят на бэкенд,
    // как в Docker это делает nginx.
    proxy: { '/api': 'http://localhost:8000' },
  },
});
