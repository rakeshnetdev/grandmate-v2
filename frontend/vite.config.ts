/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      // `@` maps to src/. Keeps imports stable when files move between folders, which
      // happens often in a feature-driven layout.
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 3535,
    // Fail loudly if 3535 is taken instead of silently starting on 3536 — the backend's
    // CORS allow-list only accepts :3535, so a bumped port turns every API call into an
    // opaque 400 on the preflight.
    strictPort: true,
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      exclude: ['src/main.tsx', 'src/test/**', '**/*.config.*'],
    },
  },
});
