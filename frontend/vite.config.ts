import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const port = Number(env.VITE_PORT || 5173)

  return {
    plugins: [react()],
    server: {
      host: '127.0.0.1',
      port,
      strictPort: true,
      proxy: {
        '/api': {
          target: env.VITE_API_TARGET || 'http://127.0.0.1:3210',
          changeOrigin: true,
        },
      },
    },
    preview: {
      host: '127.0.0.1',
      port,
    },
  }
})
