import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Hosting platforms (e.g. Render) set PORT and route traffic to 0.0.0.0:$PORT on their own domain.
const platformPort = process.env.PORT ? Number(process.env.PORT) : undefined
const onPlatform = platformPort !== undefined

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Locally: dedicated ports (5173 is used by another project), reachable only from this machine.
  server: {
    port: platformPort ?? 5180,
    strictPort: true,
    host: onPlatform ? '0.0.0.0' : undefined,
    allowedHosts: onPlatform ? true : undefined,
  },
  preview: {
    port: platformPort ?? 5181,
    strictPort: true,
    host: onPlatform ? '0.0.0.0' : undefined,
    allowedHosts: onPlatform ? true : undefined,
  },
})
