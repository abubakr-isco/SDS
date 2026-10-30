import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { defineConfig, type Plugin } from 'vite'

// Hosting platforms (e.g. Render) set PORT and route traffic to 0.0.0.0:$PORT on their own domain.
const platformPort = process.env.PORT ? Number(process.env.PORT) : undefined
const onPlatform = platformPort !== undefined

/** Serves dist/404.html with a real 404 status; Vite's own preview 404 has an empty body. */
function notFoundPage(): Plugin {
  return {
    name: 'sds-not-found-page',
    configurePreviewServer(server) {
      const dist = server.config.build.outDir
      // Runs after Vite's static files and its /privacy → /privacy.html rewrite.
      return () => {
        server.middlewares.use((req, res, next) => {
          if (existsSync(join(dist, (req.url ?? '/').split('?')[0]))) return next()
          res.statusCode = 404
          res.setHeader('Content-Type', 'text/html')
          res.end(readFileSync(join(dist, '404.html')))
        })
      }
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss(), notFoundPage()],
  // Multi-page: unknown URLs must return 404, not the homepage.
  appType: 'mpa',
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
