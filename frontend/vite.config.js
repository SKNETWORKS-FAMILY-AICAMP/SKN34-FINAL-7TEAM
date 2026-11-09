import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    watch: process.env.CAIFE_WATCH_POLLING === 'true' ? { usePolling: true, interval: 1000 } : undefined,
    proxy: {
      '/api': {
        target: process.env.CAIFE_API_PROXY_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});
