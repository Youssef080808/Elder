import { defineConfig } from 'vite';

// In development Vite serves the front end and forwards every /api call to the
// FastAPI server, so the browser talks to one origin and the session cookie
// works without CORS games. In production FastAPI serves the built files too.
export default defineConfig({
  root: '.',
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: process.env.API_ORIGIN || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
  },
});
