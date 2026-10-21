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
  build: {
    rolldownOptions: {
      output: {
        // Библиотеки — отдельными файлами: они меняются редко и кэшируются браузером,
        // а код приложения при обновлении скачивается заново маленьким файлом.
        codeSplitting: {
          groups: [
            { name: 'react', test: /node_modules[\\/](react|react-dom|react-router|react-router-dom|scheduler)[\\/]/ },
            { name: 'mantine', test: /node_modules[\\/]@mantine[\\/]/ },
            { name: 'icons', test: /node_modules[\\/]@tabler[\\/]/ },
            { name: 'vendor', test: /node_modules[\\/]/ },
          ],
        },
      },
    },
  },
});
