import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendTarget = env.VITE_DEV_BACKEND_URL || 'http://localhost:8000'

  return {
    plugins: [react()],
    server: {
      // Required by the hosted development preview; production deployments do not use this server.
      allowedHosts: true,
      host: '0.0.0.0',
      port: Number(env.VITE_DEV_PORT || 5173),
      proxy: {
        '/api': {
          target: backendTarget,
          changeOrigin: true,
          timeout: Number(env.VITE_DEV_PROXY_TIMEOUT_MS || 300000),
          proxyTimeout: Number(env.VITE_DEV_PROXY_TIMEOUT_MS || 300000),
        },
      },
    },
    build: {
      sourcemap: env.VITE_SOURCEMAP === 'true',
    },
  }
})
