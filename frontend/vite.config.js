import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    fileParallelism: false,
    maxWorkers: 1,
    pool: 'threads',
    setupFiles: './tests/setup.js',
  },
})
